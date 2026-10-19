#!/usr/bin/env python3
"""File-only dt26 USB handoff: adds one opt-in bounded-graphics entry.

Adds E:/EFI/Linux/kestrel-live-dt26.efi (fresh file, readback-verified) and a
5th menu entry (rows 1-3 byte-identical, firmware exit stays last, default
stays entry 1 dt25b text). No kernel/DTB/SFS/firmware/log changes; no repair.
Default dry-run; --apply commits with staged writes, cache flush, readback.
"""
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
CANON = PROJECT / 'builder/live-grub-dt26.cfg'
CURRENT_MENU_SHA = '9c99836e41896defc99b3104eb3a65bf9c9d5d886c73a84cb7d58615078b4406'
DT26_SRC = BASE / 'dt26a3-candidate.efi'
DT26_SHA = '5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26'
DT26_BYTES = 244398080
DT26_REL = 'EFI/Linux/kestrel-live-dt26.efi'
MENU_REL = 'boot/grub/grub.cfg'
PROTECTED = ['EFI/Linux/kestrel-live.efi', 'EFI/Linux/kestrel-live-dt24.efi',
             'arch/aarch64/airootfs.sfs', 'EFI/BOOT/BOOTAA64.EFI',
             'boot/slim3-x126100.dtb', 'casper/vmlinuz', 'casper/initrd']
DT25B_SHA = 'b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753'
DT24_SHA = '4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02'
SFS_SHA = '5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c'

NEW_ENTRY = """menuentry 'FroodzOS dt26 - BOUNDED graphics diagnostic (opt-in)' {
    set gfxpayload=keep
    echo 'Supervised simpledrm/software test: the guard may refuse to a text console.'
    echo 'At most 180 seconds bounded; 80C thermal stop; USB logs ON, firmware OFF.'
    echo 'Photograph the screen; use poweroff normally; entry 1 stays the default.'
    linux /EFI/Linux/kestrel-live-dt26.efi kestrel_log=1 rd.log=console rd.log=file archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M $platform_cmdline console=tty1 loglevel=4 panic=0 module_blacklist=dispcc_x1e80100 kestrel_textboot=1 kestrel_console=tty1 kestrel_graphics=1 systemd.unit=multi-user.target systemd.show_status=1
    boot
}
"""
OLD_HEAD_A = "echo 'FroodzOS - Lenovo native tests (dt25b)'"
OLD_HEAD_B = "echo 'FroodzOS entries are text-only: USB logs ON, firmware capture OFF.'"
NEW_HEAD_A = "echo 'FroodzOS - Lenovo native tests (dt26 opt-in graphics)'"
NEW_HEAD_B = "echo 'Entries 1-2 text-only; entry 4 bounded graphics test. USB logs ON, firmware OFF.'"
EXIT_TITLE = 'Return to firmware boot menu'


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


def build_candidate(current):
    require(OLD_HEAD_A in current and OLD_HEAD_B in current, 'header base changed')
    text = current.replace(OLD_HEAD_A, NEW_HEAD_A, 1).replace(OLD_HEAD_B, NEW_HEAD_B, 1)
    marker = "menuentry '%s' {" % EXIT_TITLE
    require(text.count(marker) == 1, 'firmware exit entry not unique')
    return text.replace(marker, NEW_ENTRY + marker, 1)


