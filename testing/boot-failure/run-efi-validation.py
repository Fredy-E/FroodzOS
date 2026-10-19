#!/usr/bin/env python3
"""Run disposable EFI/FAT live-image validation; no real media writes."""
import argparse, json, os, re, select, subprocess, time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--image',required=True)
parser.add_argument('--tag',required=True)
parser.add_argument('--systemd',action='store_true')
args=parser.parse_args()
if not re.fullmatch(r'[a-z0-9-]+',args.tag): parser.error('Unsafe tag')
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
log=P/(args.tag+'.log'); result_file=P/(args.tag+'-result.json')
if log.exists() or result_file.exists(): raise SystemExit('Refusing to overwrite earlier evidence')
cmd=['qemu-system-aarch64','-M','virt,gic-version=3','-cpu','cortex-a53','-accel','tcg','-m','2048','-smp','2',
     '-bios',str(P/'uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd'),
     '-device','qemu-xhci','-drive',f'if=none,id=stick,format=raw,readonly=on,file={args.image}',
     '-device','usb-storage,drive=stick','-nographic','-no-reboot','-monitor','none']
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
start=time.monotonic();output=b'';sent=False;reason='deadline'
with log.open('wb') as f:
    while time.monotonic()-start<240 and p.poll() is None:
        ready,_,_=select.select([p.stdout],[],[],1)
        if not ready: continue
        chunk=os.read(p.stdout.fileno(),65536)
        if not chunk: reason='eof';break
        f.write(chunk);f.flush();output+=chunk
        if not args.systemd and not sent and (b'no job control' in output or b'bash-' in output[-1024:]):
            # Serial echo contains this command too; only standalone marker lines count below.
            text="printf '\\nKESTREL_ROOTFS_OK\\n'; uname -r; findmnt -n -o FSTYPE /; cat /etc/os-release; systemctl --root=/ is-enabled sddm NetworkManager; /usr/bin/systemctl poweroff --force --force\n"
            p.stdin.write(text.encode());p.stdin.flush();sent=True
        if b'Falling back to interactive prompt' in output: reason='initramfs-mount-failure';break
        if b'---[ end Kernel panic' in output: reason='kernel-panic';break
        clean=re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]',b'',output)
        if args.systemd and re.search(rb'Reached target [^\r\n]*Multi-User System',clean): reason='systemd-multi-user';break
        if b'reboot: Power down' in output: reason='poweroff';break
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
    remaining=p.stdout.read();f.write(remaining);output+=remaining
text=output.decode(errors='replace')
markers={
    'grub_menu':'KESTREL_EFI_MENU_REACHED' in text,
    'v2_uki_loaded':'KESTREL_GRUB_LOADING_V2_UKI' in text,
    'kernel_started':'Linux version 7.3.0-rc3' in text,
    'rootfs_shell':bool(re.search(r'^KESTREL_ROOTFS_OK\r?$',text,re.M)),
    'overlay_root':bool(re.search(r'^overlay\r?$',text,re.M)),
    'kestrel_identity':bool(re.search(r'^ID=kestrelos\r?$',text,re.M)),
    'panic':'Kernel panic' in text,
    'wsl_init':'init-distro' in text or 'WSL (' in text,
    'poweroff':'reboot: Power down' in text,
    'systemd_multi_user':reason=='systemd-multi-user',
}
passed=(markers['grub_menu'] and markers['v2_uki_loaded'] and markers['kernel_started'] and not markers['panic'] and not markers['wsl_init'] and (markers['systemd_multi_user'] if args.systemd else all(markers[k] for k in ['rootfs_shell','overlay_root','kestrel_identity','poweroff'])))
summary={'command':cmd,'qemu_exit':p.returncode,'seconds':round(time.monotonic()-start,2),'stop_reason':reason,'log':str(log),'markers':markers,'passed':passed,'hardware_validated':False}
result_file.write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
print('\nFINAL OUTPUT\n'+text[-14000:])
raise SystemExit(0 if passed else 1)
