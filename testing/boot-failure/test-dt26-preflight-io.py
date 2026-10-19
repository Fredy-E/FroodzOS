#!/usr/bin/env python3
# dt26 preflight-IO persistence regressions: file fsync EIO must fail closed.
#
# Independent EIO probe showed _atomic_write_json swallowing the tmp-file
# fsync OSError and then replacing last-good while returning True
# (false-success path). Requirement: any initial pass persistence failure
# must refuse the GUI (rc 2, zero private SDDM starts) and preserve prior
# good data on precommit failure.
#
# Genuine scope: the ACTUAL writer/persist functions with a real EIO raised
# from os.fsync on regular files only (directory fsync passes through, so
# durability handling stays faithful). Portable fakes only; no hardware,
# no QEMU, no system changes, no USB/VT/firmware writes.
import errno
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

P = Path(__file__).resolve().parents[2]
SUP = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
POLICY = P / "builder/diagnostics/kestrel-graphics-policy.json"


def load_supervisor():
    spec = importlib.util.spec_from_file_location(
        "kestrel_graphics_supervisor_dt26io", SUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeClock:
    def __init__(self):
        self.now = 2000.0

    def monotonic(self):
        return self.now

    def sleep(self, d):
        try:
            self.now += max(0.0, float(d))
        except (ValueError, TypeError):
            pass


def real_owned(sid="7", display=""):
    return {"Id": sid, "User": "1000", "Name": "live", "Seat": "seat0",
            "Type": "wayland", "Class": "user", "State": "active",
            "Display": display, "Remote": "no", "Service": "sddm", "TTY": ""}


def eio_on_regular_files(fd):
    """Real EIO for regular-file fsync; directory fsync passes through."""
    try:
        is_dir = stat.S_ISDIR(os.fstat(fd).st_mode)
    except OSError:
        raise OSError(errno.EIO, "injected file fsync EIO")
    if is_dir:
        return os.fsync(fd)
    raise OSError(errno.EIO, "injected file fsync EIO")


def mock_guard_for(sessions, inject_at=3):
    class G:
        n = 0

        @staticmethod
        def collect_temperatures(root, required):
            G.n += 1
            if G.n == inject_at and sessions is not None:
                sessions["2"] = real_owned("2")
            return [{"type": t, "temp_mc": 42000} for t in required]

        @staticmethod
        def evaluate_temperatures(rows, required, minimum_mc=5000,
                                  stop_mc=80000):
            vals = {r["type"]: r["temp_mc"] for r in rows
                    if r["type"] in set(required)}
            errs = [] if set(vals) == set(required) else ["missing"]
            return {"ok": not errs, "errors": errs, "maximum_mc": 42000,
                    "sensors": vals}

        @staticmethod
        def collect_drm(root, device_root, card="card0"):
            return {"card": card, "driver": "simpledrm",
                    "character_device": True,
                    "connectors": [{"status": "connected",
                                    "modes": ["1920x1200"]}]}

        @staticmethod
        def evaluate_drm(snap):
            return {"ok": True, "errors": []}

    return G()


def full_runner(events, sessions, state):
    def run(cmd, timeout=None):
        c = list(cmd)
        events.append(list(c))
        if len(c) >= 2 and c[0] == "loginctl" and c[1] == "list-sessions":
            lines = "".join(s + "  1000 live\n" for s in sorted(sessions))
            return SimpleNamespace(returncode=0, stdout=lines, stderr="")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "show-session":
            sid = str(c[2])
            if len(c) == 3:
                # bare verify-after-terminate form (no -p flags)
                if sid in sessions:
                    d = sessions[sid]
                    return SimpleNamespace(
                        returncode=0,
                        stdout="\n".join(k + "=" + v for k, v in d.items()) + "\n",
                        stderr="")
                return SimpleNamespace(returncode=1, stdout="",
                                       stderr="no such session")
            if sid in sessions:
                requested = [c[i + 1] for i, t in enumerate(c)
                             if t == "-p" and i + 1 < len(c)]
                d = sessions[sid]
                out = [p + "=" + d[p] for p in requested if p in d]
                return SimpleNamespace(
                    returncode=0,
                    stdout=("\n".join(out) + "\n" if out else ""), stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="no")
        if c[:2] == ["systemctl", "start"]:
            if "kestrel-graphics-sddm.service" in c:
                state["unit"] = True
            if "getty@tty2.service" in c:
                state["tty"] = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "stop"]:
            if "kestrel-graphics-sddm.service" in c:
                state["unit"] = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "show"]:
            st = "active" if state["unit"] else "inactive"
            return SimpleNamespace(
                returncode=0,
                stdout="ActiveState=" + st + "\nSubState=running\nResult=success\n",
                stderr="")
        if c[:2] == ["systemctl", "is-active"]:
            if "kestrel-graphics-sddm.service" in c:
                return SimpleNamespace(
                    returncode=0 if state["unit"] else 3,
                    stdout="active\n" if state["unit"] else "inactive\n",
                    stderr="")
            if "getty@tty2.service" in c:
                return SimpleNamespace(
                    returncode=0 if state["tty"] else 3,
                    stdout="active\n" if state["tty"] else "inactive\n",
                    stderr="")
            return SimpleNamespace(returncode=3, stdout="inactive\n",
                                   stderr="")
        if c[:2] == ["systemctl", "kill"]:
            state["unit"] = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["loginctl", "terminate-session"]:
            sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["loginctl", "kill-session"]:
            sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def private_starts(events):
    return [c for c in events if c[:2] == ["systemctl", "start"]
            and "kestrel-graphics-sddm.service" in c]


