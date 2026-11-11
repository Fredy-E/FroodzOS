#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Public-build GRUB menu from the private menu v5: only entries that exist in the public image.

Entry 1 (default): touchpad-capable UKI + root image dir 'froodzos' + fz_touchpad=1.
Entry 2: fallback UKI without the interrupt-free device tree and without the touchpad driver.
Then the menu-mode submenu and the firmware return entry. Private-stick entries (original system, text recovery,
workstation, Ubuntu control) are not in the public image.
"""
import hashlib, pathlib, sys

C = pathlib.Path(r'D:\CachyOS-ARM64\maverick-dev-candidate-20261110')
src = (C / 'output' / 'grub.cfg.v5').read_bytes()
if hashlib.sha256(src).hexdigest() != 'cb726e554571304a113e5911021558dff691ee69ac00f105cca5033f77445d10':
    sys.exit('menu v5 pin mismatch')
lines = src.decode('utf-8').split('\n')
first = next(i for i, l in enumerate(lines) if l.startswith('menuentry '))
head = lines[:first]
sub0 = next(i for i, l in enumerate(lines) if l.startswith('submenu '))
tail = lines[sub0:]
KARGS = ('kestrel_log=1 rd.log=console rd.log=file archisobasedir=froodzos archisolabel=KESTREL_A64 copytoram=n '
         'cow_spacesize=512M $platform_cmdline console=tty1 loglevel=4 panic=0 module_blacklist=dispcc_x1e80100 '
         'kestrel_textboot=1 kestrel_console=tty1 kestrel_graphics=1 systemd.unit=multi-user.target '
         'systemd.show_status=1 kestrel_efilog=0')
entries = [
    "menuentry 'FroodzOS 0.1.0-dev Maverick (firmware-free build) - Wi-Fi + graphics + touchpad (default)' {",
    '    terminal_output console',
    '    set gfxpayload=keep',
    "    echo 'FroodzOS development build. Hardware firmware is NOT included: stage it first (see FIRMWARE.md).'",
    '    linux /EFI/Linux/froodzos-maverick-tp.efi ' + KARGS + ' fz_touchpad=1',
    '    boot',
    '}',
    '',
    "menuentry 'FroodzOS fallback - no touchpad driver' {",
    '    terminal_output console',
    '    set gfxpayload=keep',
    '    linux /EFI/Linux/froodzos-maverick-base.efi ' + KARGS,
    '    boot',
    '}',
]
text = '\n'.join(head + entries + tail)
text = text.replace('menu v5 (2026-11-11)', 'public-build menu (2026-11-11)', 1)
# GRUB's own small ASCII font (Arch Linux ARM grub package) instead of the private candidate's generated fonts
text = text.replace('/boot/grub/fonts/fzmono20.pf2', '/boot/grub/fonts/ascii.pf2').replace("'FZ Mono Regular 20'", "'Unifont Regular 16'")
out = C / 'output' / 'grub.cfg.public'
out.write_bytes(text.encode('utf-8'))
print('wrote', out, hashlib.sha256(text.encode('utf-8')).hexdigest())
