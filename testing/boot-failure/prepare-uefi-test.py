#!/usr/bin/env python3
"""Prepare local test dependencies and extract reference GRUB support."""
import hashlib, json, re, subprocess, urllib.request
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
ref=P/'control-reference'
iso='/mnt/d/CachyOS-ARM64/testing/control/stonking-desktop-arm64+x1e.iso'
r=subprocess.run(['pacman','-S','--needed','--noconfirm','mtools','dosfstools'],capture_output=True,text=True)
print(r.stdout,r.stderr)
if r.returncode: raise SystemExit(r.returncode)
subprocess.run(['bsdtar','-xf',iso,'-C',str(ref),'boot/grub/arm64-efi','boot/grub/fonts'],check=True)
url='https://deb.debian.org/debian/pool/main/e/edk2/'
html=urllib.request.urlopen(url,timeout=45).read().decode()
names=sorted(set(re.findall(r'href="(qemu-efi-aarch64_[^"]+_all\.deb)"',html)))
print('AVAILABLE',names)
if not names: raise SystemExit('No matching UEFI firmware package')
name=names[-1]
deb=P/name
if not deb.exists():
    urllib.request.urlretrieve(url+name,deb)
sha=hashlib.sha256(deb.read_bytes()).hexdigest()
print('DEBIAN FIRMWARE DOWNLOAD',url+name,'bytes',deb.stat().st_size,'sha256',sha)
print('PROVENANCE: HTTPS from Debian; recorded hash, not repository-signature verified')
meta=P/'uefi-firmware-provenance.json'
meta.write_text(json.dumps({'url':url+name,'sha256':sha,'verification':'HTTPS transport only; test dependency, not part of live image'},indent=2))
ar=subprocess.run(['bsdtar','-tf',str(deb)],capture_output=True,text=True,check=True)
data=next(line for line in ar.stdout.splitlines() if line.startswith('data.tar'))
out=P/'uefi-package'
out.mkdir(exist_ok=True)
subprocess.run(['bsdtar','-xf',str(deb),'-C',str(out),data],check=True)
subprocess.run(['bsdtar','-xf',str(out/data),'-C',str(out)],check=True)
for p in out.rglob('*'):
    if p.is_file() and p.suffix in ['.fd','.bin']:
        print('FIRMWARE',p,'bytes',p.stat().st_size)
