#!/usr/bin/env python3
"""Build a disposable FAT image; never accesses a real disk."""
import shutil, subprocess
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
T=Path('/home/builder/boot-failure-tests')
T.mkdir(exist_ok=True)
image=T/'grub-original-rootfs.fat'
if image.exists(): raise SystemExit('Refusing to overwrite an existing test image')
with image.open('wb') as f: f.truncate(2304*1024*1024)
subprocess.run(['mformat','-i',str(image),'-F','-v','KESTREL_A64','::'],check=True)
for d in ['::/EFI','::/EFI/BOOT','::/EFI/Linux','::/arch','::/arch/aarch64','::/boot','::/boot/grub']:
    subprocess.run(['mmd','-i',str(image),d],check=True)
def cp(source,dest):
    subprocess.run(['mcopy','-i',str(image),str(source),dest],check=True)
cp(P/'control-reference/EFI/boot/grubaa64.efi','::/EFI/BOOT/BOOTAA64.EFI')
cp('/home/builder/uki/vmlinuz-live.efi','::/EFI/Linux/kestrel-original.efi')
cp('/home/builder/live-rootfs.squashfs','::/arch/aarch64/airootfs.sfs')
cp(P/'control-reference/boot/grub/arm64-efi','::/boot/grub/') if False else None
cfg=P/'qemu-grub.cfg'
cfg.write_text('''set timeout=1
set default=0
terminal_output console
echo KESTREL_EFI_MENU_REACHED
menuentry "Original Kestrel UKI - serial validation" {
    echo KESTREL_GRUB_LOADING_ORIGINAL_UKI
    linux /EFI/Linux/kestrel-original.efi debug archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=128M clk_ignore_unused pd_ignore_unused console=ttyAMA0,115200 loglevel=7 ignore_loglevel panic=0 init=/usr/bin/bash
    boot
}
''')
cp(cfg,'::/boot/grub/grub.cfg')
print('TEST_IMAGE_READY',image,'bytes',image.stat().st_size)
