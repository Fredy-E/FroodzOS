#!/usr/bin/env python3
"""Resolve every phandle inside the five usb interconnects to node names."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
# map phandle -> node header
phmap = {}
for m in re.finditer(r'(?:([\w-]+):\s*)?([\w.,-]+@[\w,]+)\s*\{([^}]*?)phandle\s*=\s*<(0x[0-9a-f]+)>', dts, re.S):
    phmap[m.group(4)] = (m.group(1) or '?') + ':' + m.group(2)
for label, addr in [('usb_1_ss2', 'a000000'), ('usb_2', 'a200000'),
                    ('usb_mp', 'a400000'), ('usb_1_ss0', 'a600000'),
                    ('usb_1_ss1', 'a800000')]:
    m = re.search(label + r':\s*usb@' + addr + r'\s*\{(.*?)\n\t\t\};', dts, re.S)
    body = m.group(1) if m else ''
    icc = re.search(r'interconnects\s*=\s*<([^>]+)>', body)
    cells = icc.group(1).split() if icc else []
    refs = sorted({c for c in cells if c.startswith('0x')})
    names = [phmap.get(c, '??' + c) for c in refs]
    print(label, '->', names)
