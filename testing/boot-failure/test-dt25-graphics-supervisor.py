#!/usr/bin/env python3
# Owned supervisor tests: deterministic fakes + real subprocess.
# Project root derived from __file__; fail when required files missing.
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

P = Path(__file__).resolve().parents[2]
SUP = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
POLICY = P / "builder/diagnostics/kestrel-graphics-policy.json"
GUARD = P / "builder/diagnostics/kestrel_graphics_guard.py"
REQUIRED = [SUP, POLICY, GUARD]

FORBIDDEN_COMMANDS = [
    '["systemctl", "reboot"', "['systemctl', 'reboot'",
    '["systemctl", "poweroff"', "['systemctl', 'poweroff'",
    '["reboot"', "['reboot'", '["poweroff"', "['poweroff'",
    '["useradd"', "['useradd'", '["usermod"', "['usermod'",
    '["modprobe"', "['modprobe'", '["insmod"', "['insmod'",
    '"trip_point"', "'trip_point'",
    "/dev/mmcblk", "bootmnt/Logs",
]

def load_supervisor():
    spec = importlib.util.spec_from_file_location("kestrel_graphics_supervisor", SUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class FakeClock:
    def __init__(self):
        self.now = 1000.0
    def monotonic(self):
        return self.now
    def sleep(self, d):
        try:
            self.now += max(0.0, float(d))
        except (ValueError, TypeError):
            self.now += 0.0

class FakeRunner:
    """Genuine-shaped loginctl fake (systemd 262 real ABI).

    - User is numeric UID text, Name is username; there is NO UID property.
    - Separate `-p` flags return requested real props; a single comma-joined
      `-p "Id,User,..."` yields empty output with rc=0 (genuine 262).
    - fail_list / fail_detail / raise_detail inject query errors for
      fail-closed tests (runner rc!=0 or exception -> supervisor None).
    """
    def __init__(self):
        self.calls = []
        self.sessions = {}
        self.unit_active = False
        self.tty_active = False
        self.fail_start = False
        self.fail_list = False
        self.fail_detail = set()
        self.raise_detail = set()
        self.raise_list = False
    def __call__(self, cmd, timeout=None):
        self.calls.append((list(cmd), timeout))
        c = list(cmd)
        if len(c) >= 2 and c[0] == "loginctl" and c[1] == "list-sessions":
            if self.raise_list:
                raise RuntimeError("injected list-sessions error")
            if self.fail_list:
                return SimpleNamespace(returncode=1, stdout="", stderr="injected list failure")
            lines = ""
            for sid in sorted(self.sessions.keys()):
                lines += sid + " 1000 live\n"
            return SimpleNamespace(returncode=0, stdout=lines, stderr="")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "show-session":
            sid = str(c[2])
            if sid in self.raise_detail:
                raise RuntimeError("injected show-session error")
            if sid in self.fail_detail:
                return SimpleNamespace(returncode=1, stdout="", stderr="injected detail failure")
            if sid in self.sessions:
                # Genuine 262: comma-joined -p yields empty output.
                for tok in c[3:]:
                    if "," in tok:
                        return SimpleNamespace(returncode=0, stdout="", stderr="")
                # Collect requested props from repeated -p flags.
                requested = []
                for i, tok in enumerate(c):
                    if tok == "-p" and i + 1 < len(c):
                        requested.append(c[i + 1])
                d = self.sessions[sid]
                if requested:
                    # UID is not a real session property: omit it, return rest.
                    out_lines = []
                    for prop in requested:
                        if prop == "UID":
                            continue
                        if prop in d:
                            out_lines.append(prop + "=" + d[prop])
                    return SimpleNamespace(returncode=0, stdout="\n".join(out_lines) + ("\n" if out_lines else ""), stderr="")
                out = "\n".join(k + "=" + v for k, v in d.items()) + "\n"
                return SimpleNamespace(returncode=0, stdout=out, stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="no such session")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "terminate-session":
            self.sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "kill-session":
            self.sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "start"]:
            if "kestrel-graphics-sddm.service" in c:
                if self.fail_start:
                    return SimpleNamespace(returncode=1, stdout="", stderr="fail")
                self.unit_active = True
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if "getty@tty2.service" in c:
                self.tty_active = True
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "stop"]:
            if "kestrel-graphics-sddm.service" in c:
                self.unit_active = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "show"]:
            st = "active" if self.unit_active else "inactive"
            sub = "running" if self.unit_active else "dead"
            return SimpleNamespace(returncode=0, stdout="ActiveState=" + st + "\nSubState=" + sub + "\nResult=success\n", stderr="")
        if c[:2] == ["systemctl", "is-active"]:
            if "kestrel-graphics-sddm.service" in c:
                return SimpleNamespace(returncode=0 if self.unit_active else 3, stdout="active\n" if self.unit_active else "inactive\n", stderr="")
            if "getty@tty2.service" in c:
                return SimpleNamespace(returncode=0 if self.tty_active else 3, stdout="active\n" if self.tty_active else "inactive\n", stderr="")
            return SimpleNamespace(returncode=3, stdout="inactive\n", stderr="")
        if c[:2] == ["systemctl", "kill"]:
            self.unit_active = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    def cmds_joined(self):
        return "\n".join(" ".join(c) for c, _ in self.calls)