def required_20():
    data = json.loads(POLICY.read_text())
    req = set(data["required_sensor_types"])
    assert len(req) == 20, f"policy must carry 20 sensor types, got {len(req)}"
    return req


class Dt26PreflightIoFsync(unittest.TestCase):
    def test_atomic_writer_file_fsync_eio_returns_false_preserves_last_good(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26io-writer-") as tmp:
            target = Path(tmp) / "preflight.json"
            good = {"passed": False, "reason": "prior-good-marker",
                    "detail": {"marker": True},
                    "thermal": None, "drm": None, "drm_snapshot": None,
                    "native_graphics_validated": False}
            good_bytes = json.dumps(good, sort_keys=True).encode("utf-8")
            target.write_bytes(good_bytes)
            with mock.patch.object(mod.os, "fsync",
                                   side_effect=eio_on_regular_files):
                self.assertFalse(mod._atomic_write_json(target, {"new": True}))
            # last-good preserved byte-identical; no tmp litter left behind
            self.assertEqual(target.read_bytes(), good_bytes)
            self.assertEqual(list(Path(tmp).glob(".tmp-preflight-*")), [])

    def test_pass_snapshot_fsync_failure_starts_nothing_preserves_prior(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26io-nostart-") as tmp:
            sd = Path(tmp)
            prior = {"passed": False, "reason": "prior-good-marker",
                     "detail": {"marker": True},
                     "thermal": None, "drm": None, "drm_snapshot": None,
                     "native_graphics_validated": False}
            prior_bytes = json.dumps(prior, sort_keys=True).encode("utf-8")
            (sd / "preflight.json").write_bytes(prior_bytes)
            sessions = {}
            state = {"unit": False, "tty": False}
            events = []
            run = full_runner(events, sessions, state)
            clock = FakeClock()
            with mock.patch.object(mod.os, "fsync",
                                   side_effect=eio_on_regular_files):
                rc = mod.run_bounded_session(
                    thermal_root=sd, drm_root=sd, device_root=sd,
                    card="card0", required={"cpu0-0-top-thermal"},
                    guard=mock_guard_for(None, inject_at=10**9),
                    runner=run, status_dir=sd, timeout_s=5, poll_s=0.1,
                    session_wait_s=0.5,
                    _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            self.assertEqual(private_starts(events), [])
            self.assertFalse((sd / "launch-allowed").exists())
            # precommit failure: prior good snapshot untouched
            self.assertEqual((sd / "preflight.json").read_bytes(), prior_bytes)

    def test_genuine_20sensor_drm_pass_starts_only_after_complete_save(self):
        mod = load_supervisor()
        req = required_20()
        with tempfile.TemporaryDirectory(prefix="dt26io-pass-") as tmp:
            sd = Path(tmp)
            sessions = {}
            state = {"unit": False, "tty": False}
            events = []
            start_seen = {}
            inner = full_runner(events, sessions, state)

            def run(cmd, timeout=None):
                c = list(cmd)
                if (c[:2] == ["systemctl", "start"]
                        and "kestrel-graphics-sddm.service" in c
                        and "seen" not in start_seen):
                    pf = sd / "preflight.json"
                    start_seen["seen"] = True
                    start_seen["exists"] = pf.exists()
                    if pf.exists():
                        start_seen["payload"] = json.loads(pf.read_text())
                        start_seen["bytes"] = len(pf.read_bytes())
                    start_seen["launch_exists"] = (sd / "launch-allowed").exists()
                return inner(cmd, timeout=timeout)

            clock = FakeClock()
            rc = mod.run_bounded_session(
                thermal_root=sd, drm_root=sd, device_root=sd,
                card="card0", required=req,
                guard=mock_guard_for(sessions),
                runner=run, status_dir=sd, timeout_s=6, poll_s=0.1,
                session_wait_s=3, start_wait_s=2,
                _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 0)
            self.assertTrue(private_starts(events), "private SDDM never started")
            # complete structured save existed BEFORE the private start
            self.assertTrue(start_seen.get("exists"),
                            "preflight.json missing at SDDM start")
            payload = start_seen["payload"]
            self.assertTrue(payload.get("passed") is True)
            self.assertEqual(payload.get("reason"), "preflight-pass")
            self.assertIsInstance(payload.get("detail"), dict)
            self.assertIn("thermal", payload.get("detail"))
            self.assertIsNotNone(payload.get("thermal"))
            self.assertIsNotNone(payload.get("drm"))
            self.assertIsNotNone(payload.get("drm_snapshot"))
            self.assertEqual(len(payload["thermal"]["sensors"]), 20)
            self.assertTrue(payload.get("native_graphics_validated") is False)
            self.assertLessEqual(start_seen["bytes"], 64 * 1024)
            self.assertNotIsInstance(payload.get("detail"), str)


class Dt26PreflightIoCapPreserved(unittest.TestCase):
    def test_oversize_writes_concise_refusal_and_returns_false(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26io-cap-") as tmp:
            sd = Path(tmp)
            big = {"blob": "x" * (70 * 1024)}
            ok = mod._save_preflight_result(
                sd, passed=True, reason="preflight-pass", detail=big,
                thermal={"ok": True}, drm={"ok": True}, drm_snapshot={})
            self.assertFalse(ok)
            refusal = json.loads((sd / "preflight.json").read_text())
            self.assertTrue(refusal.get("passed") is False)
            self.assertEqual(refusal.get("reason"), "preflight-snapshot-too-large")
            self.assertTrue(refusal.get("native_graphics_validated") is False)
            self.assertLessEqual(len(json.dumps(refusal).encode("utf-8")),
                                 64 * 1024)

    def test_atomic_writer_oversize_returns_false_writes_nothing(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26io-cap2-") as tmp:
            target = Path(tmp) / "preflight.json"
            self.assertFalse(mod._atomic_write_json(
                target, {"blob": "y" * (70 * 1024)}))
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(tmp).glob(".tmp-preflight-*")), [])

    def test_atomic_writer_success_path_still_true_no_litter(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26io-ok-") as tmp:
            target = Path(tmp) / "preflight.json"
            payload = {"passed": True, "reason": "ok", "detail": {"a": 1}}
            self.assertTrue(mod._atomic_write_json(target, payload))
            self.assertEqual(json.loads(target.read_text()), payload)
            self.assertEqual(list(Path(tmp).glob(".tmp-preflight-*")), [])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName("__main__"))
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(getattr(result, "skipped", [])),
              "genuine_shaped_fixtures": True,
              "native_hardware_validated": False}
    print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
