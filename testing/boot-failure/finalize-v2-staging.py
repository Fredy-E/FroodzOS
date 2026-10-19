#!/usr/bin/env python3
"""Finalize local-only diagnostic staging after both real EFI tests pass."""
import hashlib, json, shutil
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64')
B=P/'testing/boot-failure'
S=P/'live-staging-v2'
manifest=B/'staging-v2-manifest.json'
if manifest.exists(): raise SystemExit('Refusing to overwrite an earlier final manifest')
results={name:json.loads((B/('qemu-v2-nls-'+name+'-result.json')).read_text()) for name in ['shell','systemd']}
assert all(v['passed'] for v in results.values()),'Both EFI tests must pass'
assert S.is_dir()
(S/'EFI/Linux').mkdir(exist_ok=True)
(S/'arch/aarch64').mkdir(parents=True,exist_ok=True)
shutil.copyfile('/home/builder/uki-v2-nls/vmlinuz-live.efi',S/'EFI/Linux/kestrel-live.efi')
shutil.copyfile('/home/builder/live-rootfs-v2.squashfs',S/'arch/aarch64/airootfs.sfs')
(S/'notes').mkdir(exist_ok=True)
for name in ['capture.sh','m1-checklist.md']:
    shutil.copyfile(P/'live-staging/notes'/name,S/'notes'/name)
(S/'KESTREL-DIAGNOSTIC-README.txt').write_text('''Kestrel diagnostic media v2 - PRIVATE / LOCAL-ONLY

This file tree contains proprietary firmware from this laptop. Never upload it.
It combines the corrected Kestrel live image with the downloaded Ubuntu Concept
control image. The default removable-media EFI loader is the reference GRUB
executable, with a diagnostic menu and its Snapdragon memory-map workaround.

Choose one-time F12 -> Kingston. Do not change permanent firmware boot order.
Use Try Ubuntu only in the control entry; do not install or write internal disks.
Kestrel entries show messages and use panic=0 to keep failures on screen.
The physical Lenovo boot, Plasma, networking and thermal gates remain untested.

The Kestrel EFI/live chain passed QEMU ARMv8-A tests through a FAT32 USB fixture:
correct initramfs PID 1, mounted writable overlay root, running rootfs userspace,
systemd multi-user startup, and forced guest poweroff in the shell test.
That is not a hardware compatibility guarantee or a Plasma GUI test.

SDDM and NetworkManager were enabled and generic Qualcomm GPU plus local board
firmware were added. If physical boot fails, photograph the last visible text.
Avoid repeated unchanged attempts. Keep hardware tests short until fan/thermal
behavior is confirmed. Capture logs using notes/capture.sh if a session starts.

The control kernel/initrd/rootfs are unchanged ISO payloads. The common GRUB
menu/default EFI loader and their two unkeyed integrity-list entries are adapted.
''')
# Keep control casper's unkeyed integrity listing consistent with intentionally
# changed loader/menu files. Preserve its original listing as local evidence.
md5=S/'md5sum.txt';text=md5.read_text()
(B/'original-control-md5sum.txt').write_text(text)
modified={'./EFI/boot/bootaa64.efi','./boot/grub/grub.cfg'}
rows=[];changes=[]
for row in text.splitlines():
    old,path=row.split('  ',1)
    if path in modified:
        with (S/path.removeprefix('./')).open('rb') as f:new=hashlib.file_digest(f,'md5').hexdigest()
        rows.append(new+'  '+path);changes.append(path)
    else:rows.append(row)
for path in sorted(modified-set(changes)):
    # The reference ISO deliberately omits grub.cfg from md5sum.txt.
    # Add the adapted menu's entry rather than assuming one already exists.
    with (S/path.removeprefix('./')).open('rb') as f:new=hashlib.file_digest(f,'md5').hexdigest()
    rows.append(new+'  '+path);changes.append(path)
assert set(changes)==modified
md5.write_text('\n'.join(rows)+'\n')
files=[]
for file in sorted(S.rglob('*')):
    if not file.is_file() or file.name=='SHA256SUMS':continue
    size=file.stat().st_size
    assert size<2**32,str(file)
    with file.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    files.append({'path':file.relative_to(S).as_posix(),'bytes':size,'sha256':digest})
sums=S/'SHA256SUMS';sums.write_text(''.join(row['sha256']+'  '+row['path']+'\n' for row in files))
with sums.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
files.append({'path':'SHA256SUMS','bytes':sums.stat().st_size,'sha256':digest})
summary={'revision':'v2-nls','stage':str(S),'file_count':len(files),'total_bytes':sum(row['bytes'] for row in files),'qemu_shell_passed':results['shell']['passed'],'qemu_systemd_passed':results['systemd']['passed'],'control_integrity_entries_updated':changes,'hardware_boot_verified':False,'usb_modified':False,'publishable':False,'files':files}
manifest.write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='files'},indent=2))
print('STAGING_FINALIZED_GB',round(summary['total_bytes']/10**9,3))
for row in files:
    if row['path'] in ['EFI/boot/bootaa64.efi','EFI/Linux/kestrel-live.efi','arch/aarch64/airootfs.sfs','boot/grub/grub.cfg','SHA256SUMS']:print(json.dumps(row))
