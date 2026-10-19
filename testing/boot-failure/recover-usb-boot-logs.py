"""Read-only USB log recovery; writes evidence only to the local project."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

PROJECT = Path('D:/CachyOS-ARM64')
STATE = PROJECT / 'testing/boot-failure'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', default='E:/')
    args = parser.parse_args()
    target = Path(args.target)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = STATE / ('native-log-recovery-' + stamp)
    out.mkdir()
    manifest_path = STATE / 'staging-v2-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    expected = {f['path'].lower(): f for f in manifest['files']}
    assert len(expected) == manifest['file_count']
    # Refuse to inspect another volume even if its drive letter was reassigned.
    ps = "Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='" + target.drive + "'\" -OperationTimeoutSec 15 | Select-Object DeviceID,VolumeName,FileSystem | ConvertTo-Json -Compress"
    query = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps], check=True, capture_output=True, text=True)
    volume = json.loads(query.stdout.strip())
    assert volume['VolumeName'] == 'KESTREL_A64' and volume['FileSystem'] == 'FAT32', volume
    actual = {}
    errors = []
    for root, dirs, names in __import__('os').walk(target):
        dirs[:] = [d for d in dirs if d.lower() != 'system volume information']
        for name in names:
            p = Path(root) / name
            rel = p.relative_to(target).as_posix()
            try:
                stat = p.stat()
                actual[rel.lower()] = {'path': rel, 'bytes': stat.st_size,
                    'modified_utc': dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat()}
            except OSError as exc:
                errors.append({'path': rel, 'error': str(exc)})
    missing = [f['path'] for key, f in expected.items() if key not in actual]
    sizes_changed = [actual[key] for key, f in expected.items() if key in actual and actual[key]['bytes'] != f['bytes']]
    new = [f for key, f in actual.items() if key not in expected]
    log_pattern = re.compile(r'(^|[/_.-])(dmesg|journal|pstore|ramoops|panic|crash|evidence|logs?)([/_.-]|$)', re.I)
    candidates = [f for f in actual.values() if log_pattern.search(f['path']) and f['path'].lower() not in expected]
    recovered = []
    for f in candidates:
        p = target / f['path']
        if f['bytes'] > 64 * 1024 * 1024:
            recovered.append({**f, 'copied': False, 'reason': 'over 64 MiB recovery limit'})
            continue
        dest = out / 'recovered' / f['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        digest = hashlib.file_digest(dest.open('rb'), 'sha256').hexdigest()
        recovered.append({**f, 'copied': True, 'local_path': str(dest), 'sha256': digest})
    critical = []
    for key in ['efi/boot/bootaa64.efi', 'efi/linux/kestrel-live.efi', 'boot/grub/grub.cfg']:
        f = expected[key]
        p = target / f['path']
        if p.is_file():
            with p.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            critical.append({'path': f['path'], 'sha256': digest, 'matches_staged': digest == f['sha256']})
        else:
            critical.append({'path': f['path'], 'missing': True, 'matches_staged': False})
    result = {'time_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'volume': volume,
        'target': str(target), 'manifest_files': manifest['file_count'],
        'scanned_files_excluding_windows_metadata': len(actual), 'missing_manifest_files': missing,
        'size_changed_manifest_files': sizes_changed, 'new_file_count': len(new), 'new_files': new,
        'log_candidates': len(candidates), 'recovered': recovered, 'errors': errors,
        'critical_hashes': critical, 'usb_modified_by_recovery': False,
        'limitation': 'No RAM-only Linux dmesg/journal can be recovered from the previous boot using Windows or WSL.'}
    (out / 'usb-inventory.json').write_text(json.dumps(list(actual.values()), indent=2), encoding='utf-8')
    (out / 'recovery-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'evidence_dir': str(out), **result}, indent=2))
    return int(bool(errors or missing or sizes_changed or any(not x['matches_staged'] for x in critical)))


if __name__ == '__main__':
    raise SystemExit(main())
