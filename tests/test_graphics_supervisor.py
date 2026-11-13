# SPDX-License-Identifier: GPL-2.0-or-later
"""Unit tests for the opt-in unbounded monitoring of builder/diagnostics/kestrel-graphics-supervisor.py.

The supervisor's system calls are replaced by fakes and time is simulated, so nothing touches a display or the system.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "builder" / "diagnostics" / "kestrel-graphics-supervisor.py"
spec = importlib.util.spec_from_file_location("kestrel_graphics_supervisor", SRC)
sup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sup)


class Clock:
    def __init__(self):
        self.t = 0.0

    def mono(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(unbounded, hot_after=None, lose_session_after=None, limit_s=3600):
    """Run the monitor loop on a fake clock; returns (rc, simulated seconds, cleanup reasons)."""
    clock = Clock()
    reasons = []
    saved = {k: getattr(sup, k) for k in ("list_sessions", "existing_gui_present", "preflight", "_save_preflight_result",
                                         "start_owned_gui", "wait_for_owned_session", "get_session_detail",
                                         "is_owned_session_detail", "bounded_cleanup", "_log")}

    def preflight(*a, **k):
        if hot_after is not None and clock.t >= hot_after:
            return False, {"thermal": {"ok": False}}
        return True, {"thermal": {"ok": True}, "drm": {"ok": True}, "drm_snapshot": {}}

    def detail(runner, sid, timeout=0):
        if lose_session_after is not None and clock.t >= lose_session_after:
            return None
        return {"Id": sid}

    def cleanup(runner, status_dir, reason="", **k):
        reasons.append(reason)

    def sleep(s):
        clock.sleep(s)
        if clock.t > limit_s:
            raise AssertionError("monitor still running after %d simulated seconds" % limit_s)

    try:
        sup.list_sessions = lambda runner: []
        sup.existing_gui_present = lambda runner: False
        sup.preflight = preflight
        sup._save_preflight_result = lambda *a, **k: True
        sup.start_owned_gui = lambda **k: (True, "")
        sup.wait_for_owned_session = lambda **k: "1"
        sup.get_session_detail = detail
        sup.is_owned_session_detail = lambda d, baseline: True
        sup.bounded_cleanup = cleanup
        sup._log = lambda m: None
        with tempfile.TemporaryDirectory() as d:
            try:
                rc = sup.run_bounded_session(thermal_root=None, drm_root=None, device_root=None, card="card0", required=[], guard=None,
                                             runner=None, status_dir=Path(d), unbounded=unbounded,
                                             _monotonic=clock.mono, _sleep=sleep)
            except AssertionError:
                rc = "still-running"
    finally:
        for k, v in saved.items():
            setattr(sup, k, v)
    return rc, clock.t, reasons


class UnboundedMonitoring(unittest.TestCase):
    def test_default_stops_at_180_seconds(self):
        rc, t, reasons = run(unbounded=False)
        self.assertEqual(rc, 0)
        self.assertEqual(reasons, ["deadline"])
        self.assertAlmostEqual(t, 180, delta=3)

    def test_unbounded_runs_past_the_deadline(self):
        rc, t, reasons = run(unbounded=True)
        self.assertEqual(rc, "still-running")      # only the test's own 3600 s guard ended it
        self.assertEqual(reasons, [])

    def test_unbounded_still_stops_at_high_temperature(self):
        rc, t, reasons = run(unbounded=True, hot_after=1000)
        self.assertEqual(rc, 2)
        self.assertEqual(reasons, ["monitor-fail"])
        self.assertAlmostEqual(t, 1000, delta=3)

    def test_unbounded_still_stops_when_the_session_is_lost(self):
        rc, t, reasons = run(unbounded=True, lose_session_after=700)
        self.assertEqual(rc, 2)
        self.assertEqual(reasons, ["monitor-fail"])

    def test_cmdline_enables_unbounded(self):
        with tempfile.TemporaryDirectory() as d:
            cl = Path(d) / "cmdline"
            cl.write_text("quiet kestrel_graphics=1 kestrel_graphics_unbounded=1\n")
            seen = {}
            orig = sup.run_bounded_session
            sup.run_bounded_session = lambda **k: seen.setdefault("unbounded", k["unbounded"]) and 0 or 0
            try:
                policy = Path(d) / "p.json"
                policy.write_text('{"required_sensor_types": ["a"]}')
                g = Path(d) / "kestrel_graphics_guard.py"
                g.write_text("")
                sup.main(["--policy", str(policy), "--cmdline", str(cl), "--status-dir", d])
            finally:
                sup.run_bounded_session = orig
            self.assertIs(seen.get("unbounded"), True)


if __name__ == "__main__":
    unittest.main()