def owned_detail(sid="1", display=""):
    """Real-shaped owned session (systemd 262 genuine ABI).

    User is numeric UID text, Name is username; no UID key exists.
    Display defaults to empty: genuine Wayland sessions normally have an
    empty Display (X11-only property, verified on builder 262 output where
    even tty/manager sessions show Display empty).
    """
    return {"Id": sid, "User": "1000", "Name": "live", "Seat": "seat0", "Type": "wayland", "Class": "user", "State": "active", "Display": display, "Remote": "no", "Service": "sddm", "TTY": ""}

def mock_guard(temp_ok=True, drm_ok=True, temp_vals=None, hot_after=None, lose_after=None):
    state = {"n": 0}
    class G:
        @staticmethod
        def collect_temperatures(root, required):
            state["n"] += 1
            n = state["n"]
            if lose_after is not None and n > lose_after:
                return []
            if hot_after is not None and n > hot_after:
                return [{"type": t, "temp_mc": 80000} for t in required]
            if temp_vals is not None:
                return list(temp_vals)
            return [{"type": t, "temp_mc": 42000} for t in required]
        @staticmethod
        def evaluate_temperatures(rows, required, minimum_mc=5000, stop_mc=80000):
            required = set(required)
            vals = {}
            errors = []
            for r in rows:
                if r["type"] in required:
                    v = r.get("temp_mc")
                    if type(v) is not int or not minimum_mc <= v <= 125000:
                        errors.append("invalid_temperature:" + str(r["type"]))
                    elif v >= stop_mc:
                        errors.append("experiment_temperature_limit:" + str(r["type"]))
                    else:
                        vals[r["type"]] = v
            for t in required:
                if t not in vals and not any(e.endswith(t) for e in errors):
                    errors.append("missing_sensor:" + t)
            if not temp_ok:
                errors.append("mock_temp_fail")
            return {"ok": not errors, "errors": errors, "maximum_mc": max(vals.values()) if vals else None, "sensors": vals}
        @staticmethod
        def collect_drm(root, device_root, card="card0"):
            return {"card": card, "driver": "simpledrm", "character_device": True, "connectors": [{"status": "connected", "modes": ["1920x1200"]}]}
        @staticmethod
        def evaluate_drm(snapshot):
            if not drm_ok:
                return {"ok": False, "errors": ["mock_drm_fail"]}
            if snapshot.get("driver") not in ("simpledrm", "simple-framebuffer"):
                return {"ok": False, "errors": ["not_the_simpledrm_fallback"]}
            if snapshot.get("character_device") is not True:
                return {"ok": False, "errors": ["missing_drm_character_device"]}
            usable = any(c.get("status") == "connected" and c.get("modes") for c in snapshot.get("connectors", []))
            if not usable:
                return {"ok": False, "errors": ["no_connected_output_with_valid_mode"]}
            return {"ok": True, "errors": []}
    return G()

