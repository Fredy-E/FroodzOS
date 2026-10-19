#!/usr/bin/env python3
"""Exercise GRUB -> original stubble UKI -> original live rootfs."""
import json, os, select, subprocess, time
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
log=P/'qemu-grub-original.log'
if log.exists(): raise SystemExit('Refusing to overwrite earlier evidence')
cmd=['qemu-system-aarch64','-M','virt,gic-version=3','-cpu','cortex-a53','-accel','tcg','-m','2048','-smp','2',
     '-bios',str(P/'uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd'),
     '-device','qemu-xhci','-drive','if=none,id=stick,format=raw,readonly=on,file=/home/builder/boot-failure-tests/grub-original-rootfs.fat',
     '-device','usb-storage,drive=stick','-nographic','-no-reboot','-monitor','none']
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
start=time.monotonic(); output=b''; sent=False; deadline=180
with log.open('wb') as f:
    while time.monotonic()-start<deadline and p.poll() is None:
        ready,_,_=select.select([p.stdout],[],[],1)
        if not ready: continue
        chunk=os.read(p.stdout.fileno(),65536)
        if not chunk: break
        f.write(chunk); f.flush(); output+=chunk
        if not sent and (b'no job control' in output or b'bash-' in output[-1024:]):
            text="printf '\\nKESTREL_ROOTFS_OK\\n'; uname -r; findmnt /; cat /etc/os-release; /usr/bin/systemctl poweroff --force --force\n"
            p.stdin.write(text.encode()); p.stdin.flush(); sent=True
        if b'KESTREL_ROOTFS_OK' in output and b'reboot: Power down' in output: break
    if p.poll() is None:
        p.terminate()
        try: p.wait(timeout=10)
        except subprocess.TimeoutExpired: p.kill();p.wait()
    remaining=p.stdout.read()
    f.write(remaining);output+=remaining
text=output.decode(errors='replace')
markers=['KESTREL_EFI_MENU_REACHED','KESTREL_GRUB_LOADING_ORIGINAL_UKI','Linux version','Device','mounted successfully','no job control','KESTREL_ROOTFS_OK','Kernel panic','HWID matching failed','Bad kernel image','reboot: Power down']
summary={'command':cmd,'exit':p.returncode,'seconds':round(time.monotonic()-start,2),'log':str(log),'markers':{x:x in text for x in markers}}
(P/'qemu-grub-original-result.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
print('\nDIAGNOSTIC LINES')
for line in text.splitlines():
    if any(x in line for x in markers) or 'ERROR' in line or 'error:' in line or 'Out of memory' in line or 'archiso' in line:
        print(line[:600])
print('\nFINAL OUTPUT\n'+text[-7000:])
