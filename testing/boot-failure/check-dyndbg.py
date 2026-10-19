#!/usr/bin/env python3
"""Check dynamic-debug support and qnoc debug statements in source."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
cfg = {}
for line in open(KSRC + '/.config', errors='replace'):
    line = line.strip()
    if line.startswith('CONFIG_DYNAMIC_DEBUG'):
        print('CONFIG', line)
r = subprocess.run(['grep', '-rn', 'dev_dbg\|dev_vdbg\|pr_debug\|DEFINE_DYNAMIC_DEBUG',
                    KSRC + '/drivers/interconnect/qcom/qnoc-x1.c',
                    KSRC + '/drivers/interconnect/qcom/icc-rpmh.c'],
                   capture_output=True, text=True)
lines = r.stdout.strip().splitlines()
print('DEBUG_STMTS', len(lines))
for l in lines[:40]:
    print('   ', l[:150])
