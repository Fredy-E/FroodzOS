#!/usr/bin/env python3
"""Per-USB-node pair0 + names for the 0011 override."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
for label, addr in [('usb_2', 'a200000'), ('usb_mp', 'a400000'),
                    ('usb_1_ss0', 'a600000'), ('usb_1_ss1', 'a800000')]:
    m = re.search(label + r':\s*usb@' + addr + r'\s*\{(.*?)\n\t\t\};', dts, re.S)
    body = m.group(1) if m else ''
    icc = re.search(r'interconnects\s*=\s*<([^>]+)>', body)
    names = re.search(r'interconnect-names\s*=\s*([^;]+);', body)
    cells = icc.group(1).split() if icc else []
    print(f'{label}: ncells={len(cells)} pair0={" ".join(cells[:6])} names={names.group(1) if names else "?"}')
