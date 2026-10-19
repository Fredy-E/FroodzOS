#!/usr/bin/env python3
"""Independent disposable proofs of residual unit-ordering/rollback risks.

No live services are started. systemd-analyze only verifies fixture units;
the hook is executed with mock mount/overlay/copy predicates and fake roots.
"""
import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
B = Path('/home/builder/boot-failure-tests')
result = {'native_hardware_validated': False, 'services_started': False}
with tempfile.TemporaryDirectory(prefix='dt25-parent-systemd-', dir=B) as tmp:
    root = Path(tmp)
    units = root / 'etc/systemd/system'
    units.mkdir(parents=True)
    stub = root / 'usr/local/sbin/kestrel-graphics-supervisor'
    stub.parent.mkdir(parents=True)
    stub.write_text('#!/bin/sh\nexit 0\n')
    stub.chmod(0o755)
    true = root / 'usr/bin/true'
    true.parent.mkdir(parents=True)
    true.write_text('#!/bin/sh\nexit 0\n')
    true.chmod(0o755)
    shutil.copyfile(P / 'builder/diagnostics/kestrel-graphics.service', units / 'kestrel-graphics.service')
    (units / 'multi-user.target').write_text('[Unit]\nDescription=Fixture multi-user\nWants=kestrel-graphics.service\n')
    for name in ['basic.target', 'sysinit.target', 'shutdown.target']:
        (units / name).write_text('[Unit]\nDescription=Fixture target\nDefaultDependencies=no\n')
    for name in ['systemd-logind.service', 'dbus.service', 'systemd-user-sessions.service']:
        (units / name).write_text('[Unit]\nDescription=Fixture dependency\nDefaultDependencies=no\n[Service]\nType=oneshot\nExecStart=/usr/bin/true\n')
    proc = subprocess.run(['systemd-analyze', '--root=' + str(root), '--man=no', 'verify',
                           str(units / 'multi-user.target'), str(units / 'kestrel-graphics.service')],
                          capture_output=True, text=True, timeout=30)
    text = proc.stdout + proc.stderr
    result['ordering'] = {'checker_exit': proc.returncode,
                          'cycle_reported': 'ordering cycle' in text.lower(), 'output': text[-7000:]}
with tempfile.TemporaryDirectory(prefix='dt25-parent-rollback-', dir=B) as tmp:
    root = Path(tmp)
    sysroot, etc = root / 'sysroot', root / 'etc'
    units = sysroot / 'etc/systemd/system'
    units.mkdir(parents=True)
    etc.mkdir()
    before = {}
    for relative, source in [('usr/local/sbin/kestrel-text-login', 'kestrel-text-login.sh'),
                              ('usr/local/sbin/kestrel-text-proof', 'kestrel-text-proof.sh'),
                              ('usr/local/lib/kestrel-text-bashrc', 'kestrel-text-bashrc')]:
        path = sysroot / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((P / 'builder/diagnostics' / source).read_bytes())
        before[relative] = path.read_bytes()
    for name in ['display-manager.service', 'sddm.service', 'sshd.service', 'sshd.socket']:
        (units / name).symlink_to('/dev/null')
    env = dict(os.environ, KESTREL_SYSROOT=str(sysroot), KESTREL_ETC=str(etc))
    script = '''getarg() { printf '1\\n'; }
mountpoint() { return 0; }
findmnt() { printf 'overlay\\n'; }
cp() { return 1; }
. HOOK
run_latehook
'''.replace('HOOK', shlex.quote(str(P / 'builder/initcpio/hooks/kestrel_graphics')))
    proc = subprocess.run(['sh', '-c', script], env=env, capture_output=True, text=True, timeout=30)
    lost = [name for name, data in before.items() if not (sysroot / name).is_file() or (sysroot / name).read_bytes() != data]
    masks_lost = [name for name in ['display-manager.service', 'sddm.service', 'sshd.service', 'sshd.socket']
                  if not (units / name).is_symlink() or os.readlink(units / name) != '/dev/null']
    result['rollback'] = {'hook_exit': proc.returncode, 'lost_preexisting_helpers': lost,
                          'lost_preexisting_masks': masks_lost, 'output': (proc.stdout + proc.stderr)[-1000:]}
print(json.dumps(result, indent=2))
