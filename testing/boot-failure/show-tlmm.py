#!/usr/bin/env python3
"""What does the tlmm node reference (why would it defer)?"""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
m = re.search(r'tlmm:\s*pinctrl@f100000\s*\{(.*?)\n\t\t\};', dts, re.S)
print(m.group(0)[:900] if m else 'TLMM NODE NOT FOUND')
