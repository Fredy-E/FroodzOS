#!/usr/bin/env python3
"""Boot the writable log-capture fixture, then read captured logs back off the FAT."""
import argparse, json, os, re, select, shutil, subprocess, time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--image',required=True)
parser.add_argument('--tag',required=True)
parser.add_argument('--systemd',action='store_true')
parser.add_argument('--deadline',type=int,default=300)
parser.add_argument('--require-platform-usb',action='store_true')
args=parser.parse_args()
if args.require_platform_usb and args.systemd: parser.error('Runtime module assertion requires the root-shell mode')
if not 60 <= args.deadline <= 900: parser.error('Deadline must be 60..900 seconds')
if not re.fullmatch(r'[a-z0-9-]+',args.tag): parser.error('Unsafe tag')
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
T=Path('/home/builder/boot-failure-tests')
log=P/(args.tag+'.log'); result_file=P/(args.tag+'-result.json')
extract=T/(args.tag+'-extracted')
if log.exists() or result_file.exists() or extract.exists(): raise SystemExit('Refusing to overwrite earlier evidence')
cmd=['qemu-system-aarch64','-M','virt,gic-version=3','-cpu','cortex-a53','-accel','tcg','-m','2048','-smp','2',
     '-bios',str(P/'uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd'),
     '-device','qemu-xhci','-drive',f'if=none,id=stick,format=raw,file={args.image}',
     '-device','usb-storage,drive=stick','-nographic','-no-reboot','-monitor','none']
p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
start=time.monotonic();output=b'';sent=False;reason='deadline'
with log.open('wb') as f:
    while time.monotonic()-start<args.deadline and p.poll() is None:
        ready,_,_=select.select([p.stdout],[],[],1)
        if not ready: continue
        chunk=os.read(p.stdout.fileno(),65536)
        if not chunk: reason='eof';break
        f.write(chunk);f.flush();output+=chunk
        if not args.systemd and not sent and (b'no job control' in output or b'bash-' in output[-1024:]):
            text="printf '\\nKESTREL_ROOTFS_OK\\n'; ls -la /run/archiso/bootmnt/Logs 2>&1; cat /run/archiso/bootmnt/Logs/boot-*/00-status.txt 2>&1; uname -r; findmnt -n -o FSTYPE /; /usr/bin/systemctl poweroff --force --force\n"
            if args.require_platform_usb:
                text=text.replace('/usr/bin/systemctl poweroff', 'echo KESTREL_MODULES_BEGIN; cat /proc/modules; echo KESTREL_MODULES_END; /usr/bin/systemctl poweroff')
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
# Read the captured logs back from the FAT image, independent of the VM.
info=json.loads(subprocess.run(['sfdisk','--json',str(args.image)],check=True,text=True,capture_output=True).stdout)['partitiontable']
offset=info['partitions'][0]['start']*info['sectorsize']
fs=f'{args.image}@@{offset}'
listing=subprocess.run(['mdir','-i',fs,'::/Logs'],capture_output=True,text=True)
boot_dirs=[line.strip().split()[-1] for line in listing.stdout.splitlines() if line.strip().lower().startswith('boot-')]
extract.mkdir()
if boot_dirs:
    subprocess.run(['mcopy','-s','-i',fs,'::/Logs/*',str(extract)+'/'],check=False)
captured={}
for f in sorted(extract.rglob('*')):
    if f.is_file():
        captured[f.relative_to(extract).as_posix()]=f.stat().st_size
def has(name, needle):
    matches=[f for f in extract.rglob(name)]
    return bool(matches) and needle in matches[0].read_text(errors='replace')
