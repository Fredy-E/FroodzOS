#!/usr/bin/env python3
"""Check sync applet presence inside the built initramfs."""
import subprocess, tempfile
from pathlib import Path
img = '/home/builder/uki-v2-log4/live-initramfs.img'
with tempfile.TemporaryDirectory(dir='/home/builder/boot-failure-tests', prefix='synccheck-') as tmp:
    r = subprocess.run(['lsinitcpio', '-x', img], cwd=tmp, capture_output=True, text=True)
    print('EXTRACT_EXIT', r.returncode, r.stdout[-200:], r.stderr[-200:])
    dest = Path(tmp)
    for name in ['bin/busybox', 'usr/bin/busybox', 'usr/bin/sync', 'usr/bin/dmesg', 'usr/bin/ash', 'bin/sh']:
        p = dest / name
        if p.is_symlink():
            print(name, 'symlink ->', p.readlink())
        elif p.exists():
            print(name, 'file', p.stat().st_size)
        else:
            print(name, 'MISSING')