def validate_candidate(raw, current_rows):
    require(b'\r' not in raw and raw.endswith(b'\n'), 'menu must be LF-only')
    text = raw.decode('ascii')
    rows = entries(text)
    require(len(rows) == 5 and text.count('menuentry ') == 5, 'expected five entries')
    require(re.findall(r'(?m)^set default=(.+)$', text) == ['0'], 'default must stay entry 1')
    require(re.findall(r'(?m)^set timeout=(.+)$', text) == ['30'], 'retain 30 second timeout')
    require(rows[0] == current_rows[0] and rows[1] == current_rows[1] and rows[2] == current_rows[2],
            'entries 1-3 must stay byte-identical')
    require(rows[4] == current_rows[3] and rows[4][0] == EXIT_TITLE, 'firmware exit must stay last')
    require('dt26' in rows[3][0] and 'graphics' in rows[3][0].lower(), 'entry 4 must be the dt26 graphics test')
    ref = linux_line(rows[0][1])
    new = linux_line(rows[3][1])
    require(new == ref.replace('/EFI/Linux/kestrel-live.efi', '/' + DT26_REL, 1).replace('kestrel_graphics=0', 'kestrel_graphics=1', 1),
            'dt26 linux line must differ from text entry only in UKI path and graphics flag')
    require(all(t in new.split() for t in ('kestrel_log=1', 'kestrel_textboot=1', 'kestrel_graphics=1', 'console=tty1', 'systemd.unit=multi-user.target')), 'unsafe dt26 entry flags')
    require('kestrel_efilog=1' not in new.split(), 'firmware capture opt-in forbidden')
    for _, body in rows[:3]:
        require('kestrel_graphics=1' not in body, 'graphics flag leaked into text/control entry')
    require("set platform_cmdline='clk_ignore_unused pd_ignore_unused efi-pstore.pstore_disable=1'" in text, 'missing platform/pstore safety')
    require(not any(t in text for t in ('initcall_blacklist=', 'boot_delay=', 'initcall_debug', 'kestrel_efilog=1')), 'retired/unsafe experiment in menu')
    return [{'number': i + 1, 'title': title} for i, (title, _) in enumerate(rows)]


