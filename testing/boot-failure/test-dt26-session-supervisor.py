#!/usr/bin/env python3
# dt26 session-schema + fail-closed regressions for the guarded graphics supervisor.
# Independently sourced from genuine systemd 262 primary source + genuine
# `loginctl show-session` output on builder (systemd 262-1-arch):
#   User=<numeric UID> (loginctl.c prints (uo) struct as UID_FMT),
#   Name=<username> (logind-session-dbus.c property_get_name),
#   NO UID session property (requesting -p UID yields empty),
#   separate `-p` flags required (comma-joined -p yields empty, rc=0),
#   Display empty is normal for Wayland/tty/manager (X11-only property).
# Portable fakes only; no hardware, no QEMU, no system changes.
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

P = Path(__file__).resolve().parents[2]
SUP = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
REQUIRED = [SUP]


def load_supervisor():
    spec = importlib.util.spec_from_file_location("kestrel_graphics_supervisor_dt26", SUP)
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


class GenuineRunner:
    """Genuine-262-shaped fake: numeric User, string Name, no UID prop.

    Comma-joined -p yields empty (real 262 behavior). Separate -p returns
    requested real props, omitting UID. fail_* inject query errors.
    """

    def __init__(self):
        self.calls = []
        self.sessions = {}
        self.unit_active = False
        self.tty_active = False
        self.fail_list = False
        self.fail_detail = set()
        self.raise_list = False
        self.raise_detail = set()

    def __call__(self, cmd, timeout=None):
        self.calls.append((list(cmd), timeout))
        c = list(cmd)
        if len(c) >= 2 and c[0] == "loginctl" and c[1] == "list-sessions":
            if self.raise_list:
                raise RuntimeError("injected list error")
            if self.fail_list:
                return SimpleNamespace(returncode=1, stdout="", stderr="fail")
            lines = "".join(s + " 1000 live\n" for s in sorted(self.sessions))
            return SimpleNamespace(returncode=0, stdout=lines, stderr="")
        if len(c) >= 3 and c[0] == "loginctl" and c[1] == "show-session":
            sid = str(c[2])
            if sid in self.raise_detail:
                raise RuntimeError("injected detail error")
            if sid in self.fail_detail:
                return SimpleNamespace(returncode=1, stdout="", stderr="fail")
            if sid in self.sessions:
                for tok in c[3:]:
                    if "," in tok:
                        return SimpleNamespace(returncode=0, stdout="", stderr="")
                requested = [c[i + 1] for i, t in enumerate(c) if t == "-p" and i + 1 < len(c)]
                d = self.sessions[sid]
                if requested:
                    lines = [p + "=" + d[p] for p in requested if p in d and p != "UID"]
                    return SimpleNamespace(returncode=0, stdout=("\n".join(lines) + "\n" if lines else ""), stderr="")
                return SimpleNamespace(returncode=0, stdout="\n".join(k + "=" + v for k, v in d.items()) + "\n", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="no such session")
        if c[:2] == ["systemctl", "start"]:
            if "kestrel-graphics-sddm.service" in c:
                self.unit_active = True
            if "getty@tty2.service" in c:
                self.tty_active = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "stop"]:
            if "kestrel-graphics-sddm.service" in c:
                self.unit_active = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["systemctl", "show"]:
            st = "active" if self.unit_active else "inactive"
            return SimpleNamespace(returncode=0, stdout="ActiveState=" + st + "\nSubState=running\nResult=success\n", stderr="")
        if c[:2] == ["systemctl", "is-active"]:
            if "kestrel-graphics-sddm.service" in c:
                return SimpleNamespace(returncode=0 if self.unit_active else 3, stdout="active\n" if self.unit_active else "inactive\n", stderr="")
            if "getty@tty2.service" in c:
                return SimpleNamespace(returncode=0 if self.tty_active else 3, stdout="active\n" if self.tty_active else "inactive\n", stderr="")
            return SimpleNamespace(returncode=3, stdout="inactive\n", stderr="")
        if c[:2] == ["systemctl", "kill"]:
            self.unit_active = False
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["loginctl", "terminate-session"]:
            self.sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if c[:2] == ["loginctl", "kill-session"]:
            self.sessions.pop(str(c[2]), None)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def joined(self):
        return "\n".join(" ".join(c) for c, _ in self.calls)


