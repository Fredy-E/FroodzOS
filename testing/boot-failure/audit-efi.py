#!/usr/bin/env python3
"""Inspect original EFI chain and test-tool availability, read-only."""
import importlib.util, re, subprocess
from pathlib import Path
import pefile
S=Path('/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a')
U=Path('/home/builder/uki/vmlinuz-live.efi')
for p in [S/'stubble.efi',U,Path('/home/builder/src/ksrc/arch/arm64/boot/Image')]:
    pe=pefile.PE(str(p),fast_load=True)
    print('\nPE',p,'machine',hex(pe.FILE_HEADER.Machine),'subsystem',pe.OPTIONAL_HEADER.Subsystem,'entry',hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),'base',hex(pe.OPTIONAL_HEADER.ImageBase),'imageSize',pe.OPTIONAL_HEADER.SizeOfImage,'align',pe.OPTIONAL_HEADER.SectionAlignment)
    for sec in pe.sections:
        print(sec.Name.rstrip(b'\0').decode(errors='replace'),'rva',hex(sec.VirtualAddress),'vsize',sec.Misc_VirtualSize,'raw',sec.SizeOfRawData,'flags',hex(sec.Characteristics))
for p in [S/'Makefile',S/'linux.c',S/'stub.c',S/'efi-log.c']:
    lines=p.read_text().splitlines()
    print('\nSOURCE',p)
    if p.name in ['Makefile','linux.c']:
        print('\n'.join(f'{i+1}: {line}' for i,line in enumerate(lines)))
    else:
        indexes=set()
        for i,line in enumerate(lines):
            if re.search(r'debug|watchdog|linux_exec|linux.*load|reboot|reset|efi_main|cmdline|log_error|StartImage|stall|WaitFor',line,re.I):
                indexes.update(range(max(0,i-4),min(len(lines),i+6)))
        print('\n'.join(f'{i+1}: {lines[i]}' for i in sorted(indexes)))
print('\nUEFI FIRMWARE')
for top in ['/usr/share/qemu','/usr/share/edk2','/usr/share/AAVMF']:
    p=Path(top)
    if p.exists():
        print('\n'.join(str(x) for x in p.rglob('*') if x.is_file() and x.suffix in ['.fd','.bin','.json']))
print('\nTOOLS')
for cmd in ['qemu-system-aarch64','mformat','mcopy','mkfs.fat','sfdisk','bsdtar','7z','dtc','fdtget','lsinitcpio']:
    result=subprocess.run(['bash','-c','command -v '+cmd],capture_output=True,text=True)
    print(cmd,result.stdout.strip() or 'MISSING')
res=subprocess.run(['lsinitcpio','-l','/home/builder/uki/live-initramfs.img'],capture_output=True,text=True)
allpaths=res.stdout.splitlines()
for pattern in ['firmware/updates/qcom/x1p42100','qcdxkmsuc','qcadsp8380','qccdsp8380','adsp_dtbs','cdsp_dtbs','usb-storage.ko','uas.ko','vfat.ko','virtio_blk.ko','virtio_pci.ko','hooks/archiso']:
    matched=[x for x in allpaths if pattern in x]
    print('INITRD',pattern,'matches',len(matched))
    print('\n'.join(matched[:6]))
