#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Portable tests for tools/fz-sigscan.py and the local signature catalog."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "logs"
V2 = FIXTURES / "v2-legacy"
V3 = FIXTURES / "v3-recorder"
CATALOG = ROOT / "tools" / "data" / "fz-signatures.json"

SPEC = importlib.util.spec_from_file_location("fz_sigscan", ROOT / "tools" / "fz-sigscan.py")
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["fz_sigscan"] = MOD
SPEC.loader.exec_module(MOD)


def run_cli(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = MOD.main([str(a) for a in args])
    return code, out.getvalue()


class CatalogTests(unittest.TestCase):
    def test_catalog_is_clean_and_complete(self):
        raw = CATALOG.read_text(encoding="utf-8")
        signatures = MOD.load_catalog(CATALOG)
        self.assertGreaterEqual(len(signatures), 40)
        self.assertEqual(len({s["id"] for s in signatures}), len(signatures))
        for signature in signatures:
            self.assertIn(signature["class"], ("KNOWN-ISSUE", "BENIGN-NOISE", "UNKNOWN/INVESTIGATE"))
            self.assertIn(signature["severity"], ("critical", "high", "medium", "low", "info"))
            self.assertTrue(signature["note"])
        for banned in ("ghp_", "AKIA", "FZ-FAKE", "@example.", "BEGIN PRIVATE KEY"):
            self.assertNotIn(banned, raw)
        self.assertNotRegex(raw, r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
        self.assertNotRegex(raw, r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")

    def test_bad_catalog_is_rejected(self):
        bad = ROOT / "tests" / ".bad-signatures.json"
        try:
            bad.write_text('{"signatures": [{"id": "x"}]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                MOD.load_catalog(bad)
        finally:
            bad.unlink(missing_ok=True)


class ScanTests(unittest.TestCase):
    def test_v2_scan_finds_the_known_issues(self):
        code, out = run_cli(V2, "--json", "--top", "10")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["boot"]["layout"], "v2")
        self.assertGreater(data["lines"], 20)
        self.assertGreater(data["matched"], 0)
        issues = {row["issue"] for row in data["known_issues"]}
        self.assertIn("ath12k-resume-failure", issues)
        self.assertIn("audio-topology-1001002", issues)
        self.assertIn("wsa884x-audio", issues)
        self.assertTrue(data["unknown"])
        self.assertTrue(all("suggested_regex" in row for row in data["unknown"]))

    def test_v3_scan_reads_streams(self):
        code, out = run_cli(V3, "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["boot"]["layout"], "v3")
        self.assertGreater(data["sources"]["kernel"], 0)
        self.assertGreater(data["sources"]["userspace"], 0)
        issues = {row["issue"] for row in data["known_issues"]}
        self.assertIn("nvme-enable-oops", issues)
        self.assertEqual(data["catalog"]["signatures"], len(MOD.load_catalog(CATALOG)))

    def test_learn_prints_unknown_clusters_and_draft(self):
        code, out = run_cli(V2, "--learn", "--top", "5")
        self.assertEqual(code, 0)
        self.assertIn("UNKNOWN/INVESTIGATE", out)
        self.assertIn("draft:", out)
        self.assertIn("sources:", out)
        self.assertNotIn("FZ-FAKE-NET", out)
        self.assertNotIn(":".join(["02"] * 5 + ["01"]), out)

    def test_normaliser_removes_identifiers(self):
        mac = ":".join(["02"] * 5 + ["01"])
        serial = "SN" + "1234567890"
        line = ("wlan0 associated ssid='FZ-FAKE-NET' bssid=%s "
                "serial=%s user=someone@example.invalid ip=203.0.113.9" % (mac, serial))
        text = MOD.normalise(line, "NetworkManager")
        self.assertNotIn("FZ-FAKE-NET", text)
        self.assertNotIn(mac, text)
        self.assertNotIn(serial, text)
        self.assertNotIn("someone@example.invalid", text)
        self.assertNotIn("203.0.113.9", text)
        self.assertIn("<ssid>", text)
        self.assertIn("<mac>", text)

    def test_missing_boot_returns_2(self):
        code, out = run_cli(ROOT / "does-not-exist")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
