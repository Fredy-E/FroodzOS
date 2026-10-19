#!/usr/bin/env python3
"""Disposable writable FAT32 fixture with USB log-capture option enabled."""
import argparse, json, re, subprocess
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--systemd',action='store_true')
parser.add_argument('--revision',default='v2-log')
parser.add_argument('--tag')
parser.add_argument('--menu',type=Path)
args=parser.parse_args()
if not re.fullmatch(r'v2(?:-[a-z0-9]+)*',args.revision):parser.error('Unsafe revision')
if args.tag and not re.fullmatch(r'[a-z0-9-]+',args.tag):parser.error('Unsafe tag')
P=Path('/mnt/d/CachyOS-ARM64')
T=Path('/home/builder/boot-failure-tests')
tag=args.tag or ('qemu-'+args.revision+('-systemd' if args.systemd else '-shell'))
image=T/(tag+'.fat')
if image.exists():raise SystemExit('Refusing to overwrite earlier media evidence')
root=Path('/home/builder/live-rootfs-v2.squashfs')
uki_log=Path('/home/builder/uki-'+args.revision+'/vmlinuz-live.efi')
assert root.exists() and uki_log.exists(),'artifacts not yet complete'
with image.open('wb') as f:f.truncate(2600*1024*1024)
subprocess.run(['sfdisk',str(image)],input='label: dos\nunit: sectors\n\nstart=2048, type=c, bootable\n',text=True,check=True,capture_output=True)
info=json.loads(subprocess.run(['sfdisk','--json',str(image)],check=True,text=True,capture_output=True).stdout)['partitiontable']
part=info['partitions'][0]
assert part['start']==2048 and part['type']=='c'
offset=part['start']*info['sectorsize']
fs=str(image)+'@@'+str(offset)
subprocess.run(['mformat','-i',fs,'-T',str(part['size']),'-F','-v','KESTREL_A64','::'],check=True)
for directory in ['::/EFI','::/EFI/BOOT','::/EFI/Linux','::/arch','::/arch/aarch64','::/boot','::/boot/grub','::/Logs','::/notes']:
    subprocess.run(['mmd','-i',fs,directory],check=True)
marker=P/'testing/boot-failure/log-option/KESTREL-LOG-TARGET'
marker.parent.mkdir(exist_ok=True)
marker.write_text('KESTREL_A64_USB_CAPTURE_V1\n')
for source,dest in [
    (P/'testing/boot-failure/control-reference/EFI/boot/grubaa64.efi','::/EFI/BOOT/BOOTAA64.EFI'),
    (uki_log,'::/EFI/Linux/kestrel-live.efi'),
    (root,'::/arch/aarch64/airootfs.sfs'),
    (marker,'::/KESTREL-LOG-TARGET')]:
    subprocess.run(['mcopy','-i',fs,str(source),dest],check=True)
cfg=(args.menu or (P/'testing/boot-failure/log-option-grub.cfg')).read_text()
cfg=re.sub(r'^set default=\d+$','set default=3',cfg,flags=re.M)
cfg=cfg.replace('set timeout=30','set timeout=1')
cfg=cfg.replace('console=tty0','console=ttyAMA0,115200')
cfg=cfg.replace('terminal_output console','terminal_output console\necho KESTREL_EFI_MENU_REACHED')
cfg=re.sub(r'^(\s*)linux /EFI/Linux/kestrel-live.efi',r'\1echo KESTREL_GRUB_LOADING_LOG_UKI\n\1linux /EFI/Linux/kestrel-live.efi',cfg,flags=re.M)
if not args.systemd:
    cfg=cfg.replace('linux /EFI/Linux/kestrel-live.efi kestrel_log=1','linux /EFI/Linux/kestrel-live.efi init=/usr/bin/bash kestrel_log=1')
file=P/'testing/boot-failure'/(tag+'-grub.cfg');file.write_text(cfg)
subprocess.run(['mcopy','-i',fs,str(file),'::/boot/grub/grub.cfg'],check=True)
print(json.dumps({'image':str(image),'tag':tag,'offset':offset,'partition_table':info,'mode':'systemd' if args.systemd else 'root-shell'},indent=2))
