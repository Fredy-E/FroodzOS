#!/usr/bin/env python3
"""Independent synthetic reproduction of rejected real-shaped sysfs class links.

Character identity is explicitly mocked; no device is opened and this is not
native hardware validation. Exit zero means the pre-review false-negative was
reproduced, NOT that graphics preflight is working.
"""
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest import mock

P = Path('/mnt/d/CachyOS-ARM64')
spec = importlib.util.spec_from_file_location('guard', P / 'builder/diagnostics/kestrel_graphics_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
with tempfile.TemporaryDirectory(prefix='dt25-parent-sysfs-', dir='/home/builder/boot-failure-tests') as tmp:
    root = Path(tmp)
    thermal = root / 'sys/class/thermal'
    thermal.mkdir(parents=True)
    required = {'fixture-cpu0', 'fixture-cpu1'}
    for i, name in enumerate(sorted(required)):
        actual = root / ('sys/devices/virtual/thermal/thermal_zone' + str(i))
        actual.mkdir(parents=True)
        (actual / 'type').write_text(name + '\n')
        (actual / 'temp').write_text('43000\n')
        (thermal / actual.name).symlink_to(actual, target_is_directory=True)
    drm = root / 'sys/class/drm'
    drm.mkdir(parents=True)
    platform = root / 'sys/devices/platform/simple-framebuffer.0'
    card = platform / 'drm/card0'
    card.mkdir(parents=True)
    (card / 'dev').write_text('226:0\n')
    (card / 'device').symlink_to(platform, target_is_directory=True)
    driver = root / 'sys/bus/platform/drivers/simple-framebuffer'
    driver.mkdir(parents=True)
    (platform / 'driver').symlink_to(driver, target_is_directory=True)
    connector = card / 'card0-Unknown-1'
    connector.mkdir()
    (connector / 'status').write_text('connected\n')
    (connector / 'modes').write_text('1920x1200\n')
    (drm / 'card0').symlink_to(card, target_is_directory=True)
    (drm / connector.name).symlink_to(connector, target_is_directory=True)
    dev = root / 'dev/dri'
    dev.mkdir(parents=True)
    (dev / 'card0').touch()
    readings = guard.collect_temperatures(thermal, required)
    with mock.patch.object(guard, '_node_identity', return_value=(226, 0)):
        snapshot = guard.collect_drm(drm, dev)
    t = guard.evaluate_temperatures(readings, required)
    d = guard.evaluate_drm(snapshot)
    bug = not readings and not snapshot['connectors'] and not t['ok'] and not d['ok']
    print(json.dumps({'pre_review_false_negative_reproduced': bug,
                      'realistic_class_symlink_fixture': True, 'drm_character_identity_mocked': True,
                      'temperatures_collected': readings, 'drm_snapshot': snapshot,
                      'thermal_policy': t, 'drm_policy': d, 'native_hardware_validated': False}, indent=2))
    raise SystemExit(0 if bug else 1)
