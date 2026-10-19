#!/usr/bin/env python3
import os, re
from pathlib import Path
lines=Path('/usr/lib/initcpio/functions').read_text().splitlines()
for i,line in enumerate(lines):
    if re.match(r'^(add_initcpio_binary|find_binary|get.*path|add_binary)\(\)',line):
        print('\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-3),min(len(lines),i+90))))
print('ENV INITCPIO_PATH',os.environ.get('INITCPIO_PATH'),'PATH',os.environ.get('PATH'))
for base in ['/usr/lib/initcpio','/etc/initcpio','/etc/initcpio/init','/usr/lib/initcpio/init']:
    p=Path(base)
    print('CANDIDATE',p,'exists',p.exists(),'symlink',p.is_symlink())
    if p.is_file(): print('PREFIX',repr(p.read_bytes()[:40]))
for file in ['/usr/bin/mkinitcpio','/usr/lib/initcpio/functions']:
    p=Path(file)
    for i,line in enumerate(p.read_text().splitlines()):
        if re.search(r'INITCPIO_PATH|initcpio_path|add_initcpio_binary|type -P|find_binary',line):
            print(file,i+1,line)
