#!/usr/bin/env python3
"""Keep menu numbering while making entries 8/9 normal systemd text boots."""
import re
from pathlib import Path

T = Path(__file__).resolve().parent
source = (T / 'dt23-grub.cfg').read_text()
menu = source.replace('Kestrel diagnostic loader dt23', 'Kestrel diagnostic loader dt24')
entries = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', menu, re.M | re.S)
assert len(entries) == 11
entry8 = '''menuentry 'Kestrel dt24 - Keyboard repair + SYSTEMD TEXT (default)' {
    set gfxpayload=keep
    echo 'Normal systemd text boot; local live console only, SSH/SDDM disabled.'
    echo 'At KESTREL-TEXT# type kestrel-proof then press Enter.'
    echo 'Allow 90 seconds for logs; use poweroff for normal shutdown.'
    echo 'Bounded firmware logger retained: at most FOUR owned records.'
    linux /EFI/Linux/kestrel-live.efi kestrel_log=1 kestrel_efilog=1 rd.log=console rd.log=file archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M $platform_cmdline console=tty1 loglevel=4 panic=0 module_blacklist=dispcc_x1e80100 kestrel_textboot=1 kestrel_console=tty1 systemd.unit=multi-user.target systemd.show_status=1
    boot
}
'''
entry9 = '''menuentry 'Kestrel dt24 - SYSTEMD TEXT + verbose FW LOG (confirm)' {
    set gfxpayload=keep
    echo 'Same normal-systemd text repair with verbose kernel diagnostics.'
    echo 'Writes at most FOUR owned firmware records; existing records disarm capture.'
    echo 'Type YES to boot. At KESTREL-TEXT# enter kestrel-proof.'
    set fwconfirm=''
    read fwconfirm
    if [ "$fwconfirm" = 'YES' ]; then
        linux /EFI/Linux/kestrel-live.efi kestrel_log=1 kestrel_efilog=1 rd.log=console rd.log=file debug archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M $platform_cmdline console=tty1 loglevel=7 ignore_loglevel panic=0 initcall_debug module_blacklist=dispcc_x1e80100 kestrel_textboot=1 kestrel_console=tty1 systemd.unit=multi-user.target systemd.show_status=1
        boot
    else
        echo 'Cancelled; no kernel started.'
        sleep 3
    fi
}
'''
menu = menu.replace(entries[7], entry8, 1).replace(entries[8], entry9, 1)
new_entries = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', menu, re.M | re.S)
assert len(new_entries) == 11 and 'set default=7\n' in menu
for i, entry in enumerate(new_entries):
    if i in (7, 8):
        assert 'init=' not in entry
        for token in ['kestrel_log=1', 'kestrel_efilog=1', 'kestrel_textboot=1',
                      'kestrel_console=tty1', 'systemd.unit=multi-user.target', 'console=tty1']:
            assert token in entry
    else:
        assert entry == entries[i], 'Unrelated menu entry changed'
with (T / 'dt24-grub.cfg').open('x', newline='\n') as stream:
    stream.write(menu)
print('DT24_SYSTEMD_TEXT_MENU_PREPARED', len(menu))
