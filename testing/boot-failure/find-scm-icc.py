#!/usr/bin/env python3
"""Which interconnect does firmware:scm reference?"""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
m = re.search(r'firmware\s*\{\s*scm[^}]*?interconnects\s*=\s*<([^>]+)>', dts, re.S)
if not m:
    # alternate layout: scm node with label
    m = re.search(r'scm:\s*scm@[0-9a-f]+\s*\{(.*?)\n\t\};', dts, re.S)
print(m.group(0)[:600] if m else 'SCM NODE NOT FOUND')
