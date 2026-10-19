#!/usr/bin/env python3
"""Full usb_2 node + its dwc3 child (role properties)."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
m = re.search(r'usb_2:\s*usb@a200000\s*\{(.*?)\n\t\t\};', dts, re.S)
body = m.group(0) if m else 'NOT FOUND'
print(body[:1500])
