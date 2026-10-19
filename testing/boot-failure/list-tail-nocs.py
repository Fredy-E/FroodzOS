#!/usr/bin/env python3
"""Locate tail-NoC nodes (disp/video/gem/nsp/lpass) in the decompiled Slim 3 DTS."""
import re
DTS = '/home/builder/boot-failure-tests/slim3.dts'
text = open(DTS, errors='replace').read()
# find interconnect node headers with unit addresses
for m in re.finditer(r'(?m)^\t*([a-z0-9_]+):?\s*([a-z-]+)@([0-9a-f]+)\s*\{', text):
    label, cls, addr = m.group(1), m.group(2), m.group(3)
    if cls == 'interconnect' or 'noc' in label:
        line_start = text.rfind('\n', 0, m.start())
        snippet = text[m.start():m.start() + 400]
        comp = re.search(r'compatible\s*=\s*([^;]+);', snippet)
        print(f'{label}: {cls}@{addr} :: {(comp.group(1) if comp else "?")[:80]}')
