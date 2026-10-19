#!/usr/bin/env python3
"""Archive only the virtual text gate's proof files for host-side review."""
import hashlib
import json
import shutil
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
result = json.loads((T / 'qemu-dt24-menu8-text-fw-off-v2-result.json').read_text())
assert result['passed'] and all(result['checks'].values())
source = Path(result['extract'])
output = T / 'dt24-qemu-text-proof'
output.mkdir()
rows = []
for leaf in ['06-text-startup.txt', '07-typed-command.txt', '00-status.txt']:
    matches = list(source.rglob(leaf))
    assert len(matches) == 1
    target = output / leaf
    shutil.copyfile(matches[0], target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.read_bytes() == matches[0].read_bytes()
    rows.append({'name': leaf, 'sha256': digest, 'bytes': target.stat().st_size})
report = {'passed': True, 'uki_sha256': result['uki_sha256'], 'files': rows,
          'virtual_serial_input_only': True, 'physical_keyboard_input_validated': False}
with (output / 'manifest.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps({'passed': True, 'checks': result['checks'], 'seconds': result['seconds'], 'proof_archive': str(output)}, indent=2))
for leaf in ['06-text-startup.txt', '07-typed-command.txt']:
    text = (output / leaf).read_text()
    print(leaf + '\n' + text.split('=== runtime modules ===')[0])
