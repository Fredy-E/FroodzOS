#!/usr/bin/env python3
"""Resolve usb interconnect phandles to node names (proper map)."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
# node header + its phandle: match header line, then phandle within next 400 chars
phmap = {}
for m in re.finditer(r'(?:([\w-]+):\s*)?([\w.,-]+@[\w,]+)\s*\{', dts):
    seg = dts[m.start():m.start() + 500]
    ph = re.search(r'phandle\s*=\s*<(0x[0-9a-f]+)>', seg)
    if ph and ph.group(1) not in phmap:
        phmap[ph.group(1)] = (m.group(1) or '?') + ':' + m.group(2)
for label, addr in [('usb_1_ss2', 'a000000'), ('usb_2', 'a200000'),
                    ('usb_mp', 'a400000'), ('usb_1_ss0', 'a600000'),
                    ('usb_1_ss1', 'a800000')]:
    m = re.search(label + r':\s*usb@' + addr + r'\s*\{(.*?)\n\t\t\};', dts, re.S)
    body = m.group(1) if m else ''
    icc = re.search(r'interconnects\s*=\s*<([^>]+)>', body)
    cells = icc.group(1).split() if icc else []
    # phandles are the cells that appear in phmap and are referenced as nodes
    refs = []
    for c in cells:
        if c in phmap:
            refs.append(phmap[c].split(':')[0])
    print(label, '->', refs)
