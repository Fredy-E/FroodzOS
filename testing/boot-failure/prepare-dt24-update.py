#!/usr/bin/env python3
"""Pin dt24 only after all exact-candidate tests pass; retain dt23 prestate."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parents[2]
T = P / 'testing/boot-failure'
old = json.loads((T / 'dt23-update-manifest.json').read_text())
audit = json.loads((T / 'dt24-artifact-audit.json').read_text())
assert audit['passed'] and audit['kernel_stub_hwids_base_cmdline_unchanged']
gates = ['dt24-artifact-audit.json', 'qemu-dt24-menu8-text-fw-off-v2-result.json', 'dt24-logger-v2-v1-result.json']
for gate in gates:
    result = json.loads((T / gate).read_text())
    assert result['passed'] and result['uki_sha256'] == audit['uki_sha256'], gate
for fixture_gate in ['platform-input-gate-unit-result.json', 'platform-usb-gate-unit-result.json',
                     'dt24-text-hook-unit-result.json', 'dt24-board-predicate-unit-result.json',
                     'dt24-prompt-regression-result.json', 'dt24-independent-review.json']:
    assert json.loads((T / fixture_gate).read_text())['passed'], fixture_gate
assert json.loads((T / 'dt24-board-green.json').read_text())['passed']
assert json.loads((T / 'dt24-usb-retained-green.json').read_text())['passed']
old_files = {item['path']: item for item in old['files']}
files = []
for relative, source in [('EFI/Linux/kestrel-live.efi', 'dt24-candidate.efi'), ('boot/grub/grub.cfg', 'dt24-grub.cfg')]:
    path = T / source
    data = path.read_bytes()
    assert len(data) < 4294967296
    files.append({'path': relative, 'source': 'testing/boot-failure/' + source,
                  'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                  'old_sha256': old_files[relative]['sha256']})
assert files[0]['sha256'] == audit['uki_sha256']
unchanged = []
for previous in old['unchanged_files']:
    path = P / 'live-staging-v2' / previous['path']
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert path.stat().st_size == previous['bytes'] and digest == previous['sha256']
    unchanged.append(previous)
manifest = {'revision': 'v2-dt24', 'uki_sha256': audit['uki_sha256'], 'gates': gates,
            'files': files, 'unchanged_files': unchanged, 'menu_entries': 11, 'default_entry': 8,
            'default_init': '/sbin/init', 'default_init_override_removed': True,
            'local_live_console_only': True, 'default_target': 'multi-user.target',
            'firmware_clear_included': False, 'native_hardware_validated': False}
with (T / 'dt24-update-manifest.json').open('x') as stream:
    json.dump(manifest, stream, indent=2)
print(json.dumps(manifest, indent=2))
