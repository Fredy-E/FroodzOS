#!/usr/bin/env python3
"""Definitive 0008 check v2 (label-prefixed nodes)."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
want = ['pcie@1bd0000', 'pcie@1bf8000', 'pcie@1c00000', 'pcie@1c08000',
        'phy@1bd4000', 'phy@1bfc000', 'phy@1c06000', 'phy@1c0e000',
        'regulator-edp-3p3', 'regulator-misc-3p3', 'regulator-pcie3-nvme',
        'regulator-wcn-0p95', 'regulator-wcn-1p9', 'regulator-wcn-3p3',
        'regulator-wwan', 'thermal-sensor@c271000', 'thermal-sensor@c272000',
        'thermal-sensor@c273000', 'thermal-sensor@c274000',
        'phy@aec2a00', 'phy@aec5a00', 'phy@1d80000']
bad = []
for node in want:
    m = re.search(r'(?:[\w-]+:\s*)?' + re.escape(node) + r'\s*\{(.*?status\s*=\s*"[^"]+";)', dts, re.S)
    if not m:
        print('NOTFOUND', node)
        bad.append(node)
        continue
    st = re.search(r'status\s*=\s*"([^"]+)"', m.group(1)).group(1)
    print(('OK  ' if st == 'disabled' else 'FAIL'), node, '->', st)
    if st != 'disabled':
        bad.append(node)
print('BAD:', bad if bad else 'none')
