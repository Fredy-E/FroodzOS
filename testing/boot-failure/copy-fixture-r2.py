#!/usr/bin/env python3
"""Rerun the plain-UKI systemd validation under a fresh tag (harness budget)."""
import json, shutil, subprocess
from pathlib import Path
T = Path('/home/builder/boot-failure-tests')
P = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
src = T / 'qemu-v2-align1-systemd.fat'
dst = T / 'qemu-v2-align1-systemd-r2.fat'
if dst.exists():
    raise SystemExit('refusing overwrite')
shutil.copyfile(src, dst)
print(json.dumps({'image': str(dst), 'tag': 'qemu-v2-align1-systemd-r2'}))
