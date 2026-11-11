#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only development metadata consistency, NEVER release qualification.

This snapshot intentionally admits only Maverick 0.1.0-dev metadata. A later
promotion requires new evidence/review, not toggling a JSON authority flag.
No installers, probes, runtime files, credentials, media or network are used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_METADATA = 128 * 1024
AUTHORITY = 'docs/releases/CODENAMES.md'
OWNER_SHA256 = '775f846fc9a15e5cd99ee272a65c1880df7aba1693dda01ab9bf6156a9e76aeb'
CURRENT = {
    'schema':'froodzos.development-release.v1', 'product':'FroodzOS',
    'release_series':'0.1', 'development_version':'0.1.0-dev',
    'codename':'Maverick', 'codename_slug':'maverick', 'target_channel':'alpha',
    'current_status':'development', 'qualified_release':None,
    'architecture':'aarch64', 'board':'lenovo-83n3', 'board_status':'experimental',
    'release_authorized':False, 'publication_authorized':False,
    'native_acceptance':False, 'build_id':None,
}
CAPABILITIES = {
    'native_boot':'native_observed', 'text_console':'native_observed',
    'keyboard_external_mouse':'owner_observed', 'wifi':'native_observed',
    'plasma_desktop':'owner_observed_software_rendering',
    'home_persistence':'accepted_different_boot', 'native_hermes':'not_accepted',
    'touchpad':'not_working', 'gpu_acceleration':'not_accepted',
    'audio_camera':'not_accepted', 'battery_power_suspend':'not_accepted',
    'type_c_pd':'not_accepted', 'safe_final_poweroff':'not_accepted',
}
BOARD = {
    'schema':'froodzos.board-profile.v1', 'id':'lenovo-83n3', 'manufacturer':'Lenovo',
    'model':'IdeaPad Slim 3 15Q8X10', 'machine_type':'83N3',
    'soc':'Snapdragon X1-26-100', 'architecture':'aarch64',
    'support_level':'experimental', 'full_hardware_acceptance':False,
    'observations_through':'2026-10-31',
    'evidence_scope':'Recorded prior owner/native evidence, not fresh hardware tests or release admission',
    'capabilities':CAPABILITIES,
}
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(?:dev|alpha|beta|rc)(?:\.[1-9][0-9]*)?)?')

class ValidationError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ValidationError(message)


def read_bounded(root, relative):
    path = Path(root) / relative
    fd = None
    try:
        require(not path.is_symlink(), 'linked metadata refused: '+relative)
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                     | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode)
                and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'nonregular/reparse metadata refused: '+relative)
        require(0 < info.st_size <= MAX_METADATA, 'metadata size refused: '+relative)
        data = bytearray()
        while len(data) <= MAX_METADATA:
            block = os.read(fd, min(8192, MAX_METADATA+1-len(data)))
            if not block:
                break
            data.extend(block)
        require(len(data) <= MAX_METADATA, 'live metadata bound exceeded: '+relative)
        return bytes(data)
    except OSError:
        raise ValidationError('metadata unavailable: '+relative) from None
    finally:
        if fd is not None:
            os.close(fd)


def read_json(root, relative):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key in '+relative)
            result[key] = value
        return result
    def constant(value):
        raise ValidationError('nonstandard JSON number in '+relative)
    try:
        return json.loads(read_bounded(root, relative).decode('utf-8'),
                          object_pairs_hook=unique, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError):
        raise ValidationError('invalid metadata JSON: '+relative) from None


def exact_snapshot(actual, expected, label):
    require(type(actual) is dict and set(actual) == set(expected), label+' fields differ')
    for key, expected_value in expected.items():
        value = actual[key]
        require(type(value) is type(expected_value), label+' field type differs: '+key)
        if type(expected_value) is dict:
            exact_snapshot(value, expected_value, label+'.'+key)
        else:
            require(value == expected_value, label+' snapshot differs: '+key)


