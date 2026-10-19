#!/usr/bin/env python3
import subprocess
from pathlib import Path
for file in ['/usr/bin/mkinitcpio','/usr/lib/initcpio/functions','/etc/mkinitcpio.conf','/home/builder/uki/live-mkinitcpio.conf']:
    p=Path(file);lines=p.read_text().splitlines();print('\nFILE',file)
    if file.endswith('mkinitcpio'):
        print('\n'.join(f'{i+1}: {x}' for i,x in enumerate(lines[:150])))
    for i,line in enumerate(lines):
        if '_d_library' in line or '_d_init' in line or 'build_image' in line or 'bsdcpio' in line:
            print('\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-3),min(len(lines),i+7))))
    if file.endswith('.conf'): print('\n'.join(lines))
for name in ['archiso','modconf','kms','block','filesystems','keyboard']:
    p=Path('/usr/lib/initcpio/install')/name
    print('\nHOOK',p,'\n'+p.read_text())
for cmd in [['lsinitcpio','-c','/home/builder/uki/live-initramfs.img'],['pacman','-Q','mkinitcpio','mkinitcpio-archiso'],['pacman','-Qkk','mkinitcpio']]:
    p=subprocess.run(cmd,capture_output=True,text=True)
    print('\nCMD',cmd,'EXIT',p.returncode,'\n'+p.stdout+p.stderr)
