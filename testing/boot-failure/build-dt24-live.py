#!/usr/bin/env python3
"""Build dt24 with checked subprocesses; retain the complete output."""
import json
import os
import subprocess
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
OUT = Path('/home/builder/uki-v2-dt24')
assert not OUT.exists(), 'Fresh evidence/build directory required'
for rel in ['builder/build-live-uki.sh', 'builder/diagnostics/kestrel-text-login.sh',
            'builder/diagnostics/kestrel-text-proof.sh', 'builder/diagnostics/kestrel-text-bashrc',
            'builder/initcpio/install/kestrel_text']:
    subprocess.run(['bash', '-n', str(P / rel)], check=True)
subprocess.run(['sh', '-n', str(P / 'builder/initcpio/hooks/kestrel_text')], check=True)
env = os.environ.copy()
env['OUT'] = str(OUT)
with (T / 'build-dt24-live.log').open('x') as log:
    result = subprocess.run(['bash', str(P / 'builder/build-live-uki.sh')], env=env,
                            stdout=log, stderr=subprocess.STDOUT)
result.check_returncode()
assert (OUT / 'vmlinuz-live.efi').stat().st_size > 100000000
assert (OUT / 'live-initramfs.img').stat().st_size > 100000000
print('DT24_LIVE_BUILD_COMPLETE', flush=True)
