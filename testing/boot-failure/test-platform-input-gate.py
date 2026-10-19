#!/usr/bin/env python3
"""Each new I2C-HID archive/early-load predicate must be load-bearing."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P / 'builder'))
from platform_input_gate import REQUIRED_MODULES, check_platform_input
from platform_usb_gate import normalized


class InputGateTests(unittest.TestCase):
    def fixture(self, root, packed, forced):
        (root / 'config').write_text('MODULES="' + ' '.join(forced) + '"\n')
        modules = root / 'usr/lib/modules/test/kernel'
        modules.mkdir(parents=True)
        for name in packed:
            (modules / (name + '.ko.zst')).touch()

    def test_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, REQUIRED_MODULES, REQUIRED_MODULES)
            self.assertTrue(all(check_platform_input(root).values()))

    def test_each_packed_predicate(self):
        for missing in REQUIRED_MODULES:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, [m for m in REQUIRED_MODULES if m != missing], REQUIRED_MODULES)
                bad = [k for k, v in check_platform_input(root).items() if not v]
                self.assertEqual(bad, ['input_' + normalized(missing) + '_packed'])

    def test_each_forced_predicate(self):
        for missing in REQUIRED_MODULES:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.fixture(root, REQUIRED_MODULES, [m for m in REQUIRED_MODULES if m != missing])
                bad = [k for k, v in check_platform_input(root).items() if not v]
                self.assertEqual(bad, ['input_' + normalized(missing) + '_early_load'])

    def test_normalized_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = [normalized(m) for m in REQUIRED_MODULES]
            self.fixture(root, names, names)
            self.assertTrue(all(check_platform_input(root).values()))

    def test_malformed_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, REQUIRED_MODULES, REQUIRED_MODULES)
            (root / 'config').write_text('MODULES=\n')
            self.assertEqual(sum(not v for v in check_platform_input(root).values()), len(REQUIRED_MODULES))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InputGateTests))
    report = {'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'fixture_only': True}
    (Path(__file__).parent / 'platform-input-gate-unit-result.json').write_text(json.dumps(report, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
