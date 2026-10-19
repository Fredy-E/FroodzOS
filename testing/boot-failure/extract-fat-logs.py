#!/usr/bin/env python3
"""Extract captured USB logs from a writable QEMU FAT fixture (host-side)."""
import json, subprocess, sys
from pathlib import Path
image = Path(sys.argv[1])
dest = Path(sys.argv[2])
info = json.loads(subprocess.run(['sfdisk', '--json', str(image)], check=True, text=True, capture_output=True).stdout)['partitiontable']
offset = info['partitions'][0]['start'] * info['sectorsize']
fs = f'{image}@@{offset}'
listing = subprocess.run(['mdir', '-i', fs, '::/Logs'], capture_output=True, text=True)
print(listing.stdout)
print(listing.stderr)
dest.mkdir(parents=True, exist_ok=True)
r = subprocess.run(['mcopy', '-s', '-i', fs, '::/Logs/*', str(dest) + '/'], capture_output=True, text=True)
print('MCOPY_EXIT', r.returncode)
print(r.stdout)
print(r.stderr)
for f in sorted(dest.rglob('*')):
    if f.is_file():
        print(f.relative_to(dest).as_posix(), f.stat().st_size)
