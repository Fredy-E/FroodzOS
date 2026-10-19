#!/usr/bin/env python3
# dt26 session fix RED regressions: empty/partial discovery, explicit Remote,
# atomic structured preflight pass snapshot before GUI start + persistence fail-closed.
# Genuine systemd 262 schema: User=numeric UID, Name=username, no UID prop,
# repeated -p flags required, Display empty normal for Wayland.
# Portable fakes only; no hardware, no QEMU, no system changes.
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

P = Path(__file__).resolve().parents[2]
SUP = P / "builder/diagnostics/kestrel-graphics-supervisor.py"


def load_supervisor():
    spec = importlib.util.spec_from_file_location("kestrel_graphics_supervisor_dt26fix", SUP)
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


def mock_guard():
    class G:
        @staticmethod
        def collect_temperatures(root, required):
            return [{"type": t, "temp_mc": 42000} for t in required]

        @staticmethod
        def evaluate_temperatures(rows, required, minimum_mc=5000, stop_mc=80000):
            vals = {r["type"]: r["temp_mc"] for r in rows if r["type"] in set(required)}
            errs = [] if set(vals) == set(required) else ["missing"]
            return {"ok": not errs, "errors": errs, "maximum_mc": 42000, "sensors": vals}

        @staticmethod
        def collect_drm(root, device_root, card="card0"):
            return {"card": card, "driver": "simpledrm", "character_device": True,
                    "connectors": [{"status": "connected", "modes": ["1920x1200"]}]}

        @staticmethod
        def evaluate_drm(snap):
            return {"ok": True, "errors": []}

    return G()


def runner_for(sessions, fail_list=False, fail_detail=(), rc_detail=0, stdout_detail=None):
    def run(cmd, timeout=None):
        c = list(cmd)
        if len(c) >= 2 and c[0] == "loginctl" and c[1] == "list-sessions":
            if fail_list:
                return SimpleNamespace(returncode=1, stdout="", stderr="fail")
            lines = "".join(s + "  1000 live\n" for s in sorted(sessions))
            return SimpleNamespace(returncode=0, stdout=lines, stderr="")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "show-session":
            sid = str(c[2])
            if sid in fail_detail:
                return SimpleNamespace(returncode=1, stdout="", stderr="fail")
            if stdout_detail is not None:
                return SimpleNamespace(returncode=rc_detail, stdout=stdout_detail, stderr="")
            if sid in sessions:
                for tok in c[3:]:
                    if "," in tok:
                        return SimpleNamespace(returncode=0, stdout="", stderr="")
                requested = [c[i + 1] for i, t in enumerate(c) if t == "-p" and i + 1 < len(c)]
                d = sessions[sid]
                lines = [p + "=" + d[p] for p in requested if p in d and p != "UID"]
                return SimpleNamespace(returncode=0, stdout=("\n".join(lines) + "\n" if lines else ""), stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="no such session")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    run.calls = []
    orig = run
    def wrapped(cmd, timeout=None):
        run.calls.append((list(cmd), timeout))
        return orig(cmd, timeout=timeout)
    return wrapped