def negative_tests(raw):
    text = raw.decode('ascii')
    current_rows = entries((USB / MENU_REL).read_bytes().decode('ascii'))
    cases = {
        'wrong_default': text.replace('set default=0', 'set default=3', 1),
        'graphics_in_text': text.replace('kestrel_graphics=0', 'kestrel_graphics=1', 1),
        'firmware_optin': text.replace('kestrel_log=1', 'kestrel_log=1 kestrel_efilog=1', 1),
        'wrong_console': text.replace('console=tty1', 'console=tty0', 1),
        'missing_pstore_disable': text.replace(' efi-pstore.pstore_disable=1', '', 1),
        'crlf': text.replace('\n', '\r\n'),
        'extra_entry': text + "menuentry 'retired' {\n    exit\n}\n",
    }
    for name, value in cases.items():
        try:
            validate_candidate(value.encode('ascii'), current_rows)
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
    report = {'mode': 'apply' if args.apply else 'dry-run', 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'usb_write_scope': [DT26_REL, MENU_REL], 'firmware_writes': 0, 'filesystem_repair': False, 'success': False}
    with output.open('x', encoding='utf-8') as receipt:
        try:
            require(DT26_SRC.stat().st_size == DT26_BYTES and sha(DT26_SRC) == DT26_SHA, 'dt26 source not audited build')
            raw_current = (USB / MENU_REL).read_bytes()
            require(sha(USB / MENU_REL) == CURRENT_MENU_SHA, 'USB menu changed since reviewed state')
            current_rows = entries(raw_current.decode('ascii'))
            require(len(current_rows) == 4, 'expected current four-entry menu')
            candidate = build_candidate(raw_current.decode('ascii'))
            report['entries'] = validate_candidate(candidate.encode('ascii'), current_rows)
            report['menu_sha256'] = hashlib.sha256(candidate.encode('ascii')).hexdigest()
            report['menu_bytes'] = len(candidate.encode('ascii'))
            report['contract_tests'] = negative_tests(candidate.encode('ascii'))
            cand_path = run_dir / 'candidate.cfg'
            if not cand_path.exists():
                cand_path.write_text(candidate, encoding='ascii', newline='\n')
            wsl_path = '/mnt/d/CachyOS-ARM64/testing/boot-failure/' + run_dir.name + '/candidate.cfg'
            grammar = subprocess.run(['wsl.exe', '-d', 'CachyOSBuilder', '-u', 'root', '--', '/usr/sbin/grub-script-check', wsl_path], capture_output=True, text=True, timeout=60)
            report['grub_script_check'] = {'exit': grammar.returncode}
            require(grammar.returncode == 0, 'real GRUB syntax check failed: ' + grammar.stderr)
            before_id = identity()
            report['identity_before'] = before_id
            require((USB / 'KESTREL-LOG-TARGET').read_text(encoding='ascii').strip() == 'KESTREL_A64_USB_CAPTURE_V1', 'USB capture marker mismatch')
            protected_before = hashes(USB, PROTECTED)
            require(protected_before['EFI/Linux/kestrel-live.efi'] == {'bytes': 244424704, 'sha256': DT25B_SHA}, 'dt25b differs')
            require(protected_before['EFI/Linux/kestrel-live-dt24.efi'] == {'bytes': 244503552, 'sha256': DT24_SHA}, 'dt24 recovery differs')
            require(protected_before['arch/aarch64/airootfs.sfs'] == {'bytes': 1748525056, 'sha256': SFS_SHA}, 'shared SFS differs')
            require(not (USB / DT26_REL).exists(), 'dt26 target already exists; fresh file only')
            require(shutil.disk_usage(USB).free >= DT26_BYTES + 1024 * 1024, 'insufficient USB space')
            log_paths = sorted(p.relative_to(USB).as_posix() for p in (USB / 'Logs').rglob('*') if p.is_file())
            logs_before = hashes(USB, log_paths)
            report['protected_before_ok'] = True
            report['logs_preserved_count'] = len(log_paths)
            if not args.apply:
                report['success'] = True
                report['usb_files_written'] = []
            else:
                require(identity() == before_id, 'USB association changed before commit')
                require(sha(USB / MENU_REL) == CURRENT_MENU_SHA, 'USB menu changed before commit')
                copy_exclusive(USB / MENU_REL, run_dir / 'usb-before.cfg')
                CANON.write_text(candidate, encoding='ascii', newline='\n')
                require(sha(CANON) == report['menu_sha256'], 'canonical candidate mismatch')
                staged_uki = USB / (DT26_REL + '.pending-' + run_dir.name)
                staged_menu = (USB / MENU_REL).with_name('grub.cfg.pending-' + run_dir.name)
                require(not staged_uki.exists() and not staged_menu.exists(), 'staging collision; preserve partial attempt')
                copy_exclusive(DT26_SRC, staged_uki)
                require(sha(staged_uki) == DT26_SHA, 'staged UKI mismatch')
                staged_uki.rename(USB / DT26_REL)
                require(sha(USB / DT26_REL) == DT26_SHA, 'dt26 UKI readback failed')
                copy_exclusive(Path(cand_path), staged_menu)
                require(sha(staged_menu) == report['menu_sha256'], 'staged menu mismatch')
                os.replace(staged_menu, USB / MENU_REL)
                flush = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', "$ErrorActionPreference='Stop'; Write-VolumeCache -DriveLetter E -ErrorAction Stop"], capture_output=True, text=True, timeout=60)
                report['volume_cache_flush'] = {'exit': flush.returncode}
                require(flush.returncode == 0, 'volume cache flush failed')
                require(identity() == before_id, 'USB association changed after commit')
                require(sha(USB / MENU_REL) == report['menu_sha256'], 'final menu readback mismatch')
                require(sha(USB / DT26_REL) == DT26_SHA, 'final UKI readback mismatch')
                require(hashes(USB, PROTECTED) == protected_before, 'protected boot payload changed')
                require(hashes(USB, log_paths) == logs_before, 'prior USB log bytes changed')
                require(sorted(p.relative_to(USB).as_posix() for p in (USB / 'Logs').rglob('*') if p.is_file()) == log_paths, 'prior log file set changed')
                report['usb_files_written'] = [DT26_REL, MENU_REL]
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
    print('DT26_HANDOFF_RECEIPT', output, flush=True)


if __name__ == '__main__':
    main()
