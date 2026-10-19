#!/usr/bin/env python3
"""Read back frozen runtime closure independently; no GUI or fixture mutation."""
import datetime
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

T = Path(__file__).resolve().parent
B = Path('/home/builder/boot-failure-tests')
BASE = B / 'dt26-runtime-closure-complete-20261018T160700Z'
ROOT = Path(str(BASE) + '-root')
SFS = Path('/home/builder/live-rootfs-v2.squashfs')
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
REPORT = T / ('dt26-parent-runtime-verification-' + TAG + '.json')
CLEAN = {'PATH': '/usr/bin:/bin', 'HOME': '/', 'LANG': 'C'}


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=45, env=CLEAN)
    return {'command': args, 'rc': p.returncode, 'stdout': p.stdout[-5000:], 'stderr': p.stderr[-1000:]}


with REPORT.open('x') as stream, (B / 'dt25-build.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    evidence_files = [Path(str(BASE) + '.json'), Path(str(BASE) + '-evidence.json')]
    receipts = {p.name: json.loads(p.read_text()) for p in evidence_files}
    programs = ['/usr/bin/chvt', '/usr/bin/timeout', '/usr/bin/loginctl', '/usr/bin/systemctl',
                '/usr/bin/dbus-run-session', '/usr/bin/sddm', '/usr/bin/kwin_wayland',
                '/usr/bin/startplasma-wayland', '/usr/bin/bash', '/usr/bin/python3.14']
    pam = sorted('/' + str(p.relative_to(ROOT)) for p in (ROOT / 'usr/lib/security').glob('pam_*.so'))
    loader = '/usr/lib/ld-linux-aarch64.so.1'
    checks = [run(['/usr/bin/chroot', str(ROOT), loader, '--inhibit-cache', '--list', p])
              for p in programs + pam]
    pycode = ('import argparse,json,os,signal,subprocess,sys,time,pathlib,re,stat,tempfile,errno,importlib.util;'
              ' print(json.dumps({"python":sys.version,"os_file":os.__file__,"isolated":sys.flags.isolated,"no_site":sys.flags.no_site,"no_bytecode":sys.dont_write_bytecode}))')
    python = run(['/usr/bin/chroot', str(ROOT), '/usr/bin/python3.14', '-I', '-S', '-B', '-c', pycode])
    bash = run(['/usr/bin/chroot', str(ROOT), '/usr/bin/bash', '--noprofile', '--norc', '-c',
                'declare -p BASH_VERSION BASH_MONOSECONDS SECONDS'])
    greeter = run(['/usr/bin/chroot', str(ROOT), loader, '--inhibit-cache', '--list', '/usr/bin/sddm-greeter'])
    byte_checks = []
    for relative in ['usr/bin/sddm', 'usr/bin/kwin_wayland', 'usr/lib/ld-linux-aarch64.so.1']:
        p = subprocess.run(['/usr/bin/unsquashfs', '-cat', str(SFS), relative],
                           capture_output=True, check=True, timeout=45, env=CLEAN)
        actual = ROOT / relative
        source_sha = hashlib.sha256(p.stdout).hexdigest()
        staged_sha = hashlib.sha256(actual.read_bytes()).hexdigest()
        byte_checks.append({'path': relative, 'bytes': len(p.stdout), 'source_sha256': source_sha,
                            'staged_sha256': staged_sha, 'equal': source_sha == staged_sha})
    candidate = run(['/usr/bin/unsquashfs', '-ll', '-p', '2', str(SFS), 'usr/bin/sddm-greeter-qt6'])
    daemon_bytes = (ROOT / 'usr/bin/sddm').read_bytes()
    greeter_strings = sorted(set(chunk.decode('utf-8', 'replace') for chunk in daemon_bytes.split(b'\0')
                                if b'sddm-greeter' in chunk and len(chunk) < 500))
    snapshot_paths = sorted((ROOT / 'private_snapshot').glob('*.py'))
    snapshots = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot_paths}
    d_free = shutil.disk_usage('/mnt/d').free
    report = {'root': str(ROOT), 'readback_receipt_keys': {k: sorted(v) for k, v in receipts.items()},
              'loader_checks': checks, 'required_loader_count': len(checks),
              'required_loader_all_pass': all(x['rc'] == 0 for x in checks),
              'frozen_python_stdlib': python, 'frozen_bash_clock_features': bash,
              'source_byte_checks': byte_checks, 'source_bytes_all_equal': all(x['equal'] for x in byte_checks),
              'generic_greeter_known_failure': greeter,
              'qt6_greeter_presence_only': candidate, 'daemon_embedded_greeter_strings': greeter_strings,
              'snapshots_are_previous_source_revision_only': snapshots,
              'd_free_bytes': d_free, 'above_10gib_reserve': d_free > 10 * 1024**3,
              'native_graphics_validated': False, 'no_compositor_launched': True,
              'no_fixture_mutation': True}
    json.dump(report, stream, indent=2)
    fcntl.flock(lock, fcntl.LOCK_UN)
print(REPORT)
print(json.dumps({k: v for k, v in report.items() if k not in ('loader_checks',)}, indent=2))
print('LOADER_RETURN_CODES=' + json.dumps({x['command'][-1]: x['rc'] for x in checks}))
