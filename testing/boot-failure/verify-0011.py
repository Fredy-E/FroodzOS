#!/usr/bin/env python3
"""Verify 0011: gem off, no 0x36 in any dwc3 interconnects, names intact."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
ok = True
m = re.search(r'gem_noc:\s*interconnect@26400000\s*\{(.*?)\n\t\t\};', dts, re.S)
st = re.search(r'status\s*=\s*"([^"]+)"', m.group(1)).group(1) if m else '?'
print('gem:', st)
ok &= (st == 'disabled')
for label, addr in [('usb_2', 'a200000'), ('usb_mp', 'a400000'),
                    ('usb_1_ss0', 'a600000'), ('usb_1_ss1', 'a800000')]:
    m = re.search(label + r':\s*usb@' + addr + r'\s*\{(.*?)\n\t\t\};', dts, re.S)
    body = m.group(1) if m else ''
    icc = re.search(r'interconnects\s*=\s*<([^>]+)>', body)
    cells = icc.group(1) if icc else ''
    has36 = '0x36' in cells.split()
    print(('FAIL ' if has36 else 'OK   ') + f'{label}: gem-ref={has36} ncells={len(cells.split())}')
    ok &= (not has36 and len(cells.split()) == 12)
print('ALL_OK' if ok else 'PROBLEM')
