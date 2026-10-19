#!/usr/bin/env python3
import hashlib, subprocess
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
T=Path('/home/builder/boot-failure-tests')
conf=T/'base-only.conf';conf.write_text('HOOKS=(base)\nMODULES=()\nBINARIES=()\nFILES=()\nCOMPRESSION="gzip"\n')
image=T/'base-only.img'
cmd=['/usr/bin/bash','-x','/usr/bin/mkinitcpio','--nopost','-k','none','-c',str(conf),'-g',str(image),'-s']
p=subprocess.run(cmd,env={'PATH':'/usr/bin:/bin','HOME':'/root','LC_ALL':'C.UTF-8'},capture_output=True,text=True)
(P/'mkinitcpio-base-trace.log').write_text(p.stdout+p.stderr)
print('BASE BUILD EXIT',p.returncode)
print(p.stdout)
for line in p.stderr.splitlines():
    if '/init' in line or '_d_library=' in line or 'bsdtar' in line: print(line[:600])
dest=T/'base-only-extract';dest.mkdir(exist_ok=True)
r=subprocess.run(['lsinitcpio','-x',str(image)],cwd=dest,capture_output=True,text=True)
print('EXTRACTION',r.returncode,r.stderr)
init=dest/'init'
print('NEW INIT',len(init.read_bytes()),hashlib.sha256(init.read_bytes()).hexdigest(),repr(init.read_bytes()[:80]))
lines=Path('/usr/bin/mkinitcpio').read_text().splitlines()
print('BUILD IMAGE SOURCE\n'+'\n'.join(f'{i+1}: {lines[i]}' for i in range(316,430)))
