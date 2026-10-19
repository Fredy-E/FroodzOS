#!/usr/bin/env python3
"""Synthetic safety-policy tests, not native temperature or DRM validation."""
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

P = Path('/mnt/d/CachyOS-ARM64')
MODULE = P / 'builder/diagnostics/kestrel_graphics_guard.py'
spec = importlib.util.spec_from_file_location('kestrel_graphics_guard', MODULE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ThermalPolicy(unittest.TestCase):
    def good(self):
        return [{'type': 'fixture-cpu0', 'temp_mc': 42000}, {'type': 'fixture-cpu1', 'temp_mc': 47000}]

    def evaluate(self, rows):
        return guard.evaluate_temperatures(rows, {'fixture-cpu0', 'fixture-cpu1'})

    def test_valid_soc_temperatures(self):
        result = self.evaluate(self.good())
        self.assertTrue(result['ok'])
        self.assertEqual(result['maximum_mc'], 47000)

    def test_battery_is_not_soc_temperature(self):
        self.assertFalse(self.evaluate([{'type': 'qcom-battmgr-bat', 'temp_mc': 30000}])['ok'])

    def test_every_required_sensor_is_load_bearing(self):
        for missing in range(2):
            self.assertFalse(self.evaluate([r for i, r in enumerate(self.good()) if i != missing])['ok'])

    def test_unreadable_sensor_blocks(self):
        rows = self.good(); rows[1]['temp_mc'] = None
        self.assertFalse(self.evaluate(rows)['ok'])

    def test_uninitialized_zero_blocks(self):
        rows = self.good(); rows[0]['temp_mc'] = 0
        self.assertFalse(self.evaluate(rows)['ok'])

    def test_strings_floats_and_bool_are_not_valid_samples(self):
        for value in ['42000', 42000.0, True]:
            rows = self.good(); rows[0]['temp_mc'] = value
            self.assertFalse(self.evaluate(rows)['ok'])

    def test_hot_limit_is_inclusive(self):
        rows = self.good(); rows[0]['temp_mc'] = 80000
        self.assertFalse(self.evaluate(rows)['ok'])

    def test_impossible_and_cold_values_block(self):
        for value in [-200000, -1, 4999, 125001]:
            rows = self.good(); rows[0]['temp_mc'] = value
            self.assertFalse(self.evaluate(rows)['ok'])

    def test_duplicate_required_sensor_is_ambiguous(self):
        self.assertFalse(self.evaluate(self.good() + [self.good()[0]])['ok'])

    def test_empty_policy_blocks(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), set())['ok'])

    def test_unrelated_sensor_does_not_substitute_or_set_maximum(self):
        result = self.evaluate(self.good() + [{'type': 'qcom-battmgr-bat', 'temp_mc': 200000}])
        self.assertTrue(result['ok'])
        self.assertEqual(result['maximum_mc'], 47000)

    def test_sysfs_collection_is_read_only_and_reports_bad_values(self):
        with tempfile.TemporaryDirectory(prefix='dt25-thermal-', dir='/home/builder/boot-failure-tests') as tmp:
            root = Path(tmp)
            for i, (name, value) in enumerate([('fixture-cpu0', '43000\n'), ('fixture-cpu1', 'bad\n'), ('qcom-battmgr-bat', '30000\n')]):
                zone = root / ('thermal_zone' + str(i)); zone.mkdir()
                (zone / 'type').write_text(name + '\n'); (zone / 'temp').write_text(value)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            rows = guard.collect_temperatures(root, {'fixture-cpu0', 'fixture-cpu1'})
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(len(rows), 2)
            self.assertFalse(self.evaluate(rows)['ok'])


class DrmPolicy(unittest.TestCase):
    def good(self):
        return {'card': 'card0', 'driver': 'simple-framebuffer', 'character_device': True,
                'connectors': [{'status': 'connected', 'modes': ['1920x1200']}]}

    def test_simpledrm_connected_output(self):
        self.assertTrue(guard.evaluate_drm(self.good())['ok'])

    def test_unexpected_driver_blocks(self):
        data = self.good(); data['driver'] = 'msm'
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_regular_file_is_not_a_drm_device(self):
        data = self.good(); data['character_device'] = False
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_card_path_injection_blocks(self):
        data = self.good(); data['card'] = '../../card0'
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_absent_disconnected_and_modeless_connectors_block(self):
        for connectors in [[], [{'status': 'disconnected', 'modes': ['1920x1200']}], [{'status': 'connected', 'modes': []}]]:
            data = self.good(); data['connectors'] = connectors
            self.assertFalse(guard.evaluate_drm(data)['ok'])


