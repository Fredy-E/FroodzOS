#!/usr/bin/env python3
"""Resolve phandles 0x17/0x18 to node names."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
for ph in ('0x17', '0x18'):
    for m in re.finditer(r'([\w-]+:\s*)?([\w.-]+@[\w]+)\s*\{[^}]*?phandle\s*=\s*<' + ph + r'>', dts, re.S):
        print(ph, '->', (m.group(1) or '').strip(), m.group(2))
