#!/usr/bin/env python3
"""Clone disposable test media and load v2 artifacts, never hardware media."""
import argparse, json, shutil, subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--systemd',action='store_true');args=parser.parse_args()
P=Path('/mnt/d/CachyOS-ARM64')
T=Path('/home/builder/boot-failure-tests')
tag='qemu-v2-systemd' if args.systemd else 'qemu-v2-shell'
image=T/(tag+'.fat')
if image.exists():raise SystemExit('Refusing to overwrite test media')
root=Path('/home/builder/live-rootfs-v2.squashfs')
uki=Path('/home/builder/uki-v2/vmlinuz-live.efi')
assert root.exists() and uki.exists(),'v2 artifacts not yet complete'
assert root.stat().st_size>1000000000 and uki.stat().st_size>50000000
shutil.copyfile(T/'grub-original-rootfs.fat',image)
for dest in ['::/EFI/Linux/kestrel-original.efi','::/arch/aarch64/airootfs.sfs']:
    subprocess.run(['mdel','-i',str(image),dest],check=True)
for source,dest in [(uki,'::/EFI/Linux/kestrel-live.efi'),(root,'::/arch/aarch64/airootfs.sfs')]:
    subprocess.run(['mcopy','-i',str(image),str(source),dest],check=True)
cfg=(P/'builder/live-grub.cfg').read_text()
cfg=cfg.replace('set timeout=30','set timeout=1').replace('set default=0','set default=2' if args.systemd else 'set default=0')
cfg=cfg.replace('console=tty0','console=ttyAMA0,115200')
cfg=cfg.replace("echo 'Kestrel diagnostic loader v2 - GRUB reached'",'echo KESTREL_EFI_MENU_REACHED')
cfg=cfg.replace("echo 'Loading corrected Kestrel UKI and local board firmware...'",'echo KESTREL_GRUB_LOADING_V2_UKI')
cfg=cfg.replace("echo 'Loading Kestrel without the graphical login manager...'",'echo KESTREL_GRUB_LOADING_V2_UKI')
if not args.systemd:cfg=cfg.replace('panic=0','panic=0 init=/usr/bin/bash')
file=P/'testing/boot-failure'/(tag+'-grub.cfg');file.write_text(cfg)
subprocess.run(['mcopy','-o','-i',str(image),str(file),'::/boot/grub/grub.cfg'],check=True)
print('V2_TEST_MEDIA_READY',image,'mode','systemd' if args.systemd else 'root-shell')
