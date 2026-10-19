#!/usr/bin/env python3
"""Make the PID1-marked dt23 menu without changing canonical/media menus."""
import re
from pathlib import Path

T = Path(__file__).resolve().parent
source = (T / 'dt21-grub.cfg').read_text()
menu = source.replace('Kestrel diagnostic loader dt21', 'Kestrel diagnostic loader dt23')
menu = menu.replace('Kestrel dt21 - USB I2C dependency repair + LIVE ROOT SHELL (default)',
                    'Kestrel dt23 - Post-switch proof live shell (default)')
menu = menu.replace('Kestrel dt21 - LIVE ROOT SHELL + FW LOG v2 (confirm)',
                    'Kestrel dt23 - Post-switch proof live shell + FW LOG v2 (confirm)')
entries = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', menu, re.M | re.S)
assert len(entries) == 11
for index in (7, 8):
    assert entries[index].count('init=/usr/bin/bash') == 1
    menu = menu.replace(entries[index],
                        entries[index].replace('init=/usr/bin/bash',
                                              'init=/usr/local/sbin/kestrel-pid1'), 1)
assert menu.count('init=/usr/local/sbin/kestrel-pid1') == 2
assert 'init=/usr/bin/bash' not in menu
assert 'set default=7\n' in menu
with (T / 'dt23-grub.cfg').open('x') as output:
    output.write(menu)
print('DT22_SHELL_MENU_PREPARED', len(menu))
