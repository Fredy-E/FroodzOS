#!/usr/bin/env python3
"""Identity-gated file-only menu cleanup; default dry-run, --apply commits."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

PROJECT = Path('D:/CachyOS-ARM64')
BASE = PROJECT / 'testing/boot-failure'
USB = Path('E:/')
CONFIG = PROJECT / 'builder/live-grub.cfg'
REFERENCE = BASE / 'dt25b-grub.cfg'
FALLBACK = BASE / 'usb-before-dt25b-20261018T110101253Z/kestrel-live-dt24.efi'
FALLBACK_REL = 'EFI/Linux/kestrel-live-dt24.efi'
CURRENT_REL = 'EFI/Linux/kestrel-live.efi'
MENU_REL = 'boot/grub/grub.cfg'
OLD_MENU_SHA = 'a4bec7016a798e82f7d6f2c546b8829d072075d36e8b61f61ed88e48035740de'
DT25B_SHA = 'b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753'
DT24_SHA = '4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02'
SFS_SHA = '5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c'
PROTECTED = [CURRENT_REL, 'arch/aarch64/airootfs.sfs', 'EFI/BOOT/BOOTAA64.EFI', 'boot/slim3-x126100.dtb', 'casper/vmlinuz', 'casper/initrd']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def copy_exclusive(source, target):
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    require(sha(source) == sha(target), 'copy readback mismatch: ' + str(target))


def entries(text):
    return [(m.group(1), m.group(2)) for m in re.finditer(r"(?ms)^menuentry '([^']+)' \{\n(.*?)^\}\n", text)]


def linux_line(body):
    rows = re.findall(r'(?m)^    linux (.+)$', body)
    require(len(rows) == 1, 'expected exactly one linux line')
    return rows[0]


def validate_menu(raw):
    require(b'\r' not in raw and raw.endswith(b'\n'), 'menu must be LF-only')
    text = raw.decode('ascii')
    rows = entries(text)
    require(len(rows) == 4 and text.count('menuentry ') == 4, 'expected four entries')
    require(re.findall(r'(?m)^set default=(.+)$', text) == ['0'], 'default must be first entry')
    require(re.findall(r'(?m)^set timeout=(.+)$', text) == ['30'], 'retain 30 second timeout')
    require('dt25b' in rows[0][0] and 'dt24' in rows[1][0], 'incorrect image titles/order')
    old_rows = entries(REFERENCE.read_text(encoding='ascii'))
    old_native = next(body for title, body in old_rows if title == 'Kestrel dt25b - SYSTEMD TEXT + TSENS check (default)')
    require(linux_line(rows[0][1]) == linux_line(old_native), 'dt25b native-tested cmdline changed')
    recovery = linux_line(rows[1][1])
    require(recovery == linux_line(old_native).replace('/' + CURRENT_REL, '/' + FALLBACK_REL, 1), 'recovery must differ only in its distinct UKI path')
    for _, body in rows[:2]:
        cmd = linux_line(body)
        require(all(token in cmd.split() for token in ('kestrel_log=1', 'kestrel_textboot=1', 'kestrel_graphics=0', 'console=tty1', 'systemd.unit=multi-user.target')), 'unsafe text entry flags')
        require('kestrel_efilog=1' not in cmd.split(), 'firmware capture opt-in forbidden')
    old_control = next((title, body) for title, body in old_rows if title.startswith('Ubuntu Concept'))
    require(rows[2] == old_control, 'Ubuntu control entry must remain byte-identical')
    require(rows[3] == ('Return to firmware boot menu', '    exit\n'), 'firmware exit entry changed')
    require("set platform_cmdline='clk_ignore_unused pd_ignore_unused efi-pstore.pstore_disable=1'" in text, 'missing platform/pstore safety')
    old_platform = REFERENCE.read_text(encoding='ascii').split("set platform_cmdline=", 1)[1].split('\nmenuentry ', 1)[0]
    new_platform = text.split("set platform_cmdline=", 1)[1].split('\nmenuentry ', 1)[0]
    require(new_platform == old_platform, 'native platform workaround block changed')
    require(not any(token in text for token in ('initcall_blacklist=', 'boot_delay=', 'initcall_debug', 'kestrel_graphics=1', 'kestrel_efilog=1')), 'retired/unsafe experiment in menu')
    return [{'number': i + 1, 'title': title, 'linux': re.findall(r'(?m)^    linux (.+)$', body)} for i, (title, body) in enumerate(rows)]


def negative_tests(raw):
    text = raw.decode('ascii')
    cases = {
        'wrong_default': text.replace('set default=0', 'set default=1', 1),
        'shared_recovery_image': text.replace('/' + FALLBACK_REL, '/' + CURRENT_REL, 1),
        'firmware_optin': text.replace('kestrel_log=1', 'kestrel_log=1 kestrel_efilog=1', 1),
        'graphics_optin': text.replace('kestrel_graphics=0', 'kestrel_graphics=1', 1),
        'wrong_native_console': text.replace('console=tty1', 'console=tty0', 1),
        'missing_control_dtb': text.replace('    devicetree /boot/slim3-x126100.dtb\n', '', 1),
        'missing_pstore_disable': text.replace(' efi-pstore.pstore_disable=1', '', 1),
        'missing_memory_workaround': text.replace('        cutmem 0x8800000000 0x8fffffffff\n', '', 1),
        'extra_entry': text + "menuentry 'retired' {\n    exit\n}\n",
        'crlf': text.replace('\n', '\r\n'),
    }
    for name, value in cases.items():
        try:
            validate_menu(value.encode('ascii'))
        except RuntimeError:
            continue
        raise RuntimeError('negative test did not reject: ' + name)
    return {'valid_candidate': True, 'negative_rejections': sorted(cases), 'tests_passed': len(cases) + 1}


def identity():
    script = "$ErrorActionPreference='Stop'; $rows=@(); foreach($d in @(Get-CimInstance Win32_DiskDrive -OperationTimeoutSec 15 | Where-Object InterfaceType -eq 'USB')) { foreach($p in @(Get-CimAssociatedInstance -InputObject $d -Association Win32_DiskDriveToDiskPartition -OperationTimeoutSec 15)) { foreach($v in @(Get-CimAssociatedInstance -InputObject $p -Association Win32_LogicalDiskToPartition -OperationTimeoutSec 15)) { $rows += [pscustomobject]@{Disk=$d.DeviceID; Model=$d.Model; DiskSize=$d.Size; Interface=$d.InterfaceType; Partition=$p.DeviceID; PartitionSize=$p.Size; Offset=$p.StartingOffset; Drive=$v.DeviceID; Label=$v.VolumeName; Filesystem=$v.FileSystem; VolumeSerial=$v.VolumeSerialNumber} } } }; ConvertTo-Json -InputObject @($rows) -Depth 4"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True, check=True, timeout=90)
    rows = json.loads(result.stdout)
    matches = [r for r in rows if r['Drive'] == 'E:' and r['Label'] == 'KESTREL_A64' and r['Filesystem'] == 'FAT32' and r['VolumeSerial'] == 'USB_VOLUME_SERIAL' and r['Interface'] == 'USB' and r['Model'] == 'Kingston DataTraveler 3.0 USB Device' and r['DiskSize'] == 61985710080 and r['PartitionSize'] == 17179869184 and r['Offset'] == 1048576]
    require(len(matches) == 1, 'physical USB identity mismatch or ambiguity')
    return matches[0]


def hashes(root, paths):
    return {rel: {'bytes': (root / rel).stat().st_size, 'sha256': sha(root / rel)} for rel in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    require(run_dir.is_relative_to(BASE.resolve()) and run_dir.is_dir(), 'run directory must exist in project evidence tree')
    output = run_dir / ('apply-receipt.json' if args.apply else 'dry-run-receipt.json')
    require(not output.exists(), 'refusing to overwrite existing receipt')
    report = {'mode': 'apply' if args.apply else 'dry-run', 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': str(CONFIG), 'run_dir': str(run_dir), 'success': False, 'usb_write_scope': [FALLBACK_REL, MENU_REL], 'firmware_writes': 0, 'filesystem_repair': False}
    with output.open('x', encoding='utf-8') as receipt:
        try:
            require(sha(REFERENCE) == OLD_MENU_SHA, 'historical reference changed')
            raw = CONFIG.read_bytes()
            report['entries'] = validate_menu(raw)
            report['menu_sha256'] = hashlib.sha256(raw).hexdigest()
            report['menu_bytes'] = len(raw)
            report['contract_tests'] = negative_tests(raw)
            grammar = subprocess.run(['wsl.exe', '-d', 'CachyOSBuilder', '-u', 'root', '--', '/usr/sbin/grub-script-check', '/mnt/d/CachyOS-ARM64/builder/live-grub.cfg'], capture_output=True, text=True, timeout=60)
            report['grub_script_check'] = {'exit': grammar.returncode, 'stdout': grammar.stdout, 'stderr': grammar.stderr}
            require(grammar.returncode == 0, 'real GRUB syntax check failed')
            before_id = identity()
            report['identity_before'] = before_id
            require((USB / 'KESTREL-LOG-TARGET').read_text(encoding='ascii').strip() == 'KESTREL_A64_USB_CAPTURE_V1', 'USB capture marker mismatch')
            require(sha(USB / MENU_REL) == OLD_MENU_SHA, 'USB menu changed since reviewed state')
            require(FALLBACK.stat().st_size == 244503552 and sha(FALLBACK) == DT24_SHA, 'dt24 source not baseline')
            protected_before = hashes(USB, PROTECTED)
            require(protected_before[CURRENT_REL] == {'bytes': 244424704, 'sha256': DT25B_SHA}, 'current dt25b differs')
            require(protected_before['arch/aarch64/airootfs.sfs'] == {'bytes': 1748525056, 'sha256': SFS_SHA}, 'shared SFS differs')
            log_paths = sorted(p.relative_to(USB).as_posix() for p in (USB / 'Logs').rglob('*') if p.is_file())
            logs_before = hashes(USB, log_paths)
            target = USB / FALLBACK_REL
            if target.exists():
                require(target.stat().st_size == 244503552 and sha(target) == DT24_SHA, 'existing recovery path has unexpected bytes')
            require(shutil.disk_usage(USB).free >= 2 * FALLBACK.stat().st_size + 1024 * 1024, 'insufficient USB space')
            report['protected_before'] = protected_before
            report['logs_preserved_count'] = len(log_paths)
            report['dt24_source_sha256'] = DT24_SHA
            if not args.apply:
                report['success'] = True
                report['usb_files_written'] = []
            else:
                require(identity() == before_id, 'USB association changed before commit')
                require(hashlib.sha256(CONFIG.read_bytes()).hexdigest() == report['menu_sha256'], 'candidate changed after validation')
                require(sha(USB / MENU_REL) == OLD_MENU_SHA, 'USB menu changed before commit')
                copy_exclusive(USB / MENU_REL, run_dir / 'usb-before.cfg')
                copy_exclusive(CONFIG, run_dir / 'candidate.cfg')
                staged_fallback = target.with_name(target.name + '.pending-' + run_dir.name)
                staged_menu = (USB / MENU_REL).with_name('grub.cfg.pending-' + run_dir.name)
                require(not staged_fallback.exists() and not staged_menu.exists(), 'staging collision; preserve partial attempt')
                if not target.exists():
                    copy_exclusive(FALLBACK, staged_fallback)
                    require(sha(staged_fallback) == DT24_SHA, 'staged dt24 mismatch')
                    staged_fallback.rename(target)
                require(sha(target) == DT24_SHA, 'recovery readback failed before menu switch')
                copy_exclusive(CONFIG, staged_menu)
                require(sha(staged_menu) == report['menu_sha256'], 'staged menu mismatch')
                os.replace(staged_menu, USB / MENU_REL)
                flush = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', "$ErrorActionPreference='Stop'; Write-VolumeCache -DriveLetter E -ErrorAction Stop"], capture_output=True, text=True, timeout=60)
                report['volume_cache_flush'] = {'exit': flush.returncode, 'stdout': flush.stdout, 'stderr': flush.stderr}
                require(flush.returncode == 0, 'volume cache flush failed')
                require(identity() == before_id, 'USB association changed after commit')
                require(sha(USB / MENU_REL) == report['menu_sha256'], 'final menu readback mismatch')
                require(sha(target) == DT24_SHA, 'final recovery readback mismatch')
                require(hashes(USB, PROTECTED) == protected_before, 'protected boot payload changed')
                require(hashes(USB, log_paths) == logs_before, 'prior USB log bytes changed')
                require(sorted(p.relative_to(USB).as_posix() for p in (USB / 'Logs').rglob('*') if p.is_file()) == log_paths, 'prior log file set changed')
                report['usb_files_written'] = [FALLBACK_REL, MENU_REL]
                report['protected_after_equal'] = True
                report['prior_logs_unchanged'] = True
                report['success'] = True
            report['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        except Exception as error:
            report['error'] = str(error)
            raise
        finally:
            json.dump(report, receipt, indent=2)
            receipt.write('\n')
            receipt.flush()
            os.fsync(receipt.fileno())
    print(json.dumps(report, indent=2), flush=True)
    print('CLEAN_MENU_RECEIPT', output, flush=True)


if __name__ == '__main__':
    main()
