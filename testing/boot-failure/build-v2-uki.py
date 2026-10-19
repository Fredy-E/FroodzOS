#!/usr/bin/env python3
"""Run the canonical corrected UKI build without shell-layer expansion."""
import argparse, os, re, subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--revision',default='v2');args=parser.parse_args()
if not re.fullmatch(r'v2(?:-[a-z0-9]+)*',args.revision): parser.error('Unsafe revision')
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
log_path=P/('build-uki-'+args.revision+'.log')
source=Path('/mnt/d/CachyOS-ARM64/builder/build-live-uki.sh')
# Keep the canonical script in its project path so relative hook discovery works.
env=os.environ.copy();env['OUT']='/home/builder/uki-'+args.revision;env['ROOT']='/home/builder/imgroot'
if Path(env['OUT']).exists(): raise SystemExit('Refusing to overwrite existing v2 UKI evidence')
with log_path.open('w') as log:
    result=subprocess.run(['bash',str(source)],env=env,stdout=log,stderr=subprocess.STDOUT)
print('UKI_BUILD_EXIT',result.returncode)
text=log_path.read_text()
for line in text.splitlines():
    if 'ERROR' in line or 'warning' in line.lower() or 'local board' in line or 'checks' in line or 'pid1_' in line or 'no_mount_' in line or 'firmware_present' in line or 'passed' in line or 'LIVE_UKI_DONE' in line: print(line)
print(text[-3500:])
raise SystemExit(result.returncode)
