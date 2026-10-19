#!/usr/bin/env python3
"""Repair 4-backslash-n back to 2-backslash-n on A ROUNDTRIP line only."""
from pathlib import Path
p = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt26-efi-harness.py')
raw = p.read_bytes()
lines = raw.split(b'\n')
fixed = 0
F = bytes([92, 92, 92, 92, 110])
T = bytes([92, 92, 110])
for i, ln in enumerate(lines):
    if b'KESTREL_INPUT_ROUNDTRIP' in ln:
        print('line', i + 1, 'four-bs-n count:', ln.count(F))
        assert ln.count(F) == 2
        lines[i] = ln.replace(F, T)
        fixed += 1
assert fixed == 1
p.write_bytes(b'\n'.join(lines))
print('repaired')