kmsg=[f for f in extract.rglob('01-kernel-kmsg.log')]
kmsg_text=kmsg[0].read_text(errors='replace') if kmsg else ''
status=[f for f in extract.rglob('00-status.txt')]
status_text=status[0].read_text(errors='replace') if status else ''
markers={
    'grub_menu':'KESTREL_EFI_MENU_REACHED' in text,
    'log_uki_loaded':'KESTREL_GRUB_LOADING_LOG_UKI' in text,
    'kernel_started':'Linux version 7.3.0-rc3' in text,
    'usb_log_active':'KESTREL_USB_LOG_ACTIVE' in text,
    'usb_log_unavailable':'KESTREL_USB_LOG_UNAVAILABLE' in text,
    'status_file_captured':bool(status),
    'early_ram_captured':any((b'Linux version 7.3.0-rc3' in (d:=f.read_bytes()) or re.search(rb';(calling|probe of) ',d)) for f in extract.rglob('early-kmsg.log') if f.is_file()),
    'firmware_off':has('checkpoint-status.log','firmware=0'),
    'early_collector_stopped':has('checkpoint-status.log','KESTREL_RAM_CAPTURE_STOPPED') or 'KESTREL_RAM_CAPTURE_STOPPED' in text,
    'overlay_root_ready':'KESTREL_OVERLAY_ROOT_READY' in status_text,
    'kmsg_captured':bool(kmsg) and 'Linux version 7.3.0-rc3' in kmsg_text,
    'kmsg_has_post_kernel_lines':bool(kmsg) and len(kmsg_text)>2000,
    'dmesg_snapshots':any(f.name=='05-dmesg-snapshots.log' for f in extract.rglob('*') if f.is_file()),
    'userspace_journal':any(f.name=='03-userspace-journal.log' and f.stat().st_size>0 for f in extract.rglob('*') if f.is_file()),
    'userspace_logger_started':'KESTREL_USERSPACE_LOGGER_STARTED' in status_text,
    'panic':'Kernel panic' in text,
    'wsl_init':'init-distro' in text or 'WSL (' in text,
    'poweroff':'reboot: Power down' in text,
}
base=(markers['grub_menu'] and markers['log_uki_loaded'] and markers['kernel_started']
      and markers['usb_log_active'] and not markers['usb_log_unavailable']
      and markers['status_file_captured'] and markers['kmsg_captured']
      and markers['kmsg_has_post_kernel_lines'] and not markers['wsl_init'] and not markers['panic']
      and markers['early_ram_captured'] and markers['firmware_off'] and markers['early_collector_stopped'])
if args.require_platform_usb:
    module_block=re.search(r'^KESTREL_MODULES_BEGIN\r?\n(.*?)^KESTREL_MODULES_END\r?$',text,re.M|re.S)
    module_text=module_block.group(1) if module_block else ''
    for module in ('gpi','i2c_qcom_geni','phy_nxp_ptn3222','qrtr','qrtr_smd'):
        markers['runtime_'+module]=bool(re.search(r'^'+module+r'\s+\d+\s',module_text,re.M))
    markers['live_overlay_fstype']=bool(re.search(r'^overlay\r?$',text,re.M))
    base=base and markers['live_overlay_fstype'] and all(markers['runtime_'+name] for name in ('gpi','i2c_qcom_geni','phy_nxp_ptn3222','qrtr','qrtr_smd'))
if args.systemd:
    passed=base and reason=='systemd-multi-user' and markers['userspace_journal'] and markers['userspace_logger_started']
else:
    passed=base and markers['overlay_root_ready'] and markers['poweroff']
summary={'deadline_seconds':args.deadline,'command':cmd,'qemu_exit':p.returncode,'seconds':round(time.monotonic()-start,2),'stop_reason':reason,
         'log':str(log),'captured_files':captured,'boot_dirs':boot_dirs,'markers':markers,
         'passed':passed,'hardware_validated':False,
         'kmsg_tail':kmsg_text[-1200:],'status_text':status_text[-1200:]}
result_file.write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
print('\nFINAL OUTPUT\n'+text[-8000:])
raise SystemExit(0 if passed else 1)
