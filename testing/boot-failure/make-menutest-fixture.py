#!/usr/bin/env python3
"""One-off fixture: current log-systemd image + current menu."""
import argparse, json, re, shutil, subprocess
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--tag', required=True)
parser.add_argument('--src', default='qemu-v2-log8-systemd.fat')
args = parser.parse_args()
if not re.fullmatch(r'[a-z0-9-]+', args.tag):
    parser.error('Unsafe tag')
P = Path('/mnt/d/CachyOS-ARM64')
T = Path('/home/builder/boot-failure-tests')
src = T / args.src
image = T / (args.tag + '.fat')
if image.exists():
    raise SystemExit('Refusing to overwrite earlier media evidence')
shutil.copyfile(src, image)
info = json.loads(subprocess.run(['sfdisk', '--json', str(image)], check=True,
                                 text=True, capture_output=True).stdout)['partitiontable']
offset = info['partitions'][0]['start'] * info['sectorsize']
fs = f'{image}@@{offset}'
cfg = (P / 'testing/boot-failure/log-option-grub.cfg').read_text()
cfg = cfg.replace('set timeout=30', 'set timeout=1').replace('set default=0', 'set default=3')
cfg = cfg.replace('console=tty0', 'console=ttyAMA0,115200')
cfg = cfg.replace("echo 'Kestrel diagnostic loader v2 - GRUB reached'", 'echo KESTREL_EFI_MENU_REACHED')
cfg = cfg.replace("echo 'Kernel log will be written to the USB Logs directory before the crash.'",
                  'echo KESTREL_GRUB_LOADING_LOG_UKI')
tmp = P / ('testing/boot-failure/' + args.tag + '-grub.cfg')
tmp.write_text(cfg)
subprocess.run(['mcopy', '-o', '-i', fs, str(tmp), '::/boot/grub/grub.cfg'], check=True)
print(json.dumps({'image': str(image), 'tag': args.tag}, indent=2))
