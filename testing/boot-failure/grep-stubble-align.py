#!/usr/bin/env python3
"""Locate stubble loader code paths: kernel placement, alignment, DTB/hwid."""
import re
from pathlib import Path
roots = list(Path('/home/builder/src').glob('stubble-*'))
print('STUBBLE_ROOTS', [str(r) for r in roots])
for root in roots:
    if not root.is_dir():
        continue
    for pat in ['*.c', '*.h', '*.rs', '*.py', 'stubblify*']:
        for f in root.rglob(pat):
            if '.git' in f.parts:
                continue
            try:
                text = f.read_text(errors='replace')
            except OSError:
                continue
            hits = [(i + 1, line) for i, line in enumerate(text.splitlines())
                    if re.search(r'align|AllocatePages|CopyMem|LoadImage|StartImage|TEXT_OFFSET|0x10000|65536|relocat|ReserveMemory|memory.?map', line, re.I)]
            if hits:
                print(f'\nFILE {f.relative_to(root)} ({len(text.splitlines())} lines, {len(hits)} hits)')
                for ln, line in hits[:60]:
                    print(f'  {ln}: {line.strip()[:160]}')
