#!/usr/bin/env python3
"""Compare gem_noc vs cnoc_main (survivor) suppliers."""
import re
dts = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read()
for pat, tag in [(r'interconnect@1500000\s*\{(.*?)\n\t\t\};', 'cnoc_main'),
                 (r'interconnect@26400000\s*\{(.*?)\n\t\t\};', 'gem_noc')]:
    m = re.search(pat, dts, re.S)
    body = m.group(1) if m else ''
    print('=====', tag)
    for key in ('compatible', 'clocks', 'power-domains', 'required-opps',
                'interconnects', 'qcom,bcm-voters', 'operating-points',
                'status'):
        for line in body.splitlines():
            if key in line:
                print('  ', line.strip()[:130])
