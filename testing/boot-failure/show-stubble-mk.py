#!/usr/bin/env python3
"""Show stubble build method: Makefile head + builder build-uki.sh stubble refs."""
import re
root = '/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a'
mk = open(root + '/Makefile').read().splitlines()
print('MAKEFILE_HEAD')
print('\n'.join(mk[:60]))
print('ARCH_REFS', [l for l in mk if re.search(r'ARCH|aarch64|CROSS|CC\s*[:?]?=', l)][:20])
for f in ['/mnt/d/CachyOS-ARM64/builder/build-uki.sh']:
    try:
        for i, l in enumerate(open(f).read().splitlines()):
            if 'tubb' in l.lower():
                print(f'{f}:{i+1}: {l}')
    except OSError as e:
        print(f, e)
