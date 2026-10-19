#!/usr/bin/env python3
"""Create a proper MBR/FAT32 USB fixture matching the physical media layout."""
import argparse, json, re, subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--systemd',action='store_true');parser.add_argument('--revision',default='v2-nls');args=parser.parse_args()
if not re.fullmatch(r'v2(?:-[a-z0-9]+)*',args.revision):parser.error('Unsafe revision')
P=Path('/mnt/d/CachyOS-ARM64')
T=Path('/home/builder/boot-failure-tests')
tag='qemu-'+args.revision+('-systemd' if args.systemd else '-shell')
image=T/(tag+'.fat')
if image.exists():raise SystemExit('Refusing to overwrite earlier media evidence')
root=Path('/home/builder/live-rootfs-v2.squashfs')
uki=Path('/home/builder/uki-'+args.revision+'/vmlinuz-live.efi')
assert root.exists() and uki.exists(),'v2 artifacts not yet complete'
with image.open('wb') as f:f.truncate(2304*1024*1024)
subprocess.run(['sfdisk',str(image)],input='label: dos\nunit: sectors\n\nstart=2048, type=c, bootable\n',text=True,check=True,capture_output=True)
info=json.loads(subprocess.run(['sfdisk','--json',str(image)],check=True,text=True,capture_output=True).stdout)['partitiontable']
part=info['partitions'][0]
assert part['start']==2048 and part['type']=='c'
offset=part['start']*info['sectorsize']
fs=str(image)+'@@'+str(offset)
subprocess.run(['mformat','-i',fs,'-T',str(part['size']),'-F','-v','KESTREL_A64','::'],check=True)
for directory in ['::/EFI','::/EFI/BOOT','::/EFI/Linux','::/arch','::/arch/aarch64','::/boot','::/boot/grub']:
    subprocess.run(['mmd','-i',fs,directory],check=True)
for source,dest in [(P/'testing/boot-failure/control-reference/EFI/boot/grubaa64.efi','::/EFI/BOOT/BOOTAA64.EFI'),(uki,'::/EFI/Linux/kestrel-live.efi'),(root,'::/arch/aarch64/airootfs.sfs')]:
    subprocess.run(['mcopy','-i',fs,str(source),dest],check=True)
cfg=(P/'builder/live-grub.cfg').read_text()
cfg=cfg.replace('set timeout=30','set timeout=1').replace('set default=0','set default=2' if args.systemd else 'set default=0')
cfg=cfg.replace('console=tty0','console=ttyAMA0,115200')
cfg=cfg.replace("echo 'Kestrel diagnostic loader v2 - GRUB reached'",'echo KESTREL_EFI_MENU_REACHED')
cfg=cfg.replace("echo 'Loading corrected Kestrel UKI and local board firmware...'",'echo KESTREL_GRUB_LOADING_V2_UKI')
cfg=cfg.replace("echo 'Loading Kestrel without the graphical login manager...'",'echo KESTREL_GRUB_LOADING_V2_UKI')
if not args.systemd:cfg=cfg.replace('panic=0','panic=0 init=/usr/bin/bash')
file=P/'testing/boot-failure'/(tag+'-grub.cfg');file.write_text(cfg)
subprocess.run(['mcopy','-i',fs,str(file),'::/boot/grub/grub.cfg'],check=True)
print(json.dumps({'image':str(image),'tag':tag,'partition_table':info,'mode':'systemd' if args.systemd else 'root-shell'},indent=2))
