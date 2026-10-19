#!/usr/bin/env python3
"""Archive one native boot and audit captured state; never write to USB/firmware."""
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT = Path('D:/CachyOS-ARM64')
BOOT_ID = '6a63f6cc-bab8-4140-a699-cabc59050514'
USB = Path('E:/')
SOURCE = USB / 'Logs' / ('boot-' + BOOT_ID)
BASE = PROJECT / 'testing/boot-failure'
STAMP = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = BASE / ('native-dt25b-' + BOOT_ID + '-' + STAMP)
EXPECTED = {
    'EFI/Linux/kestrel-live.efi': ('b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753', 244424704),
    'boot/grub/grub.cfg': ('a4bec7016a798e82f7d6f2c546b8829d072075d36e8b61f61ed88e48035740de', 6720),
    'arch/aarch64/airootfs.sfs': ('5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c', 1748525056),
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


# Reconfirm physical association, not just the drive letter or a stale manifest.
ps = '''$ErrorActionPreference='Stop'; $rows=@(); foreach($d in @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object InterfaceType -eq 'USB')) { foreach($p in @(Get-CimAssociatedInstance -InputObject $d -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) { foreach($v in @(Get-CimAssociatedInstance -InputObject $p -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15)) { $rows += [pscustomobject]@{Disk=$d.DeviceID; Model=$d.Model; DiskSize=$d.Size; Interface=$d.InterfaceType; PartitionSize=$p.Size; Offset=$p.StartingOffset; Drive=$v.DeviceID; Label=$v.VolumeName; Filesystem=$v.FileSystem; VolumeSerial=$v.VolumeSerialNumber; VolumeSize=$v.Size; Free=$v.FreeSpace} } } }; ConvertTo-Json -InputObject @($rows) -Depth 5'''
identity_result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True, check=True, timeout=90)
identities = json.loads(identity_result.stdout)
matching = [r for r in identities if r['Drive'] == 'E:' and r['Label'] == 'KESTREL_A64' and r['VolumeSerial'] == 'USB_VOLUME_SERIAL' and r['Filesystem'] == 'FAT32' and r['Interface'] == 'USB' and r['Model'] == 'Kingston DataTraveler 3.0 USB Device' and r['DiskSize'] == 61985710080 and r['Offset'] == 1048576 and r['PartitionSize'] == 17179869184]
if len(matching) != 1:
    raise SystemExit('REFUSED: current physical USB identity differs or is ambiguous')
if not SOURCE.is_dir() or OUT.exists():
    raise SystemExit('REFUSED: native boot missing or output already exists')
if shutil.disk_usage(PROJECT).free < 1024 ** 3:
    raise SystemExit('REFUSED: less than 1 GiB local space for evidence')
if (USB / 'KESTREL-LOG-TARGET').read_text(encoding='utf-8').strip() != 'KESTREL_A64_USB_CAPTURE_V1':
    raise SystemExit('REFUSED: capture marker mismatch')
OUT.mkdir(exist_ok=False)
print('ARCHIVE', OUT, flush=True)
save('usb-identity.json', matching[0])

files = sorted(SOURCE.rglob('*'))
if any(p.is_symlink() for p in files):
    raise SystemExit('REFUSED: unexpected link inside native evidence')
inventory = []
for path in files:
    if not path.is_file():
        continue
    relative = path.relative_to(SOURCE)
    target = OUT / 'usb-logs' / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    before = digest(path)
    with path.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    after = digest(path)
    copied = digest(target)
    if not before == after == copied:
        raise SystemExit('REFUSED: source changed or archived bytes differ: ' + str(path))
    inventory.append({'path': relative.as_posix(), 'bytes': target.stat().st_size, 'sha256': copied})
save('archive-manifest.json', {'boot_id': BOOT_ID, 'source': str(SOURCE), 'files': inventory, 'file_count': len(inventory), 'bytes': sum(r['bytes'] for r in inventory)})

critical = []
for relative, (expected_hash, expected_bytes) in EXPECTED.items():
    path = USB / relative
    actual_hash = digest(path)
    actual_bytes = path.stat().st_size
    row = {'path': str(path), 'sha256': actual_hash, 'bytes': actual_bytes, 'matches_expected': actual_hash == expected_hash and actual_bytes == expected_bytes}
    critical.append(row)
    print('USB_HASH', json.dumps(row), flush=True)
save('usb-critical-readback.json', critical)
menu = (USB / 'boot/grub/grub.cfg').read_text(encoding='utf-8')
with (OUT / 'on-device-grub.cfg').open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(menu)
entries = re.split(r'(?m)^menuentry ', menu)[1:]
menu_rows = [{'number': i + 1, 'title': entry.splitlines()[0], 'linux': re.findall(r'(?m)^\s*linux\s+(.+)$', entry)} for i, entry in enumerate(entries)]
save('menu-audit.json', {'default': re.search(r'(?m)^set default=(\d+)$', menu).group(1), 'entries': menu_rows, 'old_number_8_uses_shared_updated_image': '/EFI/Linux/kestrel-live.efi' in ' '.join(menu_rows[7]['linux']), 'selectable_dt24_image': any('/EFI/Linux/kestrel-live.efi' not in cmd and 'dt24' in cmd for r in menu_rows for cmd in r['linux'])})

