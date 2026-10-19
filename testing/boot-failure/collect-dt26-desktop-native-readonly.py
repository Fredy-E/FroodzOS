#!/usr/bin/env python3
"""Archive both new native graphics boots, hash/readback, never write to USB."""
import collections
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

PROJECT = Path('D:/CachyOS-ARM64')
USB = Path('E:/')
BOOT_IDS = ['54368727-c22b-4b6c-91b6-428b39dd2cbe', '7f05d7e0-f801-4316-b55c-8daa08d353c5']
EXPECTED = {
    'EFI/Linux/kestrel-live-dt26.efi': ('5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26', 244398080),
    'EFI/Linux/kestrel-live.efi': ('b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753', 244424704),
    'EFI/Linux/kestrel-live-dt24.efi': ('4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02', 244503552),
    'boot/grub/grub.cfg': ('1249291c07d42c4b07c456dfe4fb93c4ab8c792ec3b36672bde33be8a27ac935', 3424),
    'arch/aarch64/airootfs.sfs': ('5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c', 1748525056),
}

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(p, obj):
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2)
        f.write('\n')

ps = "$ErrorActionPreference='Stop'; $rows=@(); foreach($d in @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object InterfaceType -eq 'USB')) { foreach($p in @(Get-CimAssociatedInstance -InputObject $d -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) { foreach($v in @(Get-CimAssociatedInstance -InputObject $p -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15)) { $rows += [pscustomobject]@{Disk=$d.DeviceID; Model=$d.Model; DiskSize=$d.Size; Interface=$d.InterfaceType; PartitionSize=$p.Size; Offset=$p.StartingOffset; Drive=$v.DeviceID; Label=$v.VolumeName; Filesystem=$v.FileSystem; VolumeSerial=$v.VolumeSerialNumber} } } }; ConvertTo-Json -InputObject @($rows) -Depth 5"
rows = json.loads(subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, text=True, check=True, timeout=90).stdout)
match = [r for r in rows if r['Drive'] == 'E:' and r['Label'] == 'KESTREL_A64' and r['VolumeSerial'] == 'USB_VOLUME_SERIAL' and r['Filesystem'] == 'FAT32' and r['Interface'] == 'USB' and r['Model'] == 'Kingston DataTraveler 3.0 USB Device' and r['DiskSize'] == 61985710080 and r['Offset'] == 1048576 and r['PartitionSize'] == 17179869184]
require(len(match) == 1, 'physical identity mismatch')
require((USB/'KESTREL-LOG-TARGET').read_text().strip() == 'KESTREL_A64_USB_CAPTURE_V1', 'marker mismatch')
require(all((USB/'Logs'/('boot-'+bid)).is_dir() for bid in BOOT_IDS), 'expected boot missing')
require(shutil.disk_usage(PROJECT).free > 10*1024**3, 'D reserve under 10GiB')
out = PROJECT/'testing/boot-failure'/('native-dt26-desktop-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
out.mkdir(exist_ok=False)
save(out/'usb-identity.json', match[0])
critical = []
for rel, (h, n) in EXPECTED.items():
    p = USB/rel
    row = {'path':rel, 'bytes':p.stat().st_size, 'sha256':sha(p)}
    row['matches_expected'] = row['bytes'] == n and row['sha256'] == h
    critical.append(row)
save(out/'usb-critical-readback.json', critical)
require(all(r['matches_expected'] for r in critical), 'current USB critical bytes differ')
policy = json.loads((PROJECT/'builder/diagnostics/kestrel-graphics-policy.json').read_text())
required = set(policy['required_sensor_types'])
require(len(required) == policy['required_sensor_count'] == 20, 'sensor policy count')
boots = []
for bid in BOOT_IDS:
    source = USB/'Logs'/('boot-'+bid)
    dest = out/('boot-'+bid)
    dest.mkdir(exist_ok=False)
    inventory = []
    for p in sorted(source.rglob('*')):
        require(not p.is_symlink(), 'unexpected symlink in evidence')
        if not p.is_file():
            continue
        rel = p.relative_to(source)
        target = dest/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(p)
        with p.open('rb') as f, target.open('xb') as g:
            shutil.copyfileobj(f, g)
        require(before == sha(p) == sha(target), 'unstable/corrupt archived bytes')
        inventory.append({'path':rel.as_posix(), 'bytes':target.stat().st_size, 'sha256':before})
    save(dest/'archive-manifest.json', {'boot_id':bid, 'files':inventory, 'file_count':len(inventory), 'bytes':sum(r['bytes'] for r in inventory)})
    def text(name):
        p = dest/name
        return p.read_text(encoding='utf-8', errors='replace') if p.is_file() else ''
    pre = json.loads(text('08-graphics-preflight.json')) if text('08-graphics-preflight.json') else None
    cleanup = json.loads(text('09-graphics-status.json')) if text('09-graphics-status.json') else None
    journal = text('03-userspace-journal.log')
    graphics = text('10-graphics-journal.log')
    status = text('00-status.txt')
    samples = []
    capture = text('04-userspace-status.txt')
    marks = list(re.finditer(r'(?m)^sample=(\d+)$', capture))
    for i, mark in enumerate(marks):
        block = capture[mark.end():marks[i+1].start() if i+1<len(marks) else len(capture)].strip('\n')
        lines = block.splitlines()
        readings = [(kind, int(value)) for kind,value in re.findall(r'(?m)^/sys/class/thermal/thermal_zone\d+ ([\w.-]+)\n(-?\d+)$', block) if kind in required]
        counts = collections.Counter(kind for kind,_ in readings)
        missing = sorted(required-set(counts))
        duplicate = sorted(k for k,n in counts.items() if n != 1)
        invalid = [(k,v) for k,v in readings if not 5000 <= v < 80000]
        samples.append({'sample':int(mark.group(1)), 'uptime_s':float(lines[0].split()[0]), 'state':lines[1] if len(lines)>1 else '', 'readings':dict(readings), 'missing':missing, 'duplicate':duplicate, 'out_of_range':invalid, 'complete_valid':not(missing or duplicate or invalid)})
    values = [v for s in samples for v in s['readings'].values()]
    save(dest/'thermal-analysis.json', samples)
    nm = [ln for ln in journal.splitlines() if 'NetworkManager[' in ln and any(s in ln for s in ('device (', 'state is now', 'connectivity', 'new '))]
    relevant = [ln for ln in journal.splitlines() if any(s in ln for s in ('kwin_wayland', 'startplasma', 'llvmpipe', 'Session started', 'New session', 'DEADLINE_REACHED', 'SESSION_ACCEPTED', 'reboot: Power down', 'Syncing filesystems', 'Reached target System Power Off'))]
    save(dest/'runtime-findings.json', {'network_manager':nm, 'runtime':relevant})
    sensors = pre.get('thermal',{}).get('sensors',{}) if pre else {}
    boots.append({'boot_id':bid, 'file_count':len(inventory), 'bytes':sum(r['bytes'] for r in inventory), 'status_boot_id_matches':('boot_id='+bid) in status, 'graphics_cmdline': 'kestrel_graphics=1' in status, 'preflight_passed':pre.get('passed') if pre else None, 'preflight_cpu_20_exact':set(sensors)==required, 'drm':pre.get('drm_snapshot') if pre else None, 'session_accepted':'KESTREL_GRAPHICS_SESSION_ACCEPTED_MONITORING' in graphics, 'cleanup':cleanup, 'sample_count':len(samples), 'complete_cpu_samples':sum(s['complete_valid'] for s in samples), 'raw_all_cpu_samples_valid':bool(samples) and all(s['complete_valid'] for s in samples), 'cpu_min_c':min(values)/1000 if values else None, 'cpu_max_c':max(values)/1000 if values else None, 'network_lines':nm, 'user_desktop_report_not_unique_to_this_boot':True, 'input_function_not_yet_confirmed':True, 'final_hardware_poweroff_not_proven':True})
report={'archive':str(out), 'usb_read_only':True, 'boot_count':len(boots), 'boot_ids_unique':len({b['boot_id'] for b in boots})==len(BOOT_IDS), 'total_files':sum(b['file_count'] for b in boots), 'total_bytes':sum(b['bytes'] for b in boots), 'critical_bytes_all_match':True, 'boots':boots}
save(out/'result.json', report)
print(json.dumps(report,indent=2))