class ThermalHardening(unittest.TestCase):
    """Malformed thermal inputs must fail closed, never raise."""

    def good(self):
        return [{'type': 'fixture-cpu0', 'temp_mc': 42000}, {'type': 'fixture-cpu1', 'temp_mc': 47000}]

    def test_null_readings_fail_closed(self):
        self.assertFalse(guard.evaluate_temperatures(None, {'fixture-cpu0'})['ok'])

    def test_non_dict_entries_fail_closed(self):
        for bad in (None, 'x', 123, ['fixture-cpu0']):
            rows = self.good() + [bad]
            self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0', 'fixture-cpu1'})['ok'])

    def test_null_required_fails_closed(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), None)['ok'])

    def test_string_required_fails_closed(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), 'fixture-cpu0')['ok'])

    def test_mixed_invalid_required_sorts_safely(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), {'fixture-cpu0', 1, None})['ok'])

    def test_unhashable_required_fails_closed(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), [['fixture-cpu0']])['ok'])

    def test_unhashable_reading_type_fails_closed(self):
        rows = self.good() + [{'type': ['fixture-cpu0'], 'temp_mc': 42000}]
        self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0', 'fixture-cpu1'})['ok'])

    def test_invalid_limits_fail_closed(self):
        for minimum, stop in [(True, 80000), (5000.0, 80000), (None, 80000), (5000, True),
                              (80000, 80000), (70000, 60000), (5000, 80001), (0, 80000), (-5, 80000)]:
            result = guard.evaluate_temperatures(self.good(), {'fixture-cpu0', 'fixture-cpu1'}, minimum, stop)
            self.assertFalse(result['ok'])
            self.assertIn('invalid_temperature_limits', result['errors'])

    def test_overlong_required_name_fails_closed(self):
        self.assertFalse(guard.evaluate_temperatures(self.good(), {'A' * 200})['ok'])


