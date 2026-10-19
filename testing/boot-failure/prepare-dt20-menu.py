#!/usr/bin/env python3
"""Make the shell-first dt20 menu without changing canonical/media menus."""
import re
from pathlib import Path

T = Path(__file__).resolve().parent
source = (T / 'log-option-grub.cfg').read_text()
assert 'Kestrel diagnostic loader dt19' in source
assert len(re.findall(r'^menuentry ', source, re.M)) == 11
menu = source.replace('Kestrel diagnostic loader dt19', 'Kestrel diagnostic loader dt20')
menu = menu.replace('Kestrel dt19 - NO dispcc + FW LOG v2 (default)',
                    'Kestrel dt20 - USB dependencies + LIVE ROOT SHELL (default)')
menu = menu.replace('Kestrel dt19 - NO dispcc + FW LOG v2 (confirm)',
                    'Kestrel dt20 - LIVE ROOT SHELL + FW LOG v2 (confirm)')
entries = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', menu, re.M | re.S)
for index in (7, 8):
    entry = entries[index]
    assert entry.count('module_blacklist=dispcc_x1e80100') == 1
    changed = entry.replace('module_blacklist=dispcc_x1e80100',
                            'module_blacklist=dispcc_x1e80100 init=/usr/bin/bash')
    changed = changed.replace("    set gfxpayload=keep\n",
                              "    set gfxpayload=keep\n"
                              "    echo 'Target: USB-backed live root Bash, not an initramfs emergency shell.'\n"
                              "    echo 'No graphical login. Do not exit PID 1; use systemctl poweroff --force --force.'\n", 1)
    menu = menu.replace(entry, changed, 1)
assert menu.count('init=/usr/bin/bash') == 2
assert 'set default=7\n' in menu
with (T / 'dt20-grub.cfg').open('x') as output:
    output.write(menu)
print('DT20_SHELL_MENU_PREPARED')
