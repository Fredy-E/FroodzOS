#!/usr/bin/env python3
"""Verify 0015: config_noc present, gem absent in usb interconnects."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
ok = True
for label, addr in [('usb_1_ss2', 'a000000'), ('usb_2', 'a200000'),
                    ('usb_mp', 'a400000'), ('usb_1_ss0', 'a600000'),
                    ('usb_1_ss1', 'a800000')]:
    m = re.search(label + r':\s*usb@' + addr + r'\s*\{(.*?)\n\t\t\};', dts, re.S)
    body = m.group(1) if m else ''
    icc = re.search(r'interconnects\s*=\s*<([^>]+)>', body)
    cells = icc.group(1).split() if icc else []
    # resolve phandle-ish cells (>=0x30 heuristic fails; instead check node refs via names below)
    print(f'{label}: ncells={len(cells)}')
# direct approach: does the decompiled usb block mention gem/mailbox nodes?
for tag in ['gem_noc', 'mailbox@17430000', 'config_noc']:
    n = len(re.findall(tag, dts))
    print(f'{tag}: {n} mentions')
import hashlib
raw = open(DTB, 'rb').read()
print(len(raw), hashlib.sha256(raw).hexdigest())
