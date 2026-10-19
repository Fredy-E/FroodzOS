#!/usr/bin/env python3
"""Independently verify dt25b bytes and parser under fresh parent paths.

Never invokes the prepared parser test's destructive default output path.
No QEMU, media, services, sysfs, firmware or rootfs mutation.
"""
import ast
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
NEW = Path('/home/builder/uki-v2-dt25b')
OLD = Path('/home/builder/uki-v2-dt24')
FAILED = Path('/home/builder/uki-v2-dt25')
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RESULT = T / f'dt25b-parent-{STAMP}-verification.json'
PARSER_RESULT = T / f'dt25b-efi-parent-{STAMP}-parser.json'
PARSER_LOG = T / f'dt25b-efi-parent-{STAMP}-parser.log'
for target in (RESULT, PARSER_RESULT, PARSER_LOG):
    if target.exists():
        raise FileExistsError(target)

# Reuse only our independently authored PE reader functions, never the build
# auditor's top-level code or output-generating side effects.
helper = ast.parse((T / 'dt25-parent-integration-probe.py').read_text())
nodes = [n for n in helper.body if isinstance(n, ast.FunctionDef)
         and n.name in ('digest', 'pe_section_hashes')]
assert len(nodes) == 2
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'parent-pe-reader', 'exec'))

with (B / 'dt25-build.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    a = json.loads((T / 'dt25b-artifact-audit.json').read_text())
    expected = 'b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753'
    assert re.fullmatch(r'[0-9a-f]{64}', expected)
    new_sections = pe_section_hashes(NEW / 'vmlinuz-live.efi')
    old_sections = pe_section_hashes(OLD / 'vmlinuz-live.efi')
    sources = a['sources']
    assert len(sources) >= 17
    assert 'builder/diagnostics/kestrel-graphics.service' in sources
    assert 'builder/diagnostics/kestrel-graphics-sddm.service' in sources
    for name in sources:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    checks = {
        'audit_revision': a['revision'] == 'v2-dt25b',
        'audit_packing_passed': a['passed'] is True and a['packing_provenance'] == 'passed',
        'new_uki_sha': digest(NEW / 'vmlinuz-live.efi') == expected == a['uki_sha256'],
        'host_copy_sha': digest(T / 'dt25b-candidate.efi') == expected,
        'new_uki_bytes': (NEW / 'vmlinuz-live.efi').stat().st_size == 244424704 == a['uki_bytes'],
        'initrd_sha': digest(NEW / 'live-initramfs.img') == a['initramfs_sha256'] == new_sections['.initrd']['sha256'],
        'accepted_dtb': new_sections['.dtbauto']['sha256'] == 'f5f67c13bdfe975998b083ac06465c36231c0bae205e8e60fff99832264f5232',
        'accepted_kernel': new_sections['.linux']['sha256'] == '682273a91f2016b9d5484857639bd043e021b961d7f4cfd385a09566b2df3abc',
        'old_dt24_uki_preserved': digest(OLD / 'vmlinuz-live.efi') == '4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02',
        'failed_9c_uki_preserved': digest(FAILED / 'vmlinuz-live.efi') == '9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb',
        'sfs_preserved': digest(P / 'live-staging-v2/arch/aarch64/airootfs.sfs') == '5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c',
        'source_snapshots_match': all(digest(P / rel) == item['sha256'] for rel, item in sources.items()),
    }
    for name in ('.linux', '.text', '.hwids', '.cmdline', '.uname'):
        checks['baseline_' + name] = new_sections[name] == old_sections[name]
    with tempfile.TemporaryDirectory(dir=B, prefix='dt25b-parent-packed-') as tmp:
        ex = Path(tmp)
        subprocess.run(['lsinitcpio', '-x', str(NEW / 'live-initramfs.img')], cwd=ex, check=True, capture_output=True)
        parent = (ex / 'etc/kestrel-graphics-service').read_bytes()
        child = (ex / 'etc/kestrel-graphics-sddm').read_bytes()
        checks['packed_parent_matches_reviewed_source'] = parent == (P / 'builder/diagnostics/kestrel-graphics.service').read_bytes()
        checks['packed_child_matches_reviewed_source'] = child == (P / 'builder/diagnostics/kestrel-graphics-sddm.service').read_bytes()
        checks['packed_lifetime_binding'] = b'BindsTo=kestrel-graphics.service\n' in child
        command = b'/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed\n'
        checks['packed_pre_cleanup'] = b'ExecStartPre=' + command in parent
        checks['packed_post_cleanup'] = b'ExecStopPost=' + command in parent
    baseline = json.loads((T / 'dt25-integration-fix-00-preserved-baseline-20261018T081521Z.json').read_text())
    preserved = {name: digest(T / name) == item['sha256'] for name, item in baseline['files'].items()}
    checks['old_archives_preserved'] = len(preserved) == 7 and all(preserved.values())

# Independent parser rerun with a new unique output selected BEFORE main.
# This safely avoids its known, not-yet-fixed unlink of the default archive.
old_parser_hash = digest(T / 'dt25b-efi-parser-test-result.json')
spec = importlib.util.spec_from_file_location('dt25b_parent_parser_tests', T / 'dt25b-efi-parser-test.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
mod.RESULT_PATH = PARSER_RESULT
parser_exit = 0
captured = io.StringIO()
with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
    try:
        mod.main()
    except SystemExit as exc:
        parser_exit = int(exc.code or 0)
with PARSER_LOG.open('x') as stream:
    stream.write(captured.getvalue())
parser_report = json.loads(PARSER_RESULT.read_text()) if PARSER_RESULT.exists() else {'missing': True}
checks['original_parser_archive_preserved'] = digest(T / 'dt25b-efi-parser-test-result.json') == old_parser_hash
report = {
    'provenance_passed': all(checks.values()),
    'checks_passed': sum(checks.values()),
    'checks_total': len(checks),
    'checks': checks,
    'old_archives_preserved': preserved,
    'uki_sha256': expected,
    'pe_sections': new_sections,
    'parser_exit': parser_exit,
    'parser_report': parser_report,
    'parser_result': str(PARSER_RESULT),
    'parser_log': str(PARSER_LOG),
    'unsafe_default_parser_output_workaround_explicit': True,
    'harness_preflight_review_pending': 'deleg_0d758560',
    'vm_crash_gate_passed': False,
    'native_hardware_validated': False,
}
with RESULT.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps({'result_path': str(RESULT), **report}, indent=2))
raise SystemExit(0 if report['provenance_passed'] and parser_exit == 0 else 1)
