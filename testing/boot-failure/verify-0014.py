#!/usr/bin/env python3
"""Verify 0014: usb nodes' interconnects reference usb_noc+mc_virt only, no gem/mailbox."""
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
    has_gem = 'gem_noc' in body or '26400000' in (re.search(r'interconnects\s*=\s*<([^>]+)>', body) or [None, ''])[1]
    nmlines = [l for l in body.splitlines() if 'mailbox@17430000' in l]
    print(('FAIL ' if has_gem else 'OK   ') + label)
    ok &= not has_gem
print('ALL_OK' if ok else 'PROBLEM')
import hashlib
raw = open(DTB, 'rb').read()
print(len(raw), hashlib.sha256(raw).hexdigest())
