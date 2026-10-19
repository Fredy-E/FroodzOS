#!/usr/bin/env python3
"""Confirm the scm node lost its interconnects property."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
m = re.search(r'scm:\s*scm\s*\{(.*?)\n\t\t\};', dts, re.S)
body = m.group(1) if m else ''
print('has interconnects:', 'interconnects' in body)
print('has compatible:', 'qcom,scm-x1e80100' in body)
import hashlib
raw = open(DTB, 'rb').read()
print(len(raw), hashlib.sha256(raw).hexdigest())