def real_owned(sid="7", display=""):
    # Genuine Wayland SDDM shape: numeric User, Name live, empty Display.
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


class Dt26SessionSchema(unittest.TestCase):
    def test_module_present(self):
        self.assertTrue(SUP.is_file())

    def test_uses_repeated_p_requests_name_not_uid(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.sessions["7"] = real_owned("7")
        d = mod.get_session_detail(r, "7")
        self.assertIsNotNone(d)
        self.assertEqual(d.get("User"), "1000")
        self.assertEqual(d.get("Name"), "live")
        # Supervisor must request Name and must not request UID.
        flat = " ".join(" ".join(c) for c, _ in r.calls if c[:2] == ["loginctl", "show-session"])
        self.assertIn("Name", flat)
        self.assertNotIn("UID", flat)
        self.assertNotIn(",", flat)

    def test_comma_p_yields_empty_on_genuine_shape(self):
        # Documents the real-262 pitfall the old code hit: single
        # comma-joined -p returns empty even though the session exists.
        r = GenuineRunner()
        r.sessions["7"] = real_owned("7")
        out = r(["loginctl", "show-session", "7", "-p", "Id,User,UID,Seat,Type,Class,State,Display,Remote,Service,TTY"], timeout=5)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_real_wayland_empty_display_accepted(self):
        # RED on old code (required nonempty Display): genuine Wayland with
        # empty Display must be accepted as owned.
        mod = load_supervisor()
        self.assertTrue(mod.is_owned_session_detail(real_owned("7", display=""), set()))

    def test_old_synthetic_abi_rejected(self):
        # Old fake ABI (User=live string, UID key, Display=:0, no Name)
        # must NOT be accepted as owned under the real schema.
        mod = load_supervisor()
        synthetic = {"Id": "7", "User": "live", "UID": "1000", "Seat": "seat0",
                     "Type": "wayland", "Class": "user", "State": "active",
                     "Display": ":0", "Remote": "no", "Service": "sddm", "TTY": ""}
        self.assertFalse(mod.is_owned_session_detail(synthetic, set()))

    def test_missing_name_rejected(self):
        mod = load_supervisor()
        d = real_owned("7")
        del d["Name"]
        self.assertFalse(mod.is_owned_session_detail(d, set()))

    def test_numeric_user_mismatch_rejected(self):
        mod = load_supervisor()
        d = real_owned("7")
        d["User"] = "1001"
        self.assertFalse(mod.is_owned_session_detail(d, set()))
        d2 = real_owned("7")
        d2["Name"] = "builder"
        self.assertFalse(mod.is_owned_session_detail(d2, set()))

    def test_baseline_member_never_owned(self):
        mod = load_supervisor()
        self.assertFalse(mod.is_owned_session_detail(real_owned("7"), {"7"}))

    def test_remote_and_seat_and_service_guarded(self):
        mod = load_supervisor()
        d = real_owned("7")
        d["Remote"] = "yes"
        self.assertFalse(mod.is_owned_session_detail(d, set()))
        d2 = real_owned("7")
        d2["Seat"] = "seat1"
        self.assertFalse(mod.is_owned_session_detail(d2, set()))
        d3 = real_owned("7")
        d3["Service"] = "gdm"
        self.assertFalse(mod.is_owned_session_detail(d3, set()))
        d4 = real_owned("7")
        d4["Type"] = "x11"
        self.assertFalse(mod.is_owned_session_detail(d4, set()))


class Dt26FailClosed(unittest.TestCase):
    def test_list_error_is_none(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.fail_list = True
        self.assertIsNone(mod.list_sessions(r))

    def test_detail_error_is_none(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.sessions["9"] = real_owned("9")
        r.fail_detail.add("9")
        self.assertIsNone(mod.get_session_detail(r, "9"))

    def test_unknown_listing_refuses_existing_check(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.fail_list = True
        self.assertTrue(mod.existing_gui_present(r))

    def test_unknown_detail_refuses_existing_check(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.sessions["9"] = real_owned("9")
        r.fail_detail.add("9")
        self.assertTrue(mod.existing_gui_present(r))

    def test_unknown_baseline_refuses_no_start(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.fail_list = True
        clock = FakeClock()
        with tempfile.TemporaryDirectory(prefix="dt26-base-") as tmp:
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp),
                                         device_root=Path(tmp), card="card0",
                                         required={"cpu0-0-top-thermal"}, guard=mock_guard(),
                                         runner=r, status_dir=Path(tmp), timeout_s=5,
                                         poll_s=0.1, session_wait_s=0.5,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            starts = [c for c, _ in r.calls if c[:2] == ["systemctl", "start"] and "kestrel-graphics-sddm.service" in c]
            self.assertEqual(starts, [])
            joined = r.joined()
            self.assertNotIn("terminate-session 9", joined)

    def test_unknown_detail_before_start_refuses_no_termination(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.sessions["5"] = real_owned("5")
        r.fail_detail.add("5")
        clock = FakeClock()
        with tempfile.TemporaryDirectory(prefix="dt26-refuse-") as tmp:
            rc = mod.run_bounded_session(thermal_root=Path(tmp), drm_root=Path(tmp),
                                         device_root=Path(tmp), card="card0",
                                         required={"cpu0-0-top-thermal"}, guard=mock_guard(),
                                         runner=r, status_dir=Path(tmp), timeout_s=5,
                                         poll_s=0.1, session_wait_s=0.5,
                                         _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertEqual(rc, 2)
            joined = r.joined()
            self.assertNotIn("terminate-session 5", joined)
            self.assertNotIn("kill-session", joined)

    def test_unknown_new_detail_during_wait_returns_none(self):
        mod = load_supervisor()
        r = GenuineRunner()
        r.sessions["8"] = real_owned("8")
        r.fail_detail.add("8")
        clock = FakeClock()
        with tempfile.TemporaryDirectory(prefix="dt26-wait-") as tmp:
            sid = mod.wait_for_owned_session(runner=r, baseline=set(),
                                             thermal_root=Path(tmp), drm_root=Path(tmp),
                                             device_root=Path(tmp), card="card0",
                                             required={"cpu0-0-top-thermal"}, guard=mock_guard(),
                                             overall_deadline=clock.now + 5, timeout_s=1,
                                             _monotonic=clock.monotonic, _sleep=clock.sleep)
            self.assertIsNone(sid)


class Dt26ContractPreserved(unittest.TestCase):
    def test_budgets_and_limits(self):
        mod = load_supervisor()
        self.assertEqual(mod.MAX_SECONDS, 180)
        self.assertLessEqual(mod.CLEANUP_BUDGET_S, 25)
        self.assertEqual(mod.STOP_MC, 80000)
        self.assertEqual(mod.MINIMUM_MC, 5000)
        self.assertEqual(mod.OWNED_UNIT, "kestrel-graphics-sddm.service")
        self.assertEqual(mod.LIVE_UID, 1000)

    def test_no_broad_kills_no_vt_switch(self):
        src = SUP.read_text()
        for bad in ("pkill", "terminate-user", "useradd", "usermod", "modprobe",
                    "/dev/mmcblk"):
            self.assertNotIn(bad, src)
        # No chvt/fgconsole VT-switch invocation: mentions in comments that
        # explicitly document NOT using them are allowed; only a real call
        # (list element or executable path) is forbidden.
        for bad_call in ('"chvt"', "'chvt'", '["chvt"', "['chvt'", "/usr/bin/chvt",
                         "/sbin/chvt", '"fgconsole"', "'fgconsole'",
                         '["fgconsole"', "['fgconsole'"):
            self.assertNotIn(bad_call, src)
        self.assertIn("SIGTERM", src)
        self.assertIn("SIGINT", src)
        # Documents why no VT switch was added (live-image kbd/chvt unverified).
        self.assertIn("chvt", src.lower())

    def test_no_pixel_or_vt_overclaim(self):
        src = SUP.read_text()
        self.assertIn("native_graphics_validated", src)
        self.assertIn("session_active_is_not_pixel_proof", src)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("__main__"))
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(getattr(result, "skipped", [])),
              "genuine_shaped_fixtures": True,
              "schema_source": "systemd-262-logind-session-dbus+loginctl-genuine-output",
              "native_hardware_validated": False}
    print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
