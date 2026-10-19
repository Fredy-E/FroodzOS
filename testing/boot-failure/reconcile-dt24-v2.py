#!/usr/bin/env python3
"""Reconcile only this task's v2 launcher after host timeout; preserve all files."""
import json
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
B = Path('/home/builder/boot-failure-tests')
rows = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdecimal():
        continue
    try:
        name = (entry / 'comm').read_text().strip()
        if not (name.startswith('python') or name.startswith('qemu-system')):
            continue
        argv = (entry / 'cmdline').read_bytes().split(b'\0')
        if any(b'run-dt24-validation.py' in arg or b'validate-dt24-text-boot.py' in arg or b'qemu-dt24-menu8-text-fw-off-v2.fat' in arg for arg in argv):
            rows.append({'pid': int(entry.name), 'comm': name})
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
print(json.dumps({'processes': rows, 'image_exists': (B / 'qemu-dt24-menu8-text-fw-off-v2.fat').exists(),
                  'serial_exists': (T / 'qemu-dt24-menu8-text-fw-off-v2.log').exists(),
                  'result_exists': (T / 'qemu-dt24-menu8-text-fw-off-v2-result.json').exists()}, indent=2))
