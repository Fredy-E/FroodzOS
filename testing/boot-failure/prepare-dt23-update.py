#!/usr/bin/env python3
"""Pin the PID1-marked dt23 candidate and exact two-file USB update prestate."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2]
T = P / 'testing/boot-failure'
old = json.loads((T / 'dt22-update-manifest.json').read_text())
audit = json.loads((T / 'dt23-artifact-audit.json').read_text())
assert audit['passed'] and audit['kernel_dtb_stub_cmdline_unchanged_from_dt22']
old_files = {entry['path']: entry for entry in old['files']}
files = []
for relative, source in [('EFI/Linux/kestrel-live.efi', 'dt23-candidate.efi'),
                         ('boot/grub/grub.cfg', 'dt23-grub.cfg')]:
    path = T / source
    data = path.read_bytes()
    files.append({'path': relative, 'source': 'testing/boot-failure/' + source,
                  'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                  'old_sha256': old_files[relative]['sha256']})
assert files[0]['sha256'] == audit['uki_sha256']
unchanged = []
for relative in ('EFI/BOOT/BOOTAA64.EFI', 'arch/aarch64/airootfs.sfs'):
    path = P / 'live-staging-v2' / relative
    unchanged.append({'path': relative, 'bytes': path.stat().st_size,
                      'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()})
manifest = {'revision': 'v2-dt23', 'uki_sha256': audit['uki_sha256'],
            'gates': ['dt23-artifact-audit.json', 'dt23-logger-v2-v1-result.json',
                      'qemu-dt23-menu8-shell-fw-off-v1-result.json',
                      'qemu-dt23-menu8-systemd-fw-off-v1-result.json'],
            'files': files, 'unchanged_files': unchanged,
            'menu_entries': 11, 'default_entry': 8,
            'default_init': '/usr/local/sbin/kestrel-pid1', 'firmware_clear_included': False}
with (T / 'dt23-update-manifest.json').open('x') as output:
    json.dump(manifest, output, indent=2)
print(json.dumps(manifest, indent=2))
