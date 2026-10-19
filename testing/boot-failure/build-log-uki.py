#!/usr/bin/env python3
"""Build the log-capture UKI revision (keestrel_log hook, inert without kestrel_log=1)."""
import os, re, subprocess
from pathlib import Path
revision='v2-log8'
assert re.fullmatch(r'v2(?:-[a-z0-9]+)*',revision)
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
log_path=P/('build-uki-'+revision+'.log')
source=Path('/mnt/d/CachyOS-ARM64/builder/build-live-uki.sh')
streamer=Path('/home/builder/diag/kestrel-kmsg')
assert streamer.is_file(),'compile kestrel-kmsg first'
out=Path('/home/builder/uki-'+revision)
if out.exists(): raise SystemExit('Refusing to overwrite existing UKI evidence')
env=os.environ.copy()
env.update({'OUT':str(out),'ROOT':'/home/builder/imgroot','KESTREL_LOG':'1',
            'KESTREL_LOG_BINARY':str(streamer),'KESTREL_PROJECT':'/mnt/d/CachyOS-ARM64'})
with log_path.open('w') as log:
    result=subprocess.run(['bash',str(source)],env=env,stdout=log,stderr=subprocess.STDOUT)
print('UKI_BUILD_EXIT',result.returncode)
text=log_path.read_text()
for line in text.splitlines():
    if 'ERROR' in line or 'warning' in line.lower() or 'local board' in line or 'checks' in line or 'log_' in line or 'passed' in line or 'LIVE_UKI_DONE' in line: print(line)
print(text[-3500:])
raise SystemExit(result.returncode)
