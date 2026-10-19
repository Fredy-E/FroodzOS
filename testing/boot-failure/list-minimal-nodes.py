#!/usr/bin/env python3
"""Find DT labels for the minimal-boot disable round (0008)."""
import re
DTS = '/home/builder/boot-failure-tests/slim3.dts'
text = open(DTS, errors='replace').read()
targets = ['pcie@1c0000', 'pcie@1bf8000', 'pcie@1c08000', 'pcie@1b00000',
           'thermal-sensor@c273000', 'hdmi-bridge', 'aux_bridge',
           'regulator-pcie3', 'regulator-wcn', 'regulator-wwan',
           'regulator-edp', 'regulator-misc', 'phy@1c0e000', 'phy@1bfc000',
           'phy@1c0c000', 'phy@1b0e000']
seen = set()
for m in re.finditer(r'(?m)^\t*([a-z0-9_]+):\s*([a-z0-9_.-]+@?[0-9a-fx]*)\s*\{', text):
    label, node = m.group(1), m.group(2)
    for t in targets:
        base = t.split('@')[0]
        if node.startswith(base) and label not in seen:
            seen.add(label)
            addr = node.split('@')[1] if '@' in node else '-'
            print(f'{label}: {node}')
print('=== qmp pcie phy nodes ===')
for m in re.finditer(r'(?m)^\t*([a-z0-9_]+):\s*phy@[0-9a-f]+\s*\{', text):
    label = m.group(1)
    seg = text[m.start():m.start() + 300]
    if 'pcie' in seg.lower() or 'qmp' in seg.lower():
        print('   ', label, '|', (re.search(r'compatible\s*=\s*([^;]+);', seg) or [None, '?'])[1][:70])
