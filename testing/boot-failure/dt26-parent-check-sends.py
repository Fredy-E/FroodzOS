#!/usr/bin/env python3
"""Parent check: A_GUEST_CMD runtime bytes after parent edit (newline contract)."""
import ast
from pathlib import Path
src = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt26-efi-harness.py').read_text()
out = {}
for name in ('A_GUEST_CMD', 'BC_PHASE1_SEND', 'BC_JOURNAL_SEEN_SEND'):
    i = src.find(name + ' = (')
    if i < 0:
        i = src.find(name + ' = "')
        j = src.find('\n', i)
        out[name] = ast.literal_eval(src[src.find('"', i):j])
        continue
    depth = 0
    j = src.find('(', i)
    k = j
    while True:
        if src[k] == '(':
            depth += 1
        elif src[k] == ')':
            depth -= 1
        if depth == 0:
            break
        k += 1
    out[name] = ast.literal_eval(src[j:k + 1])
a = out['A_GUEST_CMD']
b = out['BC_PHASE1_SEND']
print('A endswith real newline:', a.endswith('\n'))
print('A BOOTID echo present:', 'echo BOOTID=$BID' in a)
print('A ROUNDTRIP segment newline-terminated:', 'KESTREL_INPUT_ROUNDTRIP\n' in a)
print('B real newline present:', '\n' in b)
print('A head:', repr(a[:160]))
print('B head:', repr(b[:120]))
