#!/usr/bin/env python3
"""Stage a dual diagnostic/control file tree without touching USB."""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64')
S=P/'live-staging-v2'
resume='--resume' in sys.argv
if S.exists() and not resume: raise SystemExit('Refusing to overwrite an existing v2 staging tree')
iso=P/'testing/control/stonking-desktop-arm64+x1e.iso'
with iso.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
assert digest=='0c4888195c693977ad65c74f5b516d1ce69b5e56e8aacfc7f4eacf3af18b145b',digest
if not S.exists():
    S.mkdir()
    subprocess.run(['bsdtar','--no-same-owner','--no-same-permissions','-xf',str(iso),'-C',str(S)],check=True)
dropped=[]
for f in S.rglob('*'):
    if f.is_symlink():
        dropped.append(str(f.relative_to(S)))
        f.unlink()
    elif f.is_file():
        f.chmod(0o644)
# Keep the original GRUB executable and replace only its menu later.
efi=S/'EFI/boot'
if not efi.exists(): efi=S/'EFI/BOOT'
assert efi.is_dir()
boot=next(p for p in efi.iterdir() if p.name.lower()=='bootaa64.efi')
grub=next(p for p in efi.iterdir() if p.name.lower()=='grubaa64.efi')
shutil.copyfile(grub,boot)
shutil.copyfile(P/'builder/live-grub.cfg',S/'boot/grub/grub.cfg')
files=[f for f in S.rglob('*') if f.is_file()]
large=[str(f.relative_to(S)) for f in files if f.stat().st_size>=2**32]
if large: raise SystemExit('FAT32-incompatible files: '+repr(large))
summary={'stage':str(S),'control_iso_sha256':digest,'file_count':len(files),'bytes':sum(f.stat().st_size for f in files),'dropped_symlinks':dropped,'largest_file':str(max(files,key=lambda p:p.stat().st_size).relative_to(S)),'usb_modified':False}
(P/'testing/boot-failure/control-staging-v2.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