class ThermalCollectHardening(unittest.TestCase):
    def test_missing_thermal_root_blocks(self):
        rows = guard.collect_temperatures('/home/builder/boot-failure-tests/dt25-guard-v2-missing', {'fixture-cpu0'})
        self.assertEqual(rows, [])
        self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0'})['ok'])

    def test_null_thermal_root_fails_closed(self):
        rows = guard.collect_temperatures(None, {'fixture-cpu0'})
        self.assertEqual(rows, [])
        self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0'})['ok'])

    def test_symlink_zone_does_not_escape(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            root = Path(tmp) / 'thermal'; root.mkdir()
            outside = Path(tmp) / 'outside'; outside.mkdir()
            (outside / 'type').write_text('fixture-cpu0\n')
            (outside / 'temp').write_text('43000\n')
            os.symlink(str(outside), root / 'thermal_zone0')
            rows = guard.collect_temperatures(root, {'fixture-cpu0'})
            self.assertEqual(rows, [])
            self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0'})['ok'])

    def test_symlink_temp_file_is_unreadable(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            root = Path(tmp); zone = root / 'thermal_zone0'; zone.mkdir()
            (zone / 'type').write_text('fixture-cpu0\n')
            real = zone / 'real_temp'; real.write_text('43000\n')
            os.symlink(str(real), zone / 'temp')
            rows = guard.collect_temperatures(root, {'fixture-cpu0'})
            self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0'})['ok'])

    def test_overlong_type_ignored(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            root = Path(tmp); zone = root / 'thermal_zone0'; zone.mkdir()
            (zone / 'type').write_text('A' * 200 + '\n')
            (zone / 'temp').write_text('43000\n')
            self.assertEqual(guard.collect_temperatures(root, {'A' * 200}), [])

    def test_nonascii_temp_blocks(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            root = Path(tmp); zone = root / 'thermal_zone0'; zone.mkdir()
            (zone / 'type').write_text('fixture-cpu0\n')
            (zone / 'temp').write_bytes(b'\xff\xfe\n')
            rows = guard.collect_temperatures(root, {'fixture-cpu0'})
            self.assertFalse(guard.evaluate_temperatures(rows, {'fixture-cpu0'})['ok'])


class DrmEvaluateHardening(unittest.TestCase):
    def good(self):
        return {'card': 'card0', 'driver': 'simpledrm', 'character_device': True,
                'connectors': [{'status': 'connected', 'modes': ['1920x1200']}]}

    def test_null_snapshot_fails_closed(self):
        self.assertFalse(guard.evaluate_drm(None)['ok'])

    def test_non_dict_snapshot_fails_closed(self):
        for bad in ([], 'x', 123):
            self.assertFalse(guard.evaluate_drm(bad)['ok'])

    def test_null_card_fails_closed(self):
        data = self.good(); data['card'] = None
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_int_card_fails_closed(self):
        data = self.good(); data['card'] = 0
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_unhashable_driver_fails_closed(self):
        data = self.good(); data['driver'] = ['simpledrm']
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_none_connectors_fails_closed(self):
        data = self.good(); data['connectors'] = None
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_string_connectors_fails_closed(self):
        data = self.good(); data['connectors'] = 'connected'
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_none_connector_fails_closed(self):
        data = self.good(); data['connectors'] = [None]
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_none_modes_fails_closed(self):
        data = self.good(); data['connectors'] = [{'status': 'connected', 'modes': None}]
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_string_modes_fails_closed(self):
        data = self.good(); data['connectors'] = [{'status': 'connected', 'modes': '1920x1200'}]
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_overlong_mode_blocks(self):
        data = self.good(); data['connectors'] = [{'status': 'connected', 'modes': ['9' * 5000 + 'x12']}]
        self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_zero_and_huge_modes_block(self):
        for modes in (['0x0'], ['1920x0'], ['99999x99999'], [' 1920x1200'], ['1920x1200\n'], [123], [None]):
            data = self.good(); data['connectors'] = [{'status': 'connected', 'modes': modes}]
            self.assertFalse(guard.evaluate_drm(data)['ok'])

    def test_integer_character_device_is_not_true(self):
        data = self.good(); data['character_device'] = 1
        result = guard.evaluate_drm(data)
        self.assertFalse(result['ok'])
        self.assertIn('missing_drm_character_device', result['errors'])


class DrmCollectHardening(unittest.TestCase):
    """Synthetic DRM identity: sysfs dev major/minor must match the device node."""

    def make_roots(self, tmp):
        drm_root = Path(tmp) / 'drm'; dev_root = Path(tmp) / 'dri'
        drm_root.mkdir(); dev_root.mkdir()
        card = drm_root / 'card0'; card.mkdir()
        (card / 'dev').write_text('226:0\n')
        device = card / 'device'; device.mkdir()
        target = drm_root / 'drivers' / 'simpledrm'; target.mkdir(parents=True)
        os.symlink(str(target), device / 'driver')
        conn = drm_root / 'card0-HDMI-A-1'; conn.mkdir()
        (conn / 'status').write_text('connected\n')
        (conn / 'modes').write_text('1920x1200\n')
        return drm_root, dev_root

    def fake_chr(self, node, major, minor):
        real = Path.stat

        def _fake(self):
            if self == node:
                m = mock.MagicMock()
                m.st_mode = stat.S_IFCHR | 0o600
                m.st_rdev = os.makedev(major, minor)
                return m
            return real(self)

        return mock.patch.object(Path, 'stat', _fake)

    def test_collect_regular_file_is_not_device(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (dev_root / 'card0').write_text('not-a-device')
            snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_symlink_to_null_is_not_device(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            os.symlink('/dev/null', dev_root / 'card0')
            snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_symlink_loop_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            os.symlink(str(dev_root / 'card0'), dev_root / 'card0')
            snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_nul_path_fails_closed(self):
        snap = guard.collect_drm('/tmp\x00x', '/tmp\x00y', 'card0')
        self.assertFalse(snap['character_device'])
        self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_missing_sysfs_dev_fails(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (drm_root / 'card0' / 'dev').unlink()
            (dev_root / 'card0').write_text('placeholder')
            node = dev_root / 'card0'
            with self.fake_chr(node, 226, 0):
                snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_mismatched_sysfs_dev_fails(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (drm_root / 'card0' / 'dev').write_text('226:1\n')
            (dev_root / 'card0').write_text('placeholder')
            node = dev_root / 'card0'
            with self.fake_chr(node, 226, 0):
                snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_wrong_major_fails(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (dev_root / 'card0').write_text('placeholder')
            node = dev_root / 'card0'
            with self.fake_chr(node, 1, 3):
                snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertFalse(snap['character_device'])
            self.assertFalse(guard.evaluate_drm(snap)['ok'])

    def test_collect_valid_matching_identity(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (dev_root / 'card0').write_text('placeholder')
            node = dev_root / 'card0'
            with self.fake_chr(node, 226, 0):
                snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertTrue(snap['character_device'])
            self.assertEqual(snap['driver'], 'simpledrm')
            self.assertTrue(guard.evaluate_drm(snap)['ok'])

    def test_collect_driver_symlink_loop_fails(self):
        with tempfile.TemporaryDirectory(prefix='dt25-guard-v2-', dir='/home/builder/boot-failure-tests') as tmp:
            drm_root, dev_root = self.make_roots(tmp)
            (dev_root / 'card0').write_text('placeholder')
            link = drm_root / 'card0' / 'device' / 'driver'
            link.unlink()
            os.symlink(str(link), link)
            node = dev_root / 'card0'
            with self.fake_chr(node, 226, 0):
                snap = guard.collect_drm(drm_root, dev_root, 'card0')
            self.assertNotEqual(snap['driver'], 'simpledrm')
            self.assertFalse(guard.evaluate_drm(snap)['ok'])


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    report = {'passed': result.wasSuccessful(), 'tests_run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'synthetic_policy_fixtures_only': True, 'native_hardware_validated': False}
    print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
