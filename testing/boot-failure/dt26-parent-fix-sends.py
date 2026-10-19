#!/usr/bin/env python3
"""Repair doubled backslash-n on the A_GUEST_CMD ROUNDTRIP line (file bytes)."""
from pathlib import Path
p = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt26-efi-harness.py')
b = p.read_bytes()
BS = chr(92)
wrong = ('printf ' + BS + '"' + BS + BS + 'nKESTREL_INPUT_ROUNDTRIP' + BS + BS + 'n' + BS + '"').encode()
right = ('printf ' + BS + '"' + BS + 'nKESTREL_INPUT_ROUNDTRIP' + BS + 'n' + BS + '"').encode()
n = b.count(wrong)
print('wrong-seq occurrences:', n)
assert n == 1, 'expected exactly one corrupted line'
p.write_bytes(b.replace(wrong, right))
print('repaired')
