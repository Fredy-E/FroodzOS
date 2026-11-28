#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure tests for the FZ_RECORDER marker table and the QEMU command contract.

The six-minute QEMU boot is not run here. These tests exercise the same
evaluation functions that qemu-public.py uses on the serial transcript, so a
marker or contract mistake fails in seconds.
"""
import importlib.util
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qemu_public", ROOT / "builder" / "public-image" / "qemu-public.py")
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["qemu_public"] = MOD
SPEC.loader.exec_module(MOD)

GOOD_BLOCK = """noise
===REC===
service_active=active
userspace_monotonic_us=1200000
recorder_started_monotonic_us=2600000
first_record_uptime_ms=900
handover_gap_ms=350
kmsg_has_boot=1
kmsg_bytes=812345
journal_bytes=1203456
term_has_marker=1
term_has_exit=1
term_has_secret=0
term_has_redacted=1
max_file_bytes=8388608
total_bytes=52428800
per_file_cap=8388608
global_cap=67108864
cap_ok=1
flood_supported=1
flood_cap_reached=1
free_after_kb=4096
reserve_kb=2048
guard_ok=1
redaction_seen=1
ram_fallback=0
printk_console=4
excess=0
journald_forwards_kmsg=0
false_alarm_events=0
smartlog_starts=1
===RECEND===
"""


def replace(block, key, value):
    return "\n".join(("%s=%s" % (key, value)) if line.startswith(key + "=") else line
                     for line in block.splitlines())


class RecorderMarkerTests(unittest.TestCase):
    def test_good_block_passes(self):
        markers = MOD.evaluate_recorder_markers(GOOD_BLOCK)
        self.assertTrue(markers["block_found"])
        self.assertTrue(MOD.recorder_markers_pass(markers))
        self.assertTrue(markers["flood_cap_reached"])
        self.assertEqual(markers["raw"]["kmsg_bytes"], "812345")

    def test_ansi_and_crlf_are_tolerated(self):
        decorated = "chat\x1b[0m\r\n" + GOOD_BLOCK.replace("\n", "\r\n")
        markers = MOD.evaluate_recorder_markers(decorated)
        self.assertTrue(markers["block_found"])
        self.assertTrue(MOD.recorder_markers_pass(markers))

    def test_missing_block_fails(self):
        markers = MOD.evaluate_recorder_markers("login: no recorder block here")
        self.assertFalse(markers["block_found"])
        self.assertFalse(MOD.recorder_markers_pass(markers))

    def test_each_required_marker_can_fail(self):
        cases = {
            "service_active": "inactive",
            "kmsg_has_boot": "0",
            "kmsg_bytes": "0",
            "journal_bytes": "0",
            "term_has_marker": "0",
            "term_has_exit": "0",
            "term_has_redacted": "0",
            "redaction_seen": "0",
            "cap_ok": "0",
            "free_after_kb": "1",
            "guard_ok": "0",
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                markers = MOD.evaluate_recorder_markers(replace(GOOD_BLOCK, key, value))
                self.assertFalse(MOD.recorder_markers_pass(markers), key)

    def test_secret_present_breaks_redaction(self):
        markers = MOD.evaluate_recorder_markers(replace(GOOD_BLOCK, "term_has_secret", "1"))
        self.assertFalse(markers["terminal_redaction_applied"])
        self.assertFalse(MOD.recorder_markers_pass(markers))

    def test_late_start_and_bad_gap_are_markers(self):
        late = replace(replace(GOOD_BLOCK, "recorder_started_monotonic_us", "9000000"),
                       "handover_gap_ms", "2500")
        markers = MOD.evaluate_recorder_markers(late)
        self.assertFalse(markers["recorder_started_early"])
        self.assertFalse(markers["handover_gap_ok"])

    def test_size_caps_are_checked_against_the_reported_limits(self):
        markers = MOD.evaluate_recorder_markers(
            replace(replace(GOOD_BLOCK, "max_file_bytes", "9000000"), "total_bytes", "70000000"))
        self.assertFalse(markers["size_cap_respected"])

    def test_panic_always_fails(self):
        markers = MOD.evaluate_recorder_markers(GOOD_BLOCK + "\nKernel panic - not syncing\n")
        self.assertTrue(markers["panic"])
        self.assertFalse(MOD.recorder_markers_pass(markers))

    def test_table_is_adjustable(self):
        table = ({"name": "only_this", "required": True,
                  "check": lambda kv: kv.get("service_active") == "active"},)
        markers = MOD.evaluate_recorder_markers(GOOD_BLOCK, table)
        self.assertTrue(MOD.recorder_markers_pass(markers, table))
        markers = MOD.evaluate_recorder_markers(replace(GOOD_BLOCK, "service_active", "failed"), table)
        self.assertFalse(MOD.recorder_markers_pass(markers, table))

    def test_rescue_and_optional_markers_are_not_required(self):
        markers = MOD.evaluate_recorder_markers(replace(GOOD_BLOCK, "ram_fallback", "1"))
        self.assertTrue(markers["ram_fallback_used"])
        self.assertTrue(MOD.recorder_markers_pass(markers))


class PowercutTests(unittest.TestCase):
    def test_readable_logs_pass(self):
        files = {"stream_files": 2, "complete_records": 12, "alive_marker": True}
        markers = MOD.evaluate_powercut("FZREC_POWER_READY\n", files)
        self.assertTrue(MOD.powercut_markers_pass(markers))

    def test_no_ready_marker_or_no_records_fails(self):
        self.assertFalse(MOD.powercut_markers_pass(
            MOD.evaluate_powercut("no marker", {"stream_files": 1, "complete_records": 1})))
        self.assertFalse(MOD.powercut_markers_pass(
            MOD.evaluate_powercut("FZREC_POWER_READY", {"stream_files": 1, "complete_records": 0})))


class HarnessContractTests(unittest.TestCase):
    def test_command_keeps_defaults_and_adds_recorder_pieces(self):
        default = MOD.build_qemu_command(Path("image.img"), False, False, "", Path("unused.mon"))
        self.assertIn("snapshot=on", " ".join(default))
        self.assertEqual(default[default.index("-monitor") + 1], "none")
        recorder = MOD.build_qemu_command(Path("image.img"), False, False, "full", Path("qemu.mon"))
        joined = " ".join(recorder)
        self.assertNotIn("snapshot=on", joined)
        self.assertIn("id=rectest", joined)
        self.assertIn("unix:qemu.mon,server=on,wait=off", joined)

    def test_guest_script_uses_the_documented_contract(self):
        script = MOD.recorder_selftest_script()
        for token in ("===REC===", "===RECEND===", "streams/kernel", "streams/journal",
                      "streams/terminal", "FZREC_MARKER_", "FZREC_SECRET_", "term_has_exit", "REDACTED",
                      "cap_reached=1", "FZREC_", "_READY"):
            self.assertIn(token, script)
        self.assertIn("FZ_LOG_MAX_STREAM_BYTES", script)
        self.assertIn("FZ_LOG_MIN_FREE_KB", script)

    @unittest.skipUnless(shutil.which("sh"), "sh not installed")
    def test_guest_script_is_posix_shell(self):
        proc = subprocess.run(["sh", "-n"], input=MOD.recorder_selftest_script(), text=True,
                              capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
