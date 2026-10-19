#!/usr/bin/env python3
"""Full usb node interconnect lines including names."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
m = re.search(r'usb@a200000\s*\{(.*?)\n\t\t\};', dts, re.S)
for line in (m.group(0) if m else 'NOT FOUND').splitlines():
    s = line.strip()
    if 'interconnect' in s or 'phys' in s or s.startswith('status'):
        print(s[:200])
