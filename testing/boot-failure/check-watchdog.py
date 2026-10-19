#!/usr/bin/env python3
"""Check firmware watchdog nodes in the Slim 3 DTB and driver availability."""
import re
import subprocess
DTS = '/home/builder/boot-failure-tests/slim3.dts'
text = open(DTS, errors='replace').read()
for m in re.finditer(r'(watchdog@[0-9a-f]+)\s*\{(.*?)\n\t\t\};', text, re.S):
    body = m.group(2)
    status = re.search(r'status\s*=\s*"([^"]+)"', body)
    compat = re.search(r'compatible\s*=\s*([^;]+);', body)
    print(m.group(1), '| status:', status.group(1) if status else 'okay(default)',
          '| compat:', (compat.group(1)[:120] if compat else '?'))
print('--- kernel config ---')
cfg = open('/home/builder/src/ksrc/.config').read().splitlines()
for line in cfg:
    if re.search(r'WATCHDOG|WDT', line) and ('=y' in line or '=m' in line):
        print(line)
print('--- initramfs contents: wdt modules? ---')
r = subprocess.run(['lsinitcpio', '-l', '/home/builder/uki-v2-align1/live-initramfs.img'],
                   capture_output=True, text=True)
mods = [l for l in r.stdout.splitlines() if re.search(r'wdt|watchdog', l, re.I)]
print('\n'.join(mods) if mods else 'NO_WDT_MODULES_IN_INITRAMFS')
print('--- rootfs modules present? ---')
r = subprocess.run(['ls', '/home/builder/imgroot/usr/lib/modules/7.3.0-rc3/kernel/drivers/watchdog/'],
                   capture_output=True, text=True)
print(r.stdout.strip() or r.stderr.strip())