class Dt26FixEmptyPartial(unittest.TestCase):
    def test_rc0_empty_detail_is_none_and_refuses(self):
        mod = load_supervisor()
        run = runner_for({"c1": real_owned("c1")}, stdout_detail="")
        d = mod.get_session_detail(run, "c1")
        self.assertIsNone(d)
        run2 = runner_for({"c1": real_owned("c1")}, stdout_detail="")
        self.assertTrue(mod.existing_gui_present(run2))

    def test_rc0_partial_identity_is_none_and_refuses(self):
        mod = load_supervisor()
        partial = "Id=c1\nUser=1001\nName=builder\n"
        run = runner_for({}, stdout_detail=partial)
        d = mod.get_session_detail(run, "c1")
        self.assertIsNone(d)
        run2 = runner_for({}, stdout_detail=partial)
        # list must show the session; inject listing with c1 present
        def run_list(cmd, timeout=None):
            c = list(cmd)
            if c[:2] == ["loginctl", "list-sessions"]:
                return SimpleNamespace(returncode=0, stdout="c1 1001 builder\n", stderr="")
            if c[:2] == ["loginctl", "show-session"]:
                return SimpleNamespace(returncode=0, stdout=partial, stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        self.assertTrue(mod.existing_gui_present(run_list))

    def test_id_mismatch_is_none(self):
        mod = load_supervisor()
        d_full = real_owned("c9")
        lines = "\n".join(k + "=" + v for k, v in d_full.items()) + "\n"
        run = runner_for({}, stdout_detail=lines)
        self.assertIsNone(mod.get_session_detail(run, "other"))

    def test_missing_each_required_is_none(self):
        mod = load_supervisor()
        for key in ("User", "Name", "Type", "Class", "State", "Remote"):
            d = real_owned("c9")
            del d[key]
            lines = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
            run = runner_for({}, stdout_detail=lines)
            self.assertIsNone(mod.get_session_detail(run, "c9"), msg=key)

    def test_valid_empty_listing_stays_valid(self):
        mod = load_supervisor()
        run = runner_for({})
        self.assertEqual(mod.list_sessions(run), set())
        self.assertFalse(mod.existing_gui_present(runner_for({})))


class Dt26FixRemote(unittest.TestCase):
    def test_missing_remote_rejected(self):
        mod = load_supervisor()
        d = real_owned("c9")
        del d["Remote"]
        self.assertFalse(mod.is_owned_session_detail(d, set()))
        # discovery layer also refuses: detail without Remote is None
        lines = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
        run = runner_for({}, stdout_detail=lines)
        self.assertIsNone(mod.get_session_detail(run, "c9"))

    def test_empty_remote_rejected(self):
        mod = load_supervisor()
        for empty in ("", "   "):
            d = real_owned("c9")
            d["Remote"] = empty
            self.assertFalse(mod.is_owned_session_detail(d, set()), msg=repr(empty))

    def test_explicit_no_false_accepted(self):
        mod = load_supervisor()
        for val in ("no", "false", "No", "FALSE"):
            d = real_owned("c9")
            d["Remote"] = val
            # get layer: nonempty Remote passes validation
            lines = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
            run = runner_for({}, stdout_detail=lines)
            self.assertIsNotNone(mod.get_session_detail(run, "c9"), msg=val)
            if val.strip().lower() in ("no", "false"):
                self.assertTrue(mod.is_owned_session_detail(d, set()), msg=val)

    def test_yes_remote_rejected(self):
        mod = load_supervisor()
        d = real_owned("c9")
        d["Remote"] = "yes"
        self.assertFalse(mod.is_owned_session_detail(d, set()))


class Dt26FixGenuineStillPasses(unittest.TestCase):
    def test_genuine_wayland_empty_display_passes(self):
        mod = load_supervisor()
        d = real_owned("7", display="")
        self.assertTrue(mod.is_owned_session_detail(d, set()))
        lines = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
        run = runner_for({}, stdout_detail=lines)
        got = mod.get_session_detail(run, "7")
        self.assertIsNotNone(got)
        self.assertEqual(got.get("User"), "1000")
        self.assertEqual(got.get("Name"), "live")

    def test_genuine_empty_seat_tty_still_valid_discovery(self):
        mod = load_supervisor()
        d = real_owned("7")
        d["Seat"] = ""
        d["TTY"] = ""
        d["Display"] = ""
        lines = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
        run = runner_for({}, stdout_detail=lines)
        self.assertIsNotNone(mod.get_session_detail(run, "7"))


class Dt26FixPreflightSnapshot(unittest.TestCase):
    def _full_runner(self, events, sessions, state):
        def run(cmd, timeout=None):
            c = list(cmd)
            events.append(list(c))
            if len(c) >= 2 and c[0] == "loginctl" and c[1] == "list-sessions":
                lines = "".join(s + "  1000 live\n" for s in sorted(sessions))
                return SimpleNamespace(returncode=0, stdout=lines, stderr="")
            if len(c) >= 3 and c[0] == "loginctl" and c[1] == "show-session":
                sid = str(c[2])
                if sid in sessions:
                    requested = [c[i + 1] for i, t in enumerate(c) if t == "-p" and i + 1 < len(c)]
                    d = sessions[sid]
                    out = [p + "=" + d[p] for p in requested if p in d]
                    return SimpleNamespace(returncode=0, stdout=("\n".join(out) + "\n" if out else ""), stderr="")
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
                return SimpleNamespace(returncode=0, stdout="ActiveState=" + st + "\nSubState=running\nResult=success\n", stderr="")
            if c[:2] == ["systemctl", "is-active"]:
                if "kestrel-graphics-sddm.service" in c:
                    return SimpleNamespace(returncode=0 if state["unit"] else 3,
                                            stdout="active\n" if state["unit"] else "inactive\n", stderr="")
                if "getty@tty2.service" in c:
                    return SimpleNamespace(returncode=0 if state["tty"] else 3,
                                            stdout="active\n" if state["tty"] else "inactive\n", stderr="")
                return SimpleNamespace(returncode=3, stdout="inactive\n", stderr="")
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

    def test_pass_snapshot_ordering_content(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26fix-pass-") as tmp:
            sd = Path(tmp)
            sessions = {}
            state = {"unit": False, "tty": False}
            start_seen = {}
            inner = self._full_runner([], sessions, state)

            def run(cmd, timeout=None):
                c = list(cmd)
                if c[:2] == ["systemctl", "start"] and "kestrel-graphics-sddm.service" in c:
                    pf = sd / "preflight.json"
                    start_seen["exists"] = pf.exists()
                    if pf.exists():
                        start_seen["payload"] = json.loads(pf.read_text())
                    start_seen["launch_exists"] = (sd / "launch-allowed").exists()
                return inner(cmd, timeout=timeout)

            class G:
                n = 0

                @staticmethod
                def collect_temperatures(root, required):
                    G.n += 1
                    if G.n == 3:
                        sessions["2"] = real_owned("2")
                    return [{"type": t, "temp_mc": 42000} for t in required]

                @staticmethod
                def evaluate_temperatures(rows, required, minimum_mc=5000, stop_mc=80000):
                    vals = {r["type"]: r["temp_mc"] for r in rows if r["type"] in set(required)}
                    return {"ok": True, "errors": [], "maximum_mc": 42000, "sensors": vals}

                @staticmethod
                def collect_drm(root, device_root, card="card0"):
                    return {"card": card, "driver": "simpledrm", "character_device": True,
                            "connectors": [{"status": "connected", "modes": ["1920x1200"]}]}

                @staticmethod
                def evaluate_drm(snap):
                    return {"ok": True, "errors": []}

            clock = FakeClock()
            rc = mod.run_bounded_session(thermal_root=sd, drm_root=sd, device_root=sd,
                                         card="card0", required={"cpu0-0-top-thermal"}, guard=G(),
                                         runner=run, status_dir=sd, timeout_s=6, poll_s=0.1,
                                         session_wait_s=3, start_wait_s=2,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 0)
            # ordering: preflight.json existed BEFORE private SDDM start.
            # (launch-allowed marker is created inside start_owned_gui after
            # the snapshot and before systemctl start, so it already exists
            # at start time; the load-bearing order is snapshot-before-start.)
            self.assertTrue(start_seen.get("exists"), "preflight.json missing at SDDM start")
            self.assertTrue(start_seen["payload"].get("passed") is True)
            # content: structured, actual thermal + DRM snapshot, native false
            pf = json.loads((sd / "preflight.json").read_text())
            self.assertTrue(pf.get("passed") is True)
            self.assertEqual(pf.get("reason"), "preflight-pass")
            self.assertIsInstance(pf.get("detail"), dict)
            self.assertIn("thermal", pf.get("detail"))
            self.assertIsNotNone(pf.get("thermal"))
            self.assertIsNotNone(pf.get("drm"))
            self.assertIsNotNone(pf.get("drm_snapshot"))
            self.assertTrue(pf.get("native_graphics_validated") is False)
            self.assertLessEqual(len(json.dumps(pf).encode("utf-8")), 64 * 1024)
            # no str(detail) truncation substitute at top level
            self.assertNotIsInstance(pf.get("detail"), str)

    def test_pass_persistence_failure_fails_closed_no_start(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26fix-persist-") as tmp:
            blocker = Path(tmp) / "status"
            blocker.write_text("file-blocks-dir\n")
            sessions = {}
            state = {"unit": False, "tty": False}
            events = []
            run = self._full_runner(events, sessions, state)
            clock = FakeClock()
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp),
                                         device_root=Path(tmp), card="card0",
                                         required={"cpu0-0-top-thermal"}, guard=mock_guard(),
                                         runner=run, status_dir=blocker, timeout_s=5,
                                         poll_s=0.1, session_wait_s=0.5,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            starts = [c for c in events if c[:2] == ["systemctl", "start"] and "kestrel-graphics-sddm.service" in c]
            self.assertEqual(starts, [])

    def test_fail_branch_is_structured_not_str(self):
        mod = load_supervisor()
        with tempfile.TemporaryDirectory(prefix="dt26fix-fail-") as tmp:
            sd = Path(tmp)
            sessions = {}
            state = {"unit": False, "tty": False}
            run = self._full_runner([], sessions, state)

            class GBad:
                @staticmethod
                def collect_temperatures(root, required):
                    return [{"type": t, "temp_mc": 42000} for t in required]

                @staticmethod
                def evaluate_temperatures(rows, required, minimum_mc=5000, stop_mc=80000):
                    return {"ok": False, "errors": ["mock_temp_fail"], "maximum_mc": None, "sensors": {}}

                @staticmethod
                def collect_drm(root, device_root, card="card0"):
                    return {"card": card, "driver": "simpledrm", "character_device": True,
                            "connectors": [{"status": "connected", "modes": ["1920x1200"]}]}

                @staticmethod
                def evaluate_drm(snap):
                    return {"ok": True, "errors": []}

            clock = FakeClock()
            rc = mod.run_bounded_session(thermal_root=sd, drm_root=sd, device_root=sd,
                                         card="card0", required={"cpu0-0-top-thermal"}, guard=GBad(),
                                         runner=run, status_dir=sd, timeout_s=5, poll_s=0.1,
                                         session_wait_s=0.5,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            pf = json.loads((sd / "preflight.json").read_text())
            self.assertTrue(pf.get("passed") is False)
            self.assertIsInstance(pf.get("detail"), dict)
            self.assertTrue(pf.get("native_graphics_validated") is False)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("__main__"))
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(getattr(result, "skipped", [])),
              "genuine_shaped_fixtures": True,
              "native_hardware_validated": False}
    print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