logs = OUT / 'usb-logs'
status = (logs / '00-status.txt').read_text(encoding='utf-8')
proof = (logs / '07-typed-command.txt').read_text(encoding='utf-8')
fields = dict(line.split('=', 1) for line in proof.split('\n\n', 1)[0].splitlines() if '=' in line)
policy_path = PROJECT / 'builder/diagnostics/kestrel-graphics-policy.json'
policy = json.loads(policy_path.read_text(encoding='utf-8'))
required = set(policy['required_sensor_types'])
assert len(required) == policy['required_sensor_count'] == 20
capture = (logs / '04-userspace-status.txt').read_text(encoding='utf-8')
marks = list(re.finditer(r'(?m)^sample=(\d+)$', capture))
samples = []
for i, mark in enumerate(marks):
    end = marks[i + 1].start() if i + 1 < len(marks) else len(capture)
    block = capture[mark.end():end].strip('\n')
    lines = block.splitlines()
    readings = [{'zone': z, 'type': kind, 'temp_mc': int(value)} for z, kind, value in re.findall(r'(?m)^/sys/class/thermal/(thermal_zone\d+) ([\w.-]+)\n(-?\d+)$', block)]
    counts = collections.Counter(r['type'] for r in readings)
    missing = sorted(required.difference(counts))
    duplicate = sorted(k for k in required if counts[k] > 1)
    invalid = [r for r in readings if r['type'] in required and not policy['experiment_minimum_mc'] <= r['temp_mc'] < policy['experiment_stop_mc']]
    samples.append({'sample': int(mark.group(1)), 'uptime_s': float(lines[0].split()[0]), 'system_state': lines[1], 'readings': readings, 'missing_required': missing, 'duplicate_required': duplicate, 'invalid_required': invalid, 'required_pass': not (missing or duplicate or invalid)})
assert samples, 'no thermal samples parsed'
assert [s['sample'] for s in samples] == list(range(len(samples))), 'non-contiguous thermal sample IDs'
per_sensor = []
for kind in sorted(required):
    values = [r['temp_mc'] for sample in samples for r in sample['readings'] if r['type'] == kind]
    per_sensor.append({'type': kind, 'readings': len(values), 'minimum_mc': min(values) if values else None, 'maximum_mc': max(values) if values else None})
values = [r['temp_mc'] for sample in samples for r in sample['readings'] if r['type'] in required]
checks = {
    'all_usb_critical_hashes_match': all(r['matches_expected'] for r in critical),
    'boot_id_in_status_matches': ('boot_id=' + BOOT_ID) in status,
    'typed_boot_id_matches': fields.get('boot_id') == BOOT_ID,
    'typed_command_marker': proof.startswith('KESTREL_TYPED_COMMAND_OK\n'),
    'typed_systemd_overlay_bash_tty1': all(fields.get(k) == v for k, v in {'pid1': 'systemd', 'fstype': 'overlay', 'shell_comm': 'bash', 'tty': '/dev/tty1', 'multi_user': 'active', 'mode': 'typed'}.items()),
    'text_optout_graphics_zero': 'kestrel_graphics=0' in status,
    'firmware_logging_optin_absent': 'kestrel_efilog=1' not in status,
    'efi_pstore_disabled_in_cmdline': 'efi-pstore.pstore_disable=1' in status,
    'all_required_cpu_sensor_samples_pass': all(s['required_pass'] for s in samples),
}
summary = {
    'boot_id': BOOT_ID, 'collected_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'archive': str(OUT),
    'checks': checks, 'typed_proof_fields': fields, 'native_cpu_readings_observed': True,
    'thermal_policy_sha256': digest(policy_path), 'required_sensors': len(required), 'samples': len(samples),
    'complete_valid_cpu_samples': sum(s['required_pass'] for s in samples), 'required_cpu_reading_count': len(values),
    'minimum_cpu_c': min(values) / 1000, 'maximum_cpu_c': max(values) / 1000,
    'first_sample_uptime_s': samples[0]['uptime_s'], 'last_sample_uptime_s': samples[-1]['uptime_s'],
    'sample_span_s': round(samples[-1]['uptime_s'] - samples[0]['uptime_s'], 2),
    'system_states': dict(collections.Counter(s['system_state'] for s in samples)),
    'distinct_reported_thermal_types': sorted({r['type'] for s in samples for r in s['readings']}),
    'collector_window_finished_marker': 'KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED' in status,
    'checkpoint_status': (logs / 'checkpoint-status.log').read_text(encoding='utf-8'),
    'sensors': per_sensor,
    'limitations': ['A saved numeric CPU sample is not cooling/fan/thermal-control validation.', 'Graphics was disabled; no native Plasma/PAM/guard acceptance.', 'Helper revision=v2-dt24 is inherited helper identity, not an artifact hash.', 'FAT/wall-clock timestamps are not used as monotonic boot identity.', 'Shutdown acceptance requires separate kernel/journal review.'],
}
save('thermal-samples.json', samples)
save('native-summary.json', summary)
health = subprocess.run(['fsutil.exe', 'dirty', 'query', 'E:'], capture_output=True, text=True, timeout=30)
save('usb-dirty-query.json', {'returncode': health.returncode, 'stdout': health.stdout, 'stderr': health.stderr, 'repair_performed': False})
backup = BASE / 'usb-before-dt25b-20261018T110101253Z'
save('backup-inventory.json', [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(backup.rglob('*')) if p.is_file()])
print(json.dumps({k: v for k, v in summary.items() if k not in ('sensors', 'distinct_reported_thermal_types')}, indent=2), flush=True)
print('LOCAL_EVIDENCE_READY', OUT, flush=True)
sys.exit(0 if all(checks.values()) else 1)
