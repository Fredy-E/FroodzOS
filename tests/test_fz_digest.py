#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Portable tests for tools/fz-digest.py using synthetic v2 and v3 fixtures."""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "logs"
V2 = FIXTURES / "v2-legacy"
V3 = FIXTURES / "v3-recorder"

SPEC = importlib.util.spec_from_file_location("fz_digest", ROOT / "tools" / "fz-digest.py")
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["fz_digest"] = MOD
SPEC.loader.exec_module(MOD)


def run_cli(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = MOD.main([str(a) for a in args])
    return code, out.getvalue()


def load(folder):
    boot = MOD.Boot(Path(folder))
    boot.load()
    return boot


class DigestTests(unittest.TestCase):
    def test_v2_legacy_layout(self):
        boot = load(V2)
        data = MOD.build_digest(boot)
        self.assertEqual(data["boot"]["layout"], "v2")
        self.assertEqual(data["boot"]["duration_s"], 120.0)
        self.assertIn("iio-sensor-proxy.service", data["failed_units"])
        self.assertIsNotNone(data["first_oops"])
        self.assertIsNotNone(data["first_warning"])
        self.assertIn("WARNING", data["first_warning"]["text"])
        self.assertGreaterEqual(len(data["first_warning"]["context"]), 3)
        self.assertIn("wifi", data["errors_by_subsystem"])
        self.assertIn("sound", data["errors_by_subsystem"])
        self.assertIn("waydroid", data["errors_by_subsystem"])
        self.assertEqual(data["terminal"], [])

    def test_v3_layout_and_power_loss(self):
        boot = load(V3)
        data = MOD.build_digest(boot)
        self.assertEqual(data["boot"]["layout"], "v3")
        self.assertEqual(data["boot"]["outcome"], "power_loss")
        kinds = [item["kind"] for item in data["destination"]["destinations"]]
        self.assertIn("stick", kinds)
        self.assertIn("persist", kinds)
        self.assertTrue(data["destination"]["degraded"])
        self.assertEqual(len(data["terminal"]), 4)
        self.assertEqual(sum(1 for row in data["terminal"] if row["nonzero"]), 1)
        self.assertEqual(data["findings"]["suspend"]["failed_resume"], "1")
        self.assertTrue(any("partial" in gap for gap in data["gaps"]))
        self.assertTrue(any("gap" in gap for gap in data["gaps"]))
        self.assertIn("ath12k", json.dumps(data["findings"]["wifi"]))
        self.assertIn("iio-sensor-proxy.service", data["failed_units"])

    def test_prompt_injection_is_quoted_not_instruction(self):
        data = MOD.build_digest(load(V3))
        kinds = {item["kind"] for item in data["suspicious"]}
        self.assertIn("override-instructions", kinds)
        for item in data["suspicious"]:
            self.assertTrue(item["text"].startswith('"') and item["text"].endswith('"'))
        v2 = MOD.build_digest(load(V2))
        self.assertTrue(any(item["kind"] == "fake-role-prefix" for item in v2["suspicious"]))

    def test_secrets_and_identifiers_are_masked_in_output(self):
        for folder in (V2, V3):
            code, text = run_cli(folder)
            self.assertEqual(code, 0)
            for secret in ("FZ-FAKE-PSK-0001", "FZ-FAKE-PSK-0002", "FZ-FAKE-PSK-0003",
                           "FAKE-" + "SERIAL-0001", ":".join(["02"] * 5 + ["04"])):
                self.assertNotIn(secret, text)
            self.assertIn("prompt-injection-like", text)

    def test_json_output_is_deterministic(self):
        first = json.dumps(MOD.build_digest(load(V3)), indent=2, ensure_ascii=False)
        second = json.dumps(MOD.build_digest(load(V3)), indent=2, ensure_ascii=False)
        self.assertEqual(first, second)
        code, out = run_cli(V3, "--json")
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["schema"], "fz-digest/1")
        self.assertIn("first_oops", parsed)
        self.assertIn("timeline", parsed)

    def test_complete_index_wins_over_partial(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name) / "boot-v3-clean"
        shutil.copytree(V3, folder)
        (folder / "index.json").write_text(json.dumps({
            "schema": 3, "boot_id": "99999999-8888-7777-6666-555555555555",
            "complete": True, "outcome": "clean", "duration_s": 41,
            "streams": {"kernel": {"total_bytes": 512, "gaps": []}},
        }), encoding="utf-8")
        data = MOD.build_digest(load(folder))
        self.assertEqual(data["boot"]["outcome"], "clean")
        self.assertEqual(data["boot"]["duration_s"], 41.0)
        self.assertFalse(any("partial" in gap for gap in data["gaps"]))

    def test_previous_boot_difference(self):
        prev = load(V2)
        boot = load(V3)
        boot.previous = prev
        data = MOD.build_digest(boot)
        self.assertEqual(data["previous"]["boot_id"], "11111111-2222-3333-4444-555555555555")
        changes = " ".join(data["previous"]["changes"])
        self.assertIn("duration_s", changes)
        self.assertIn("terminal_commands", changes)
        code, out = run_cli(V3, "--prev", V2)
        self.assertEqual(code, 0)
        self.assertIn("Changes vs previous boot", out)

    def test_quote_escapes_control_text_and_masks_secrets(self):
        secret = "FZ-" + "FAKE-PSK-9999"
        quoted = MOD.quote("line one\nline two\x01 password=" + secret)
        self.assertNotIn("\n", quoted)
        self.assertIn("\\x01", quoted)
        self.assertIn("<masked>", quoted)
        self.assertNotIn(secret, quoted)

    def test_missing_folder_returns_2(self):
        code, out = run_cli(ROOT / "does-not-exist")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
