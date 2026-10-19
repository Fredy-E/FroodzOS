#!/usr/bin/env python3
"""Find the qnoc driver initcall symbol for initcall_blacklist diagnostics."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
# driver registration macro use
r = subprocess.run(['grep', '-rn', 'module_platform_driver\|builtin_platform_driver',
                    KSRC + '/drivers/interconnect/qcom/qnoc-x1.c'],
                   capture_output=True, text=True)
print('DRIVER_MACRO\n' + r.stdout.strip())
# init text symbols for qnoc in System.map
n = 0
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and parts[2].startswith('__initcall') is False:
        pass
    if 'qnoc' in parts[2].lower() and ('initcall' in parts[2] or 'init' in parts[2]):
        print('MAP', line.strip())
        n += 1
        if n > 30:
            break
print('--- __initcall section qnoc entries ---')
n = 0
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and parts[1] == 't' and 'qnoc' in parts[2]:
        print('MAP-T', line.strip())
        n += 1
        if n > 30:
            break
