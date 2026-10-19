#!/usr/bin/env python3
"""Inspect builder UKI dirs and stage the log-option delta sources."""
import os, shutil, sys
base = '/home/builder'
for name in sorted(os.listdir(base)):
    if name.startswith('uki-'):
        p = os.path.join(base, name)
        print(name, 'symlink' if os.path.islink(p) else 'dir', '->', os.readlink(p) if os.path.islink(p) else '')
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                fp = os.path.join(p, f)
                print('   ', f, os.path.getsize(fp) if os.path.isfile(fp) else '<dir>')
if len(sys.argv) > 1 and sys.argv[1] == 'stage':
    src = '/home/builder/uki-v2-log6/vmlinuz-live.efi'
    print('UKI_EXISTS', os.path.isfile(src), os.path.getsize(src) if os.path.isfile(src) else 0)
    dst_dir = '/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/EFI/Linux'
    os.makedirs(dst_dir, exist_ok=True)
    os.makedirs('/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/boot/grub', exist_ok=True)
    shutil.copyfile(src, os.path.join(dst_dir, 'kestrel-live-log.efi'))
    shutil.copyfile('/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option-grub.cfg',
                    '/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/boot/grub/grub.cfg')
    print('STAGED')