def authority_entries(raw):
    require(hashlib.sha256(raw).hexdigest() == OWNER_SHA256,
            'owner-selected naming authority bytes differ')
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        raise ValidationError('authority is not UTF-8') from None
    pairs = re.findall(r'^\|\s*\*\*(\d+\.\d+)\*\*\s*\|\s*\*\*([^*]+)\*\*', text, re.M)
    displays = re.findall(r'^FroodzOS (\d+\.\d+) (.+?) — ARM64(?: (Alpha|Beta|RC))?\s*$', text, re.M)
    require(len(pairs) == 25 and [(v,n) for v,n,c in displays] == pairs,
            'authority table/display coverage differs')
    require(len({v for v,n in pairs}) == len({n for v,n in pairs}) == 25,
            'authority names/versions are not unique')
    return [{'series':version, 'codename':name, 'slug':name.lower().replace(' ','-'),
             'intended_stage':channel.lower() if channel else 'stable',
             'display_name':'FroodzOS '+version+' '+name+' — ARM64'+(' '+channel if channel else ''),
             'selection_status':'selected'} for version,name,channel in displays]


def codename_for(version, catalog):
    """Resolve a PRODUCT version only; never infer one from component versions."""
    require(type(version) is str, 'product version must be literal text')
    match = VERSION.fullmatch(version)
    require(match is not None, 'malformed product version; no normalization performed')
    series = match.group(1)+'.'+match.group(2)
    require(type(catalog) is dict and type(catalog.get('entries')) is list,
            'catalog unavailable')
    rows = [row for row in catalog['entries'] if type(row) is dict and row.get('series') == series]
    require(len(rows) == 1 and type(rows[0].get('codename')) is str,
            'product series is unassigned or duplicated')
    return rows[0]['codename']


def validate(root=ROOT):
    catalog = read_json(root, 'release/codenames.json')
    require(type(catalog) is dict and set(catalog) == {
        'schema','authority_document','authority_sha256','authority_role','entries'},
        'catalog schema differs')
    require(catalog['schema'] == 'froodzos.codenames.v1'
            and catalog['authority_document'] == AUTHORITY
            and type(catalog['authority_sha256']) is str
            and re.fullmatch('[0-9a-f]{64}', catalog['authority_sha256']) is not None
            and catalog['authority_sha256'] == OWNER_SHA256
            and catalog['authority_role'] == 'OWNER_SELECTED_NAMING_ONLY_NOT_RELEASE_QUALIFICATION',
            'catalog authority differs')
    expected = authority_entries(read_bounded(root, AUTHORITY))
    require(type(catalog['entries']) is list and len(catalog['entries']) == len(expected),
            'selected codename coverage differs')
    for actual, wanted in zip(catalog['entries'], expected):
        exact_snapshot(actual, wanted, 'codename '+wanted['series'])
    current = read_json(root, 'release/current.json')
    board = read_json(root, 'release/boards/lenovo-83n3.json')
    exact_snapshot(current, CURRENT, 'current development target')
    exact_snapshot(board, BOARD, 'recorded experimental board')
    require(codename_for(current['development_version'], catalog) == current['codename'],
            'product version/codename mismatch')
    return {'ok':True, 'scope':'DEVELOPMENT_METADATA_ONLY', 'codename_count':len(expected),
            'product_version':current['development_version'], 'codename':current['codename'],
            'board':board['id'], 'board_status':board['support_level'],
            'release_authorized':False, 'publication_authorized':False,
            'native_acceptance':False, 'qualification':'NOT_EVALUATED',
            'notice':'Naming/record consistency only; not hardware, package or release approval.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='read-only project metadata root')
    args = parser.parse_args(argv)
    try:
        result = validate(args.root)
    except ValidationError as exc:
        print(json.dumps({'ok':False,'scope':'DEVELOPMENT_METADATA_ONLY','error':str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
