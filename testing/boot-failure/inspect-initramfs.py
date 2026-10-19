#!/usr/bin/env python3
"""Identify WSL contamination inside the original initramfs."""
import hashlib, os, re, subprocess
from pathlib import Path
U=Path('/home/builder/uki/live-initramfs.img')
P=Path('/home/builder/boot-failure-tests/initramfs-original')
if P.exists(): raise SystemExit('Refusing to overwrite extracted evidence')
P.mkdir()
for cmd in [['lsinitcpio','--help'],['lsinitcpio','-x',str(U)]]:
    r=subprocess.run(cmd,cwd=P,capture_output=True,text=True)
    print('COMMAND',cmd,'EXIT',r.returncode,'\n',r.stdout[:2000],r.stderr[:2000])
for name in ['init','usr/bin/ash','usr/bin/busybox','usr/lib/initcpio/init','etc/ld.so.preload']:
    p=P/name
    print('\nEXTRACTED',name,'exists',p.exists(),'symlink',p.is_symlink())
    if p.is_symlink(): print('TARGET',os.readlink(p))
    elif p.exists() and p.is_file():
        data=p.read_bytes()
        print('BYTES',len(data),'SHA256',hashlib.sha256(data).hexdigest(),'PREFIX',repr(data[:128]))
        matches=re.findall(rb'[ -~]{8,}',data)
        print('WSL STRINGS',[x.decode() for x in matches if b'WSL' in x or b'init-distro' in x][:20])
for name in ['/init','/usr/lib/initcpio/init','/usr/lib/initcpio/install/base','/usr/lib/initcpio/install/udev']:
    p=Path(name)
    print('\nHOST FILE',p,'symlink',p.is_symlink())
    if p.is_file():
        b=p.read_bytes()
        print('BYTES',len(b),'SHA256',hashlib.sha256(b).hexdigest(),'PREFIX',repr(b[:80]))
        if b.startswith(b'#!'): print(b.decode()[:10000])
print('\nINITCPIO IMPLEMENTATION')
lines=Path('/usr/lib/initcpio/functions').read_text().splitlines()
print('\n'.join(f'{i+1}: {lines[i]}' for i in range(988,1128)))
print('ENV INITCPIO_PATH',os.environ.get('INITCPIO_PATH'),'PATH',os.environ.get('PATH'))
for base in ['/usr/lib/initcpio','/etc/initcpio']:
    for name in ['init','init_functions']:
        p=Path(base)/name
        print('CANDIDATE',p,'exists',p.exists())
        if p.exists(): print('PREFIX',repr(p.read_bytes()[:40]))
print('\nINITCPIO SOURCE REFERENCES')
for base in ['/usr/lib/initcpio','/etc/initcpio']:
    d=Path(base)
    if not d.exists(): continue
    for f in d.rglob('*'):
        if not f.is_file() or f.stat().st_size>150000: continue
        try: lines=f.read_text().splitlines()
        except UnicodeDecodeError: continue
        for i,line in enumerate(lines):
            if re.search(r'(/init[\s\"\x27]|BUILDROOT|add_binary.+ash|ld.so.preload|init-distro)',line):
                print(f,i+1,line[:300])
