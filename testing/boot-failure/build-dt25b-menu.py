#!/usr/bin/env python3
"""Build dt25b native menu: dt24-grub.cfg + one text-first dt25b entry, default -> new entry.
Firmware capture OFF (slots occupied); graphics explicitly 0; all old entries byte-identical.
LF only; fresh exclusive output.
"""
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
SRC = T / 'dt24-grub.cfg'
OUT = T / 'dt25b-grub.cfg'
assert not OUT.exists(), 'refusing: output exists %s' % OUT
src = SRC.read_bytes()
assert b'\r' not in src, 'expected LF-only source'
text = src.decode('utf-8')
assert text.count('menuentry ') == 11, text.count('menuentry ')
assert '\nset default=7\n' in text

entry = (
    "menuentry 'Kestrel dt25b - SYSTEMD TEXT + TSENS check (default)' {\n"
    "    set gfxpayload=keep\n"
    "    echo 'Normal systemd text boot on dt25b image; local live console only, SSH/SDDM disabled.'\n"
    "    echo 'Firmware capture is OFF (slots occupied); USB file logging stays on.'\n"
    "    echo 'At KESTREL-TEXT# type kestrel-proof then press Enter.'\n"
    "    echo 'Allow 90 seconds for logs; use poweroff for normal shutdown.'\n"
    "    linux /EFI/Linux/kestrel-live.efi kestrel_log=1 rd.log=console rd.log=file archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M $platform_cmdline console=tty1 loglevel=4 panic=0 module_blacklist=dispcc_x1e80100 kestrel_textboot=1 kestrel_console=tty1 kestrel_graphics=0 systemd.unit=multi-user.target systemd.show_status=1\n"
    "    boot\n"
    "}\n"
)
anchor = "menuentry 'Kestrel v2 - slow print (EXPERIMENTAL, may remain at logo)' {"
assert text.count(anchor) == 1
text = text.replace(anchor, entry + anchor)
text = text.replace('\nset default=7\n', '\nset default=9\n', 1)
assert text.count('menuentry ') == 12
assert '\nset default=9\n' in text
# every old line preserved in order, except the intentional default change
old_lines = src.decode('utf-8').splitlines()
new_lines = text.splitlines()
oi = 0
for nl in new_lines:
    if oi < len(old_lines) and nl == old_lines[oi]:
        oi += 1
    elif oi < len(old_lines) and old_lines[oi] == 'set default=7' and nl == 'set default=9':
        oi += 1
assert oi == len(old_lines), (oi, len(old_lines))
OUT.write_bytes(text.encode('utf-8'))
print('MENU_BUILT bytes=%d entries=12 default=9' % len(text.encode()))
