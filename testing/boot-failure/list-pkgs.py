#!/usr/bin/env python3
"""List project pkgs layout and stubble source root for the alignment fix."""
import os
for d in ['/mnt/d/CachyOS-ARM64/pkgs', '/home/builder/src']:
    print('DIR', d)
    try:
        for name in sorted(os.listdir(d)):
            print('   ', name)
    except OSError as e:
        print('   MISSING', e)
