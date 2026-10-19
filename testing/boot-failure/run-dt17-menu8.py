#!/usr/bin/env python3
import json, subprocess
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64');T=P/'testing/boot-failure';rev='v2-dt17';tag='qemu-dt17-menu8-v5'
result=T/(tag+'-initramfs.json')
if result.exists():raise SystemExit('Preserve earlier evidence; choose a fresh tag')
subprocess.run(['python3',str(T/'build-v2-uki.py'),'--revision',rev],check=True)
r=subprocess.run(['python3',str(P/'builder/validate-live-initramfs.py'),'/home/builder/uki-'+rev+'/live-initramfs.img','--require-local-firmware','--require-log-capture'],capture_output=True,text=True)
result.write_text(r.stdout);print(r.stdout);r.check_returncode()
subprocess.run(['python3',str(T/'prepare-log-validation.py'),'--revision',rev,'--systemd'],check=True)
subprocess.run(['python3',str(T/'run-efi-log-validation.py'),'--image','/home/builder/boot-failure-tests/qemu-'+rev+'-systemd.fat','--tag',tag,'--systemd'],check=True)
