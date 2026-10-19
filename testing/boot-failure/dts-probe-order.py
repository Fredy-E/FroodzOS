#!/usr/bin/env python3
"""Decompile the Slim 3 DTB and list /soc children in DT order around the interconnects."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
out = '/home/builder/boot-failure-tests/slim3.dts'
r = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-o', out, DTB],
                   capture_output=True, text=True)
print('DTC_EXIT', r.returncode, r.stderr[-500:] if r.stderr else '')
text = open(out, errors='replace').read()
print('DTS_BYTES', len(text))
# find soc@0 node children with unit addresses, in file order
m0 = re.search(r'^\t(soc@0)\s*\{', text, re.M)
print('SOC_MATCH', m0.group(0) if m0 else None)
start = m0.start() if m0 else -1
print('SOC_START', start)
depth = 0
in_soc = False
children = []
for i, line in enumerate(text.splitlines()):
    if 'soc {' in line and '@' not in line and 'soc:' not in line and i < soc // 80 + 5:
        pass
# simpler: regex top-level nodes with unit address inside soc block
start = text.find('\tsoc {')
if start < 0:
    start = text.find('soc {')
print('SOC_START', start)
# walk braces
pos = text.find('{', start)
depth = 1
p = pos + 1
top_children = []
cur = ''
while depth > 0 and p < len(text):
    c = text[p]
    if c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
    p += 1
block = text[start:p]
# top-level children: lines with exactly 2 tabs + name@addr {
for m in re.finditer(r'^\t\t([A-Za-z0-9_,.\-]+@([0-9a-fA-F]+))\s*\{', block, re.M):
    top_children.append((m.group(1), m.group(2)))
print('SOC_CHILD_COUNT', len(top_children))
for name, addr in top_children:
    print(f'{addr} {name}')
