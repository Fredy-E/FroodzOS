#!/usr/bin/env python3
"""Read-only, fail-closed preflight for a bounded simpledrm graphics experiment.

This does not set thermal trips, clocks, voltages, fans, firmware or power state.
Its 80C ceiling is a conservative experiment stop, not a platform trip policy.
A passed preflight is not proof that Plasma renders or that cooling works.
"""
import argparse
import json
import os
import re
import stat
from pathlib import Path

CARD = re.compile(r'card[0-9]+\Z')
MODE = re.compile(r'([0-9]+)x([0-9]+)\Z')
DEV = re.compile(r'([0-9]+):([0-9]+)\Z')
DRIVERS = frozenset({'simple-framebuffer', 'simpledrm'})
# Pinned kernel source: include/drm/drm_ioctl.h defines DRM_MAJOR 226.
DRM_MAJOR = 226


def evaluate_temperatures(readings, required_types, minimum_mc=5000, stop_mc=80000):
    """Require every selected SoC sensor; battery data cannot substitute."""
    try:
        if isinstance(required_types, (str, bytes)) or required_types is None:
            raise TypeError('invalid required sensor policy')
        required = set(required_types)
    except TypeError:
        return {'ok': False, 'errors': ['empty_or_invalid_required_sensor_policy'], 'maximum_mc': None, 'sensors': {}}
    errors = []
    values = {}
    seen = set()
    if not required or any(not isinstance(name, str) or not name or len(name) > 128 for name in required):
        errors.append('empty_or_invalid_required_sensor_policy')
    if type(minimum_mc) is not int or type(stop_mc) is not int or not 0 < minimum_mc < stop_mc <= 80000:
        return {'ok': False, 'errors': ['invalid_temperature_limits'], 'maximum_mc': None, 'sensors': {}}
    if not isinstance(readings, (list, tuple)):
        errors.append('invalid_temperature_readings')
        errors.extend('missing_sensor:' + str(name) for name in sorted((required - seen), key=repr))
        return {'ok': False, 'errors': errors, 'maximum_mc': None, 'sensors': values}
    for reading in readings:
        if not isinstance(reading, dict):
            errors.append('invalid_temperature_entry')
            continue
        try:
            name = reading.get('type')
            in_required = name in required
        except TypeError:
            errors.append('invalid_temperature_entry')
            continue
        if not in_required:
            continue
        if name in seen:
            errors.append('duplicate_sensor:' + str(name))
        seen.add(name)
        value = reading.get('temp_mc')
        if type(value) is not int or not minimum_mc <= value <= 125000:
            errors.append('invalid_temperature:' + str(name))
            continue
        values[name] = value
        if value >= stop_mc:
            errors.append('experiment_temperature_limit:' + str(name))
    errors.extend('missing_sensor:' + str(name) for name in sorted((required - seen), key=repr))
    return {'ok': not errors, 'errors': errors,
            'maximum_mc': max(values.values()) if values else None, 'sensors': values}


def evaluate_drm(snapshot):
    errors = []
    if not isinstance(snapshot, dict):
        return {'ok': False, 'errors': ['invalid_drm_snapshot']}
    card = snapshot.get('card', '')
    if not isinstance(card, str) or not CARD.fullmatch(card):
        errors.append('invalid_drm_card')
    driver = snapshot.get('driver')
    if not isinstance(driver, str) or driver not in DRIVERS:
        errors.append('not_the_simpledrm_fallback')
    if snapshot.get('character_device') is not True:
        errors.append('missing_drm_character_device')
    connectors = snapshot.get('connectors', [])
    if not isinstance(connectors, list):
        errors.append('invalid_drm_connectors')
        connectors = []
    usable = False
    for connector in connectors:
        if not isinstance(connector, dict):
            errors.append('invalid_drm_connector')
            continue
        if connector.get('status') != 'connected':
            continue
        modes = connector.get('modes', [])
        if not isinstance(modes, list):
            errors.append('invalid_drm_modes')
            continue
        for mode in modes:
            if not isinstance(mode, str) or len(mode) > 32:
                continue
            try:
                match = MODE.fullmatch(mode)
            except re.error:
                continue
            if match:
                try:
                    sizes = [int(size) for size in match.groups()]
                except ValueError:
                    continue
                if all(0 < size <= 8192 for size in sizes):
                    usable = True
    if not usable:
        errors.append('no_connected_output_with_valid_mode')
    return {'ok': not errors, 'errors': errors}


