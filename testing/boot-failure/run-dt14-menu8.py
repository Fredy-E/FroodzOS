#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64');T=P/'testing/boot-failure';rev='v2-dt14';tag='qemu-dt14-menu8-v2'
result=T/(tag+'-initramfs.json')
if result.exists():raise SystemExit('Preserve earlier evidence; choose a fresh tag')
r=subprocess.run(['python3',str(P/'builder/validate-live-initramfs.py'),'/home/builder/uki-'+rev+'/live-initramfs.img','--require-local-firmware','--require-log-capture'],capture_output=True,text=True)
result.write_text(r.stdout);print(r.stdout);r.check_returncode()
subprocess.run(['python3',str(T/'prepare-log-validation.py'),'--revision',rev,'--systemd'],check=True)
subprocess.run(['python3',str(T/'run-efi-log-validation.py'),'--image','/home/builder/boot-failure-tests/qemu-'+rev+'-systemd.fat','--tag',tag,'--systemd'],check=True)
