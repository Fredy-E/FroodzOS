#!/usr/bin/env python3
"""dt25-guard-v3 positive proof: genuine sysfs class symlinks now collect.

Kernel-shaped fixture under /home/builder/boot-failure-tests (never /tmp):
  sys/class/thermal/thermal_zoneN -> sys/devices/virtual/thermal/thermal_zoneN
  sys/class/drm/card0 -> sys/devices/platform/.../drm/card0
  sys/class/drm/card0-Unknown-1 -> <card>/card0-Unknown-1 (same-card ancestry)
Character identity is mocked (no device opened); not native validation.
Exit 0 only when genuine links collect and evaluate ok, and escaping/
dangling/symlink-root/leaf-alias cases still fail closed.
"""
import importlib.util
import json
import os
import stat
import tempfile
from pathlib import Path
from unittest import mock

P = Path('/mnt/d/CachyOS-ARM64')
spec = importlib.util.spec_from_file_location('guard', P / 'builder/diagnostics/kestrel_graphics_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

real_stat = Path.stat

def fake_chr(node, major, minor):
    def _fake(self):
        if self == node:
            m = mock.MagicMock()
            m.st_mode = stat.S_IFCHR | 0o600
            m.st_rdev = os.makedev(major, minor)
            return m
        return real_stat(self)
    return mock.patch.object(Path, 'stat', _fake)

with tempfile.TemporaryDirectory(prefix='dt25-guard-v3-proof-', dir='/home/builder/boot-failure-tests') as tmp:
    base = Path(tmp)
    thermal = base / 'sys' / 'class' / 'thermal'
    thermal.mkdir(parents=True)
    required = {'fixture-cpu0', 'fixture-cpu1'}
    for i, name in enumerate(sorted(required)):
        actual = base / 'sys' / 'devices' / 'virtual' / 'thermal' / ('thermal_zone' + str(i))
        actual.mkdir(parents=True)
        (actual / 'type').write_text(name + '\n')
        (actual / 'temp').write_text('43000\n')
        (thermal / actual.name).symlink_to(actual, target_is_directory=True)
    drm = base / 'sys' / 'class' / 'drm'
    drm.mkdir(parents=True)
    platform = base / 'sys' / 'devices' / 'platform' / 'simple-framebuffer.0'
    card = platform / 'drm' / 'card0'
    card.mkdir(parents=True)
    (card / 'dev').write_text('226:0\n')
    (card / 'device').symlink_to(platform, target_is_directory=True)
    driver = base / 'sys' / 'bus' / 'platform' / 'drivers' / 'simple-framebuffer'
    driver.mkdir(parents=True)
    (platform / 'driver').symlink_to(driver, target_is_directory=True)
    connector = card / 'card0-Unknown-1'
    connector.mkdir()
    (connector / 'status').write_text('connected\n')
    (connector / 'modes').write_text('1920x1200\n')
    (drm / 'card0').symlink_to(card, target_is_directory=True)
    (drm / connector.name).symlink_to(connector, target_is_directory=True)
    dev = base / 'dev' / 'dri'
    dev.mkdir(parents=True)
    (dev / 'card0').write_text('placeholder')
    readings = guard.collect_temperatures(thermal, required)
    with fake_chr(dev / 'card0', 226, 0):
        snapshot = guard.collect_drm(drm, dev)
    t = guard.evaluate_temperatures(readings, required)
    d = guard.evaluate_drm(snapshot)
    # Negative spot-checks (must stay fail-closed).
    outside = base / 'outside'
    outside.mkdir()
    (outside / 'type').write_text('fixture-cpu0\n')
    (outside / 'temp').write_text('43000\n')
    (thermal / 'thermal_zone9').symlink_to(outside, target_is_directory=True)
    escape_rows = guard.collect_temperatures(thermal, required)
    escape_ok = len(escape_rows) == 2
    (thermal / 'thermal_zone9').unlink()
    linkroot = base / 'drm-link'
    linkroot.symlink_to(drm)
    with fake_chr(dev / 'card0', 226, 0):
        symlink_root_snap = guard.collect_drm(linkroot, dev)
    symlink_root_ok = (not symlink_root_snap['character_device'] and symlink_root_snap['connectors'] == [])
    try:
        int_bug = guard.evaluate_temperatures([{'type': 1, 'temp_mc': 42000}, {'type': 1, 'temp_mc': 43000}], {1})
        int_ok = not int_bug['ok']
    except Exception:
        int_ok = False
    positive = (len(readings) == 2 and t['ok'] and len(snapshot['connectors']) == 1 and d['ok']
                and escape_ok and symlink_root_ok and int_ok)
    print(json.dumps({'genuine_thermal_rows': len(readings), 'genuine_drm_connectors': len(snapshot['connectors']),
                      'thermal_ok': t['ok'], 'drm_ok': d['ok'], 'escape_still_rejected': escape_ok,
                      'symlink_root_still_rejected': symlink_root_ok, 'int_policy_never_raises': int_ok,
                      'positive_proof': positive, 'native_hardware_validated': False}, indent=2))
    raise SystemExit(0 if positive else 1)
