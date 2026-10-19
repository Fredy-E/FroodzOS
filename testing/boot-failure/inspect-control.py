#!/usr/bin/env python3
"""Extract only reference boot files from the already downloaded ISO."""
import subprocess
from pathlib import Path
import pefile
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/control-reference')
P.mkdir(exist_ok=True)
iso='/mnt/d/CachyOS-ARM64/testing/control/stonking-desktop-arm64+x1e.iso'
files=['boot/grub/grub.cfg','EFI/boot/bootaa64.efi','EFI/boot/grubaa64.efi','casper/vmlinuz']
subprocess.run(['bsdtar','-xf',iso,'-C',str(P),*files],check=True)
print((P/'boot/grub/grub.cfg').read_text())
for name in files[1:]:
    p=P/name
    pe=pefile.PE(str(p),fast_load=True)
    print('\nREFERENCE',name,'size',p.stat().st_size,'machine',hex(pe.FILE_HEADER.Machine),'entry',hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),'image size',pe.OPTIONAL_HEADER.SizeOfImage)
    for sec in pe.sections:
        n=sec.Name.rstrip(b'\0').decode(errors='replace')
        print(n,sec.Misc_VirtualSize,sec.SizeOfRawData)
        if n in ['.cmdline','.uname','.sbat']:
            print(sec.get_data()[:sec.Misc_VirtualSize].decode(errors='replace'))
for args in [['pacman','-Ss','edk2'],['pacman','-Si','mtools','dosfstools'],['pacman','-Q','edk2-aarch64']]:
    r=subprocess.run(args,capture_output=True,text=True)
    print('\nQUERY',args,'exit',r.returncode,'\n',r.stdout,r.stderr)
print('\nMAKE DEFAULTS')
print(Path('/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a/Make.defaults').read_text())