def _small_text(path, limit=128):
    try:
        path = Path(path)
        if path.is_symlink():
            return None
        with path.open(encoding='ascii') as stream:
            text = stream.read(limit + 1)
        return text.strip() if len(text) <= limit else None
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return None


def _devices_anchor_for_class(root_p, class_name):
    """Canonical sys/devices anchor for a sys/class/<name> root, else None.

    Explicit and safe: requires the literal suffix sys/class/<class_name> with
    no symlink at the class root or its sys parent. Fixtures without that
    suffix (older synthetic regular-directory roots) yield None, in which case
    symlink entries stay rejected while regular directories still work. Never a
    magic /tmp allowlist.
    """
    try:
        rp = Path(root_p)
    except (TypeError, ValueError, RuntimeError):
        return None
    try:
        if rp.is_symlink():
            return None
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        if rp.name != class_name:
            return None
        class_dir = rp.parent
        if class_dir.name != 'class':
            return None
        sys_dir = class_dir.parent
        if sys_dir.name != 'sys':
            return None
        try:
            if sys_dir.is_symlink():
                return None
        except (OSError, ValueError, RuntimeError):
            return None
        anchor = sys_dir / 'devices'
        return anchor.resolve(strict=True)
    except (OSError, ValueError, RuntimeError):
        return None


def _approved_link_target(link, anchor):
    """Canonical target of a class symlink constrained under anchor, else None."""
    try:
        if anchor is None:
            return None
        target = link.resolve(strict=True)
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        if not target.is_dir():
            return None
        try:
            target.relative_to(anchor)
        except ValueError:
            return None
        if target.name != link.name:
            return None
        return target
    except (OSError, ValueError, RuntimeError):
        return None


def _approved_card_target(link, anchor, card):
    """Canonical card target constrained under sys/devices with drm ancestry."""
    target = _approved_link_target(link, anchor)
    if target is None:
        return None
    try:
        if target.name != card:
            return None
        if target.parent.name != 'drm':
            return None
        return target
    except (OSError, ValueError, RuntimeError):
        return None


def collect_temperatures(root, required_types):
    try:
        if isinstance(required_types, (str, bytes)) or required_types is None:
            return []
        wanted = set(required_types)
    except TypeError:
        return []
    try:
        root_p = Path(root)
    except (TypeError, ValueError):
        return []
    try:
        if root_p.is_symlink():
            return []
    except (OSError, ValueError, RuntimeError):
        return []
    try:
        zones = sorted(root_p.glob('thermal_zone[0-9]*'))
    except (OSError, ValueError, RuntimeError, TypeError):
        return []
    anchor = _devices_anchor_for_class(root_p, 'thermal')
    readings = []
    for zone in zones:
        try:
            is_link = zone.is_symlink()
        except (OSError, ValueError, RuntimeError):
            continue
        zone_read = zone
        if is_link:
            approved = _approved_link_target(zone, anchor)
            if approved is None:
                continue
            zone_read = approved
        name = _small_text(zone_read / 'type')
        try:
            if name not in wanted:
                continue
        except TypeError:
            continue
        text = _small_text(zone_read / 'temp')
        value = int(text) if text is not None and re.fullmatch(r'[+-]?[0-9]+', text) else None
        readings.append({'type': name, 'temp_mc': value})
    return readings


