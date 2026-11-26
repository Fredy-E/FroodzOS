#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Portable tests for tools/check-log-leaks.py and the reader-side redactor."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "logs"
SPEC = importlib.util.spec_from_file_location("check_log_leaks", ROOT / "tools" / "check-log-leaks.py")
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["check_log_leaks"] = MOD
SPEC.loader.exec_module(MOD)

REDACT_SPEC = importlib.util.spec_from_file_location("fz_redact", ROOT / "tools" / "fz_redact.py")
REDACT = importlib.util.module_from_spec(REDACT_SPEC)
sys.modules["fz_redact"] = REDACT
REDACT_SPEC.loader.exec_module(REDACT)

FAKE_MAC = ":".join(["02"] * 5 + ["99"])
FAKE_PSK = "FZ-" + "FAKE-PSK-9999"
FAKE_SERIAL = "FZ" + "1234567890"


def run_cli(root, *extra):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = MOD.main(["--root", str(root)] + [str(x) for x in extra])
    return code, out.getvalue()


class LeakGateTests(unittest.TestCase):
    def temp_tree(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, value in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(value, bytes):
                path.write_bytes(value)
            else:
                path.write_text(value, encoding="utf-8", newline="\n")
        return root

    def test_synthetic_fixtures_are_allowed(self):
        code, out = run_cli(FIXTURES)
        self.assertEqual(code, 0, out)
        self.assertIn("0 finding(s)", out)

    def test_current_worktree_has_no_findings(self):
        code, out = run_cli(ROOT, "--worktree")
        self.assertEqual(code, 0, out)

    def test_boot_log_path_is_refused_and_content_is_not_printed(self):
        root = self.temp_tree({
            "Logs/boot-12345678-1234-1234-1234-123456789abc/01-kernel-kmsg.log":
                "6,1,0,-;Booting Linux ssid='FZ-SECRET-NET' psk=\"" + FAKE_PSK + "\"\n",
        })
        code, out = run_cli(root, "--json")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertTrue(data["findings"])
        self.assertEqual(data["findings"][0]["path"],
                         "Logs/boot-12345678-1234-1234-1234-123456789abc/01-kernel-kmsg.log")
        self.assertNotIn("FZ-SECRET-NET", out)
        self.assertNotIn(FAKE_PSK, out)

    def test_typescript_and_stream_segment_paths_are_refused(self):
        root = self.temp_tree({
            "artifacts/term.typescript": "script started\n",
            "notes/streams/journal/000001.jsonl": "{}\n",
        })
        code, out = run_cli(root)
        self.assertEqual(code, 1)
        self.assertIn("term.typescript", out)
        self.assertIn("streams/journal/000001.jsonl", out)

    def test_mac_serial_and_psk_shapes_outside_fixtures_fail(self):
        root = self.temp_tree({
            "notes/identifiers.txt": (
                "observed %s\nSerialNumber: %s\npsk=\"%s\"\n" % (FAKE_MAC, FAKE_SERIAL, FAKE_PSK)
            ),
        })
        code, out = run_cli(root, "--json")
        self.assertEqual(code, 1)
        reasons = " ".join(item["reason"] for item in json.loads(out)["findings"])
        self.assertIn("MAC-address-shaped", reasons)
        self.assertIn("serial-number-shaped", reasons)
        self.assertIn("PSK/password-shaped", reasons)
        for secret in (FAKE_MAC, FAKE_SERIAL, FAKE_PSK):
            self.assertNotIn(secret, out)

    def test_placeholder_values_pass(self):
        root = self.temp_tree({
            "notes/placeholders.txt": (
                "psk=<redacted:psk:0123456789ab>\n"
                "SerialNumber: <redacted>\n"
                "password=${PASSWORD}\n"
                "ssid=<ssid>\n"
            ),
        })
        code, out = run_cli(root)
        self.assertEqual(code, 0, out)

    def test_renamed_large_boot_log_fails_but_a_short_excerpt_passes(self):
        root = self.temp_tree({
            "notes/short.log.txt": "6,1,0,-;Booting Linux\n6,2,1,-;Linux version 7.3.0\n",
        })
        code, out = run_cli(root)
        self.assertEqual(code, 0, out)
        records = "".join("6,%d,100,-;%s\n" % (n, "x" * 2200) for n in range(35))
        root2 = self.temp_tree({"notes/renamed-notes.md": records})
        code, out = run_cli(root2, "--json")
        self.assertEqual(code, 1)
        self.assertTrue(any("renamed boot log" in item["reason"]
                            for item in json.loads(out)["findings"]))

    def test_zero_mac_and_documentation_are_not_flagged(self):
        root = self.temp_tree({
            "docs/example.md": "Use 00:00:00:00:00:00 as the placeholder MAC.\n",
        })
        code, out = run_cli(root)
        self.assertEqual(code, 0, out)


class RedactorSMokeTests(unittest.TestCase):
    def setUp(self):
        self.red = REDACT.Redactor(bytes.fromhex("00" * 32))

    def test_reader_redactor_removes_secret_shapes(self):
        source = (
            "wlan0 psk=\"%s\" ssid=\"FZ-FAKE-NET\" bssid=%s\n"
            "SerialNumber: %s\n"
            "mail someone@example.invalid\n"
        ) % (FAKE_PSK, FAKE_MAC, FAKE_SERIAL)
        out = self.red.text(source)
        for value in (FAKE_PSK, FAKE_MAC, FAKE_SERIAL, "FZ-FAKE-NET", "someone@example.invalid"):
            self.assertNotIn(value, out)
        self.assertIn("<redacted:", out)

    def test_redaction_is_idempotent(self):
        once = self.red.text("password=%s\n" % FAKE_PSK)
        twice = self.red.text(once)
        self.assertEqual(once, twice)

    def test_prompt_arms_the_next_line_rule(self):
        out = self.red.text("password for live:\ntyped-value\nnext-line\n")
        self.assertNotIn("typed-value", out)
        self.assertIn("next-line", out)

    def test_synthetic_token_vectors(self):
        github = "ghp" + "_" + "A" * 36
        aws = "AK" + "IA" + "C" * 16
        jwt = "eyJ" + "hbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIn0." + "E" * 32
        auth = "Authorization: Bearer " + "F" * 24
        url = "https://user:" + "G" * 16 + "@example.invalid/path"
        private_key = "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----"
        for source, value, kind in (
            ("github key", github, "github"),
            ("aws key", aws, "aws"),
            ("jwt", jwt, "jwt"),
            ("authorization", auth, "auth-bearer"),
            ("url userinfo", url, "url-credential"),
            ("private key", private_key, "private-key"),
        ):
            with self.subTest(source):
                out = self.red.text(source + " " + value + "\n")
                self.assertNotIn(value.splitlines()[0], out)
                self.assertIn("<redacted:" + kind, out)


if __name__ == "__main__":
    unittest.main()
