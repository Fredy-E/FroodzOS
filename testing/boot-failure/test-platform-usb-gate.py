#!/usr/bin/env python3
"""Each packed/early-load clause must independently reject a broken image."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "builder"))
from platform_usb_gate import REQUIRED_MODULES, check_platform_usb, normalized


class PlatformUsbGateTests(unittest.TestCase):
    def fixture(self, root, packed, forced):
        (root / "config").write_text('MODULES="' + ' '.join(forced) + '"\n')
        modules = root / "usr/lib/modules/test/kernel"
        modules.mkdir(parents=True)
        for name in packed:
            # Predicate fixtures, not real kernel modules or boot evidence.
            (modules / (name + ".ko.zst")).touch()

    def test_complete_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, REQUIRED_MODULES, REQUIRED_MODULES)
            self.assertTrue(all(check_platform_usb(root).values()))

    def test_every_presence_clause_is_load_bearing(self):
        for missing in REQUIRED_MODULES:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, [n for n in REQUIRED_MODULES if n != missing], REQUIRED_MODULES)
                checks = check_platform_usb(root)
                self.assertEqual([key for key, value in checks.items() if not value],
                                 [f"platform_{normalized(missing)}_packed"])

    def test_every_early_load_clause_is_load_bearing(self):
        for missing in REQUIRED_MODULES:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, REQUIRED_MODULES, [n for n in REQUIRED_MODULES if n != missing])
                checks = check_platform_usb(root)
                self.assertEqual([key for key, value in checks.items() if not value],
                                 [f"platform_{normalized(missing)}_early_load"])

    def test_underscore_aliases_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = [normalized(n) for n in REQUIRED_MODULES]
            self.fixture(root, names, names)
            self.assertTrue(all(check_platform_usb(root).values()))

    def test_malformed_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, REQUIRED_MODULES, REQUIRED_MODULES)
            (root / "config").write_text('MODULES=\n')
            checks = check_platform_usb(root)
            self.assertEqual(sum(not value for value in checks.values()), len(REQUIRED_MODULES))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PlatformUsbGateTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "fixture_only": True, "native_hardware_validated": False}
    (Path(__file__).parent / "platform-usb-gate-unit-result.json").write_text(json.dumps(report, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
