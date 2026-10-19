#!/usr/bin/env python3
"""Find how stubble.efi was built and inspect its source layout."""
import os, re
root = '/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a'
print('TOP')
for name in sorted(os.listdir(root)):
    print('   ', name)
for probe in ['README.md', 'Makefile', 'meson.build', 'build.sh', 'mkosi.conf']:
    p = os.path.join(root, probe)
    if os.path.isfile(p):
        print('FOUND', probe)
import subprocess
r = subprocess.run(['grep', '-rln', 'stubble.efi', '/mnt/d/CachyOS-ARM64/builder',
                    '--include=*.sh', '--include=*.py'], capture_output=True, text=True)
print('BUILDER_REFS\n' + r.stdout)
r = subprocess.run(['grep', '-rn', 'ninja\\|meson setup\\|make.*stubble\\|build.*stub',
                    '/mnt/d/CachyOS-ARM64/docs/phase2-results.md'], capture_output=True, text=True)
print('PHASE2\n' + r.stdout[:3000])
