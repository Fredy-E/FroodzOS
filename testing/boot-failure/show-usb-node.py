#!/usr/bin/env python3
"""Dump the dwc3 USB node to list every supplier it can wait on."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
m = re.search(r'usb_a:\s*usb@a200000\s*\{(.*?)\n\t\t\};', dts, re.S)
if not m:
    m = re.search(r'usb@a200000\s*\{(.*?)\n\t\t\};', dts, re.S)
body = m.group(0) if m else 'NODE NOT FOUND'
# print refs only
for line in body.splitlines():
    s = line.strip()
    if re.match(r'(phys|clocks|resets|interconnects|power-domains|vdd|vdda|extcon|usb-role|qcom,|compatible|status|reg|interrupt)', s):
        print(s[:110])