def _sysfs_dev_identity(root_p, card):
    text = _small_text(root_p / card / 'dev', 32)
    if text is None:
        return None
    match = DEV.fullmatch(text)
    if not match:
        return None
    try:
        return (int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def _node_identity(node):
    try:
        if node.is_symlink():
            return None
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        st = node.stat()
    except (OSError, ValueError, RuntimeError):
        return None
    try:
        if not stat.S_ISCHR(st.st_mode):
            return None
        return (os.major(st.st_rdev), os.minor(st.st_rdev))
    except (AttributeError, OSError, ValueError, OverflowError):
        return None


def collect_drm(root, device_root, card='card0'):
    data = {'card': card, 'driver': None, 'character_device': False, 'connectors': []}
    if not isinstance(card, str) or not CARD.fullmatch(card):
        return data
    try:
        root_p, device_p = Path(root), Path(device_root)
    except (TypeError, ValueError):
        return data
    try:
        if root_p.is_symlink() or device_p.is_symlink():
            return data
    except (OSError, ValueError, RuntimeError):
        return data
    anchor = _devices_anchor_for_class(root_p, 'drm')
    try:
        card_path = root_p / card
    except (TypeError, ValueError, RuntimeError):
        return data
    try:
        card_is_link = card_path.is_symlink()
    except (OSError, ValueError, RuntimeError):
        return data
    card_real = None
    if card_is_link:
        card_real = _approved_card_target(card_path, anchor, card)
        if card_real is None:
            return data
    else:
        try:
            if not card_path.is_dir():
                card_real = None
            else:
                card_real = card_path
        except (OSError, ValueError, RuntimeError):
            card_real = None
    try:
        card_canon = card_real.resolve(strict=True) if card_real is not None else None
    except (OSError, ValueError, RuntimeError):
        card_canon = None
    if card_real is not None:
        try:
            data['driver'] = (card_real / 'device/driver').resolve(strict=True).name
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            node_id = _node_identity(device_p / card)
            # Canonical card dir is already approved; read dev directly.
            # Leaf symlinks stay rejected via _small_text.
            sysfs_id = None
            text = _small_text(card_real / 'dev', 32)
            if text is not None:
                match = DEV.fullmatch(text)
                if match:
                    try:
                        sysfs_id = (int(match.group(1)), int(match.group(2)))
                    except ValueError:
                        sysfs_id = None
            if node_id is not None and sysfs_id is not None and node_id == sysfs_id and node_id[0] == DRM_MAJOR:
                data['character_device'] = True
        except (OSError, ValueError, RuntimeError):
            pass
    try:
        matches = sorted(root_p.glob(card + '-*'))
    except (OSError, ValueError, RuntimeError):
        matches = []
    for connector in matches:
        try:
            is_link = connector.is_symlink()
        except (OSError, ValueError, RuntimeError):
            continue
        conn_read = connector
        if is_link:
            if card_canon is None or anchor is None:
                continue
            try:
                target = connector.resolve(strict=True)
            except (OSError, ValueError, RuntimeError):
                continue
            try:
                if not target.is_dir():
                    continue
                if target.name != connector.name:
                    continue
                try:
                    target.relative_to(card_canon)
                except ValueError:
                    continue
                conn_read = target
            except (OSError, ValueError, RuntimeError):
                continue
        modes = _small_text(conn_read / 'modes', 4096)
        data['connectors'].append({'status': _small_text(conn_read / 'status'),
                                   'modes': modes.splitlines() if modes else []})
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sensor', action='append', required=True, help='Exact SoC thermal-zone type; repeat for every required sensor')
    parser.add_argument('--card', default='card0')
    parser.add_argument('--thermal-root', type=Path, default=Path('/sys/class/thermal'))
    parser.add_argument('--drm-root', type=Path, default=Path('/sys/class/drm'))
    parser.add_argument('--device-root', type=Path, default=Path('/dev/dri'))
    args = parser.parse_args()
    required = set(args.sensor)
    readings = collect_temperatures(args.thermal_root, required)
    drm_snapshot = collect_drm(args.drm_root, args.device_root, args.card)
    thermal = evaluate_temperatures(readings, required)
    drm = evaluate_drm(drm_snapshot)
    result = {'passed': thermal['ok'] and drm['ok'], 'thermal': thermal, 'drm': drm,
              'drm_snapshot': drm_snapshot, 'native_graphics_validated': False,
              'read_only_preflight': True}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
