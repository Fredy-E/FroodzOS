#!/usr/bin/env python3
"""Repair audited live rootfs blockers; preserve original squashfs evidence."""
import subprocess
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path('/home/builder/imgroot')
OUT=Path('/home/builder/live-rootfs-v2.squashfs')
if OUT.exists(): raise SystemExit('Refusing to overwrite existing v2 evidence')
def run(args):
    print('RUN',' '.join(map(str,args)),flush=True)
    r=subprocess.run(list(map(str,args)),check=False,capture_output=True,text=True)
    print(r.stdout,r.stderr,flush=True)
    r.check_returncode()
    return r.stdout
packages=['linux-firmware-qcom','linux-firmware-atheros','linux-firmware-whence']
urls=run(['pacman','-Sp','--print-format','%l',*packages]).splitlines()
files=[Path('/var/cache/pacman/pkg')/Path(urlparse(url).path).name for url in urls if url.startswith(('https://','http://','file://'))]
if len(files)<3: raise SystemExit('Failed to resolve all firmware package files')
run(['pacman','-Sw','--noconfirm',*packages])
if not all(p.exists() for p in files): raise SystemExit('Missing downloaded packages')
run(['pacman','--root',ROOT,'--config',ROOT/'etc/pacman.conf','--gpgdir',ROOT/'etc/pacman.d/gnupg','--cachedir','/var/cache/pacman/pkg','-U','--noconfirm','--needed',*files])
run(['systemctl','--root',ROOT,'enable','sddm','NetworkManager'])
run(['systemctl','--root',ROOT,'set-default','graphical.target'])
run(['systemctl','--root',ROOT,'is-enabled','sddm','NetworkManager'])
run(['systemctl','--root',ROOT,'get-default'])
assert (ROOT/'etc/systemd/system/display-manager.service').is_symlink()
assert (ROOT/'etc/systemd/system/multi-user.target.wants/NetworkManager.service').is_symlink()
(ROOT/'etc/machine-id').write_text('')
print('QCOM TOP-LEVEL FIRMWARE',flush=True)
for p in sorted((ROOT/'usr/lib/firmware/qcom').glob('*')):
    if p.is_file(): print(p.name,p.stat().st_size,flush=True)
run(['mksquashfs',ROOT,OUT,'-comp','xz','-processors','4','-noappend','-no-progress'])
print('ROOTFS_V2_DONE',OUT,OUT.stat().st_size,flush=True)
