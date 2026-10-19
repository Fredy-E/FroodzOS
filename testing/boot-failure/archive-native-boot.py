#!/usr/bin/env python3
"""Archive native USB log dirs + firmware export with hash checks."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

bootdir = sys.argv[1]  # e.g. boot-<uuid>
root = Path('D:/CachyOS-ARM64/testing/boot-failure')
report_path = Path(sys.argv[2])  # firmware recovery report.json
manifest = json.loads((root / 'dt22-update-manifest.json').read_text())

bid = bootdir[5:]
src = Path('E:/Logs') / bootdir
dst = root / ('native-dt22-' + bid)
dst.mkdir(exist_ok=False)
out = dst / 'usb-logs'
out.mkdir()
entries = []
for f in sorted(x for x in src.iterdir() if x.is_file()):
    data = f.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    target = out / f.name
    shutil_copy = __import__('shutil').copy2(f, target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == sha
    assert hashlib.sha256(f.read_bytes()).hexdigest() == sha
    entries.append({'name': f.name, 'bytes': len(data), 'sha256': sha})
report = json.loads(report_path.read_text(encoding='utf-8-sig'))
shutil = __import__('shutil')
shutil.copy2(report_path, dst / 'firmware-report.json')
arts = []
for f in manifest['files']:
    p = Path('E:/') / f['path']
    h = hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
    assert h == f['sha256'], (f['path'], h)
    arts.append({'path': f['path'], 'sha256': h, 'matches_dt22_manifest': True})
result = {'captured_at_utc': datetime.now(timezone.utc).isoformat(),
          'boot_id': bid, 'usb_source': str(src), 'archive': str(dst),
          'usb_logs': entries,
          'firmware_export': str(Path(report_path).parent),
          'firmware_boot_ids': report['boot_ids'],
          'artifacts': arts, 'usb_writes': 0, 'firmware_writes': 0}
(dst / 'archive-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
