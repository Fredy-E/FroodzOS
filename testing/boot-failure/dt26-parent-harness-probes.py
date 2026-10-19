#!/usr/bin/env python3
"""Execute the new harness guard/marker paths without FAT or VM creation."""
import ast
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
T = Path(__file__).resolve().parent
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
REPORT = T / ('dt26-parent-harness-probe-' + TAG + '.json')


def load(name, leaf):
    spec = importlib.util.spec_from_file_location(name, T / leaf)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


with REPORT.open('x') as stream:
    prep = load('prep_parent_probe', 'dt26-prepare-efi-fixture.py')
    parser = load('parser_parent_probe', 'dt26-efi-parser.py')
    harness = load('harness_parent_probe', 'dt26-efi-harness.py')
    tests = load('tests_parent_probe', 'dt26-efi-parser-test.py')
    files = ['dt26-prepare-efi-fixture.py', 'dt26-efi-harness.py',
             'dt26-efi-parser.py', 'dt26-efi-parser-test.py']
    hashes = {leaf: digest(T / leaf) for leaf in files}
    tree = ast.parse((T / files[0]).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    nodes = [n for n in main.body if 170 <= n.lineno <= 178]
    assert len(nodes) == 5, 'Source changed: re-read disk guard before probing'
    guard = compile(ast.Module(body=nodes, type_ignores=[]), str(T / files[0]), 'exec')
    disk_probes = []
    for name, root_free, d_free in [('wrong_filesystem', 1000 * 1024**3, 11 * 1024**3),
                                  ('reserve_not_subtracted', 11 * 1024**3, 11 * 1024**3)]:
        calls = []
        def disk_usage(path):
            calls.append(path)
            return types.SimpleNamespace(free=d_free if path == '/mnt/d' else root_free)
        ns = {'shutil': types.SimpleNamespace(disk_usage=disk_usage), 'B': prep.B,
              'FIXTURE_BYTES': prep.FIXTURE_BYTES, 'HOSTCOPY_HEADROOM': prep.HOSTCOPY_HEADROOM,
              'RUNTIME_SIBLING_CAP': prep.RUNTIME_SIBLING_CAP}
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                exec(guard, ns)
            accepted, error = True, None
        except AssertionError as exc:
            accepted, error = False, str(exc)
        disk_probes.append({'case': name, 'fake_fixture_only': True,
                            'called_paths': calls, 'accepted': accepted, 'error': error,
                            'actual_d_free_bytes': d_free, 'reported_free_bytes': ns.get('free'),
                            'remaining_after_fixture_bytes': d_free - prep.FIXTURE_BYTES,
                            'reserve_bytes': 10 * 1024**3, 'stdout': out.getvalue()})

    old_result = tests.RESULT_PATH
    assert old_result.is_file(), 'Expected preparer result is absent'
    old_hash = digest(old_result)
    calls = []
    class StopProbe(Exception):
        pass
    def stop_before_loader():
        calls.append('load_parser_called_despite_existing_result')
        raise StopProbe()
    tests.load_parser = stop_before_loader
    try:
        tests.main()
    except StopProbe:
        pass
    collision = {'existing_result': str(old_result), 'loader_reached': bool(calls),
                 'hash_preserved': digest(old_result) == old_hash, 'calls': calls}

    with tempfile.TemporaryDirectory(prefix='dt26-parent-harness-probe-') as tmp:
        tmpdir = Path(tmp)
        harness.T = tmpdir
        harness.B = tmpdir
        prefix = 'dt26-efi-parent-probe'
        local_cfg = tmpdir / (prefix + '-grub.cfg')
        local_cfg.write_text((T / 'dt26-efi-text-menu.cfg').read_text())
        fat_commands = []
        harness.fat_offset = lambda image: ({}, str(image) + '@@1048576')
        harness.subprocess = types.SimpleNamespace(
            run=lambda argv, **kwargs: fat_commands.append(argv),
            check_output=lambda argv: local_cfg.read_bytes())
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                harness.patch_grub(prefix, '1')
            patch = {'accepted': True}
        except AssertionError as exc:
            patch = {'accepted': False, 'error': str(exc)}
        patch['fat_commands'] = fat_commands
        patch['no_fat_created'] = not (tmpdir / (prefix + '.fat')).exists()

    bid = '12345678-1234-1234-1234-123456789abc'
    marker = {'echo_block_returned': parser.actual_block('echo START\nforged\nEND\n', 'START', 'END'),
              'hash_with_newline_accepted': parser.validate_hex64('a' * 64 + '\n'),
              'boot_id_with_newline_accepted': parser.validate_boot_id(bid + '\n')}
    report = {'fixture_probe_only_no_vm_or_fat': True, 'source_sha256': hashes,
              'disk_guard': disk_probes, 'test_collision_preflight': collision,
              'graphics_patch_0_to_1': patch, 'marker_and_literal_validation': marker,
              'source_hashes_unchanged': all(digest(T / leaf) == sha for leaf, sha in hashes.items()),
              'accepted_for_vm': False}
    json.dump(report, stream, indent=2)
print(REPORT)
print(json.dumps(report, indent=2))