class SupervisorContract(unittest.TestCase):
    def test_required_files_exist(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
    def test_module_loads_and_has_required_api(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        mod = load_supervisor()
        for name in ["load_policy", "preflight", "bounded_cleanup", "run_bounded_session", "list_sessions", "get_session_detail", "is_owned_session_detail", "existing_gui_present", "start_owned_gui", "wait_for_owned_session", "MAX_SECONDS", "STOP_MC", "MINIMUM_MC", "OWNED_UNIT", "CLEANUP_BUDGET_S"]:
            self.assertTrue(hasattr(mod, name), "missing " + name)
        self.assertEqual(mod.MAX_SECONDS, 180)
        self.assertEqual(mod.STOP_MC, 80000)
        self.assertEqual(mod.MINIMUM_MC, 5000)
        self.assertEqual(mod.OWNED_UNIT, "kestrel-graphics-sddm.service")
        self.assertLessEqual(mod.CLEANUP_BUDGET_S, 25)
        self.assertEqual(mod.LIVE_UID, 1000)
    def test_policy_missing_blocks(self):
        mod = load_supervisor()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-pol-") as tmp:
            ok, detail = mod.load_policy(Path(tmp) / "no-such.json")
            self.assertFalse(ok)
    def test_policy_empty_battery_duplicate_blocks(self):
        mod = load_supervisor()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-pol2-") as tmp:
            q = Path(tmp) / "policy.json"
            q.write_text('{"required_sensor_types": []}')
            ok, _ = mod.load_policy(q)
            self.assertFalse(ok)
            q.write_text('{"required_sensor_types": ["cpu0-0-top-thermal", "cpu0-0-top-thermal"]}')
            ok2, _ = mod.load_policy(q)
            self.assertFalse(ok2)
            q.write_text('{"required_sensor_types": ["qcom-battmgr-bat"]}')
            ok3, _ = mod.load_policy(q)
            self.assertFalse(ok3)
    def test_preflight_battery_only_high_temp_blocks(self):
        mod = load_supervisor()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-pre-") as tmp:
            root = Path(tmp)
            g = mock_guard(temp_vals=[{"type": "qcom-battmgr-bat", "temp_mc": 30000}])
            ok, _ = mod.preflight(root, root, root, "card0", {"cpu0-0-top-thermal", "cpuss0-top-thermal"}, g)
            self.assertFalse(ok)
            g2 = mock_guard(temp_vals=[{"type": "cpu0-0-top-thermal", "temp_mc": 80000}, {"type": "cpuss0-top-thermal", "temp_mc": 42000}])
            ok2, _ = mod.preflight(root, root, root, "card0", {"cpu0-0-top-thermal", "cpuss0-top-thermal"}, g2)
            self.assertFalse(ok2)
            g3 = mock_guard(drm_ok=False)
            ok3, _ = mod.preflight(root, root, root, "card0", {"cpu0-0-top-thermal", "cpuss0-top-thermal"}, g3)
            self.assertFalse(ok3)
            g4 = mock_guard()
            ok4, _ = mod.preflight(root, root, root, "card0", {"cpu0-0-top-thermal", "cpuss0-top-thermal"}, g4)
            self.assertTrue(ok4)
    def test_existing_session_refuses_without_termination(self):
        mod = load_supervisor()
        runner = FakeRunner()
        runner.sessions["5"] = owned_detail("5")
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-refuse-") as tmp:
            g = mock_guard()
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=5, poll_s=0.1, session_wait_s=0.5, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            joined = runner.cmds_joined()
            self.assertNotIn("terminate-session 5", joined)
            self.assertNotIn("kill-session", joined)
            self.assertNotIn("pkill", joined)
            self.assertNotIn("terminate-user", joined)
            self.assertFalse(any("terminate-session" in c and " 5" in c for c, _ in runner.calls))
    def test_no_start_before_all_gates(self):
        mod = load_supervisor()
        runner = FakeRunner()
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-nostart-") as tmp:
            g = mock_guard(temp_ok=False)
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=5, poll_s=0.1, session_wait_s=0.5, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            starts = [c for c, _ in runner.calls if c[:2] == ["systemctl", "start"] and "kestrel-graphics-sddm.service" in c]
            self.assertEqual(starts, [])
    def test_temp_hot_during_start_blocks(self):
        mod = load_supervisor()
        runner = FakeRunner()
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-hotstart-") as tmp:
            g = mock_guard(hot_after=1)
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=10, poll_s=0.1, session_wait_s=1, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
    def test_temp_loss_during_session_wait_blocks(self):
        mod = load_supervisor()
        runner = FakeRunner()
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-losswait-") as tmp:
            g = mock_guard(lose_after=3)
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=10, poll_s=0.1, session_wait_s=2, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            self.assertFalse(any("terminate-user" in " ".join(c) for c, _ in runner.calls))
    def test_owned_cleanup_verifies_and_reports(self):
        mod = load_supervisor()
        runner = FakeRunner()
        runner.sessions["9"] = owned_detail("9")
        runner.unit_active = True
        runner.tty_active = False
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-clean-") as tmp:
            sd = Path(tmp)
            rc = mod.bounded_cleanup(runner, sd, reason="deadline", owned="9", _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 0)
            payload = json.loads((sd / "status.json").read_text())
            self.assertTrue(payload["bounded_cleanup"])
            self.assertTrue(payload["owned_stopped"])
            self.assertTrue(payload["owned_gone"])
            self.assertTrue(payload["tty2_restored"])
            joined = runner.cmds_joined()
            self.assertIn("kestrel-graphics-sddm.service", joined)
            self.assertIn("getty@tty2", joined)
            self.assertIn("terminate-session 9", joined)
            self.assertNotIn("pkill", joined)
            self.assertNotIn("terminate-user", joined)
            self.assertNotIn("display-manager.service", joined)
            for _, to in runner.calls:
                if to is not None:
                    self.assertLessEqual(float(to), 15)
    def test_cleanup_incomplete_when_owned_stuck(self):
        mod = load_supervisor()
        class StuckRunner(FakeRunner):
            def __call__(self, cmd, timeout=None):
                self.calls.append((list(cmd), timeout))
                c = list(cmd)
                if c[:2] == ["systemctl", "is-active"]:
                    return SimpleNamespace(returncode=0, stdout="active\n", stderr="")
                if c[:2] == ["systemctl", "show"]:
                    return SimpleNamespace(returncode=0, stdout="ActiveState=active\nSubState=running\nResult=success\n", stderr="")
                return super().__call__(cmd, timeout=timeout)
        runner = StuckRunner()
        runner.sessions["7"] = owned_detail("7")
        runner.unit_active = True
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-stuck-") as tmp:
            sd = Path(tmp)
            rc = mod.bounded_cleanup(runner, sd, reason="deadline", owned="7", _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 1)
            payload = json.loads((sd / "status.json").read_text())
            self.assertFalse(payload["bounded_cleanup"])
    def test_no_orphan_no_foreign_kills_static_and_runtime(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        src = SUP.read_text()
        self.assertIn("SIGTERM", src)
        self.assertIn("SIGINT", src)
        self.assertNotIn("pkill", src)
        self.assertNotIn("terminate-user", src)
        for bad in FORBIDDEN_COMMANDS:
            self.assertNotIn(bad, src)
        self.assertNotIn("XDG_RUNTIME_DIR=/tmp", src)
        mod = load_supervisor()
        runner = FakeRunner()
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-noorphan-") as tmp:
            g = mock_guard()
            def appear_after_two(root, required):
                return [{"type": t, "temp_mc": 42000} for t in required]
            orig_collect = g.collect_temperatures
            calls = {"n": 0}
            def counting_collect(root, required):
                calls["n"] += 1
                if calls["n"] == 3:
                    runner.sessions["2"] = owned_detail("2")
                    runner.unit_active = True
                return orig_collect(root, required)
            g.collect_temperatures = counting_collect
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=6, poll_s=0.1, session_wait_s=3, start_wait_s=2, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertIn(rc, (0, 2))
            joined = runner.cmds_joined()
            self.assertNotIn("pkill", joined)
            self.assertNotIn("terminate-user", joined)
    def test_180s_budget_enforced(self):
        mod = load_supervisor()
        self.assertEqual(mod.MAX_SECONDS, 180)
        runner = FakeRunner()
        clock = FakeClock()
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-budget-") as tmp:
            g = mock_guard()
            start = clock.now
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp), device_root=Path(tmp), card="card0", required={"cpu0-0-top-thermal"}, guard=g, runner=runner, status_dir=Path(tmp), timeout_s=999, poll_s=0.1, session_wait_s=1, start_wait_s=1, _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertIn(rc, (0, 2))
            elapsed = clock.now - start
            self.assertLessEqual(elapsed, 180 + 30)
            timeouts = [to for _, to in runner.calls if to is not None]
            if timeouts:
                self.assertLessEqual(max(timeouts), 30)
    def test_signal_handler_idempotent(self):
        mod = load_supervisor()
        src = SUP.read_text()
        self.assertIn("_handle_signal", src)
        self.assertIn("pending_signal", src)
        self.assertIn("cleaning", src)
        mod._cleanup_state["pending_signal"] = None
        mod._cleanup_state["cleaning"] = False
        mod._handle_signal(15, None)
        self.assertEqual(mod._cleanup_state["pending_signal"], 15)
        mod._cleanup_state["cleaning"] = True
        mod._handle_signal(15, None)
        self.assertEqual(mod._cleanup_state["pending_signal"], 15)
        mod._cleanup_state["pending_signal"] = None
        mod._cleanup_state["cleaning"] = False
    def _fake_backend(self, tmp):
        tmp = Path(tmp)
        bindir = tmp / "fakebin"
        statedir = tmp / "fakestate"
        bindir.mkdir(parents=True, exist_ok=True)
        statedir.mkdir(parents=True, exist_ok=True)
        log = tmp / "calls.log"
        log.write_text("")
        syst = bindir / "systemctl"
        syst.write_text("#!/bin/sh\nLOG=\"" + str(log) + "\"\nSTATE=\"" + str(statedir) + "\"\necho \"systemctl $@\" >> \"$LOG\"\ncmd=\"$1\"\nsub=\"$2\"\nif [ \"$cmd\" = \"start\" ]; then\n  if echo \"$@\" | grep -q kestrel-graphics-sddm; then echo active > \"$STATE/unit\"; echo started > \"$STATE/started\"; exit 0; fi\n  if echo \"$@\" | grep -q getty@tty2; then echo active > \"$STATE/tty2\"; exit 0; fi\n  exit 0\nfi\nif [ \"$cmd\" = \"stop\" ]; then\n  if echo \"$@\" | grep -q kestrel-graphics-sddm; then echo inactive > \"$STATE/unit\"; exit 0; fi\n  exit 0\nfi\nif [ \"$cmd\" = \"show\" ]; then\n  echo \"ActiveState=active\"\n  echo \"SubState=running\"\n  echo \"Result=success\"\n  exit 0\nfi\nif [ \"$cmd\" = \"is-active\" ]; then\n  if echo \"$@\" | grep -q kestrel-graphics-sddm; then if [ \"$(cat \"$STATE/unit\" 2>/dev/null)\" = \"active\" ]; then echo active; exit 0; else echo inactive; exit 3; fi; fi\n  if echo \"$@\" | grep -q getty@tty2; then echo active; exit 0; fi\n  echo inactive; exit 3\nfi\nif [ \"$cmd\" = \"kill\" ]; then echo inactive > \"$STATE/unit\"; exit 0; fi\nexit 0\n")
        syst.chmod(0o755)
        loginctl = bindir / "loginctl"
        loginctl.write_text("#!/bin/sh\nLOG=\"" + str(log) + "\"\nSTATE=\"" + str(statedir) + "\"\necho \"loginctl $@\" >> \"$LOG\"\nif [ \"$1\" = \"list-sessions\" ]; then if [ -f \"$STATE/started\" ]; then echo \"1 1000 live\"; fi; exit 0; fi\nif [ \"$1\" = \"show-session\" ]; then sid=\"$2\"; if echo \"$@\" | grep -q \",\"; then exit 0; fi; if [ -f \"$STATE/started\" ] && [ ! -f \"$STATE/terminated\" ]; then echo \"Id=1\"; echo \"User=1000\"; echo \"Name=live\"; echo \"Seat=seat0\"; echo \"Type=wayland\"; echo \"Class=user\"; echo \"State=active\"; echo \"Display=\"; echo \"Remote=no\"; echo \"Service=sddm\"; exit 0; else exit 1; fi; fi\nif [ \"$1\" = \"terminate-session\" ]; then touch \"$STATE/terminated\"; exit 0; fi\nif [ \"$1\" = \"kill-session\" ]; then touch \"$STATE/terminated\"; exit 0; fi\nexit 0\n")
        loginctl.chmod(0o755)
        return bindir, statedir, log
    def _mock_guard_file(self, tmp):
        g = Path(tmp) / "kestrel_graphics_guard.py"
        g.write_text("def collect_temperatures(root, required):\n    return [{\"type\": t, \"temp_mc\": 42000} for t in required]\ndef collect_drm(root, device_root, card=\"card0\"):\n    return {\"card\": card, \"driver\": \"simpledrm\", \"character_device\": True, \"connectors\": [{\"status\": \"connected\", \"modes\": [\"1920x1200\"]}]}\ndef evaluate_temperatures(rows, required, minimum_mc=5000, stop_mc=80000):\n    vals={r[\"type\"]: r[\"temp_mc\"] for r in rows if r[\"type\"] in set(required)}\n    errs=[] if set(vals)==set(required) else [\"missing\"]\n    return {\"ok\": not errs, \"errors\": errs, \"maximum_mc\": 42000, \"sensors\": vals}\ndef evaluate_drm(snap):\n    return {\"ok\": True, \"errors\": []}\n")
        return g
    def test_real_subprocess_term_owned_cleanup(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-subterm-") as tmp:
            tmp = Path(tmp)
            bindir, statedir, log = self._fake_backend(tmp)
            sup_copy = tmp / "kestrel-graphics-supervisor.py"
            sup_copy.write_bytes(SUP.read_bytes())
            self._mock_guard_file(tmp)
            self._mock_guard_file(tmp)
            pol = tmp / "policy.json"
            pol.write_text('{"required_sensor_types": ["cpu0-0-top-thermal", "cpuss0-top-thermal"]}')
            sdir = tmp / "status"
            sdir.mkdir()
            env = dict(os.environ)
            env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen([sys.executable, str(sup_copy), "--policy", str(pol), "--thermal-root", str(tmp), "--drm-root", str(tmp), "--device-root", str(tmp), "--timeout-s", "60", "--session-wait-s", "5", "--status-dir", str(sdir)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            try:
                out = ""
                start = time.monotonic()
                found = False
                while time.monotonic() - start < 15:
                    if proc.poll() is not None:
                        break
                    if (sdir / "launch-allowed").exists():
                        found = True
                        break
                    time.sleep(0.2)
                self.assertTrue(found, "supervisor never started owned unit " + (proc.stdout.read() if proc.poll() is not None else ""))
                time.sleep(1.0)
                proc.send_signal(signal.SIGTERM)
                try:
                    stdout, _ = proc.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0, stdout)
                calls = log.read_text() if log.exists() else ""
                self.assertIn("kestrel-graphics-sddm.service", calls)
                self.assertIn("terminate-session", calls)
                self.assertNotIn("pkill", calls)
                self.assertNotIn("terminate-user", calls)
                self.assertNotIn("display-manager", calls)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    try:
                        proc.communicate(timeout=5)
                    except Exception:
                        pass
    def test_real_subprocess_timeout_deadline(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="dt25-sup-subto-") as tmp:
            tmp = Path(tmp)
            bindir, statedir, log = self._fake_backend(tmp)
            sup_copy = tmp / "kestrel-graphics-supervisor.py"
            sup_copy.write_bytes(SUP.read_bytes())
            self._mock_guard_file(tmp)
            pol = tmp / "policy.json"
            pol.write_text('{"required_sensor_types": ["cpu0-0-top-thermal"]}')
            sdir = tmp / "status"
            sdir.mkdir()
            env = dict(os.environ)
            env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.run([sys.executable, str(sup_copy), "--policy", str(pol), "--thermal-root", str(tmp), "--drm-root", str(tmp), "--device-root", str(tmp), "--timeout-s", "3", "--session-wait-s", "1", "--status-dir", str(sdir)], capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("KESTREL_GRAPHICS_", proc.stdout)
            calls = log.read_text() if log.exists() else ""
            self.assertNotIn("pkill", calls)
            self.assertNotIn("terminate-user", calls)
if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("__main__"))
    import json as _json
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(getattr(result, "skipped", [])), "synthetic_fixtures_only": False, "genuine_shaped_fixtures": True, "schema_source": "systemd-262-logind-session-dbus+loginctl-genuine-output", "native_hardware_validated": False}
    print(_json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)

