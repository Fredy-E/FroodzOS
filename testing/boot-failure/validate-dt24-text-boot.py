#!/usr/bin/env python3
"""Exercise dt24 default entry through EFI, normal systemd and typed getty input."""
import argparse
import hashlib
import json
import os
import re
import select
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='qemu-dt24-menu8-text-fw-off-v2')
parser.add_argument('--deadline', type=int, default=600)
args = parser.parse_args()
assert re.fullmatch('[a-z0-9-]+', args.tag) and 60 <= args.deadline <= 900
P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
image = B / (args.tag + '.fat')
log_path = T / (args.tag + '.log')
result_path = T / (args.tag + '-result.json')
extract = B / (args.tag + '-extracted')
assert not any(p.exists() for p in [image, log_path, result_path, extract]), 'Use a fresh evidence tag'
audit = json.loads((T / 'dt24-artifact-audit.json').read_text())
expected = audit['uki_sha256']
subprocess.run(['python3', str(T / 'prepare-log-validation.py'), '--revision', 'v2-dt24',
                '--tag', args.tag, '--menu', str(T / 'dt24-grub.cfg'), '--systemd'], check=True)
cfg_path = T / (args.tag + '-grub.cfg')
cfg = cfg_path.read_text()
cfg = re.sub(r'^set default=\d+$', 'set default=7', cfg, flags=re.M)
cfg = cfg.replace('kestrel_efilog=1', '')
cfg = cfg.replace('kestrel_console=tty1', 'kestrel_console=ttyAMA0').replace('console=tty1', 'console=ttyAMA0,115200')
entry = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', cfg, re.M | re.S)[7]
# Required differences from native are serial routing and removal of firmware opt-in.
assert 'init=' not in entry and 'kestrel_efilog=1' not in entry
assert 'kestrel_console=ttyAMA0' in entry and 'systemd.unit=multi-user.target' in entry
assert 'kestrel_textboot=1' in entry
cfg_path.write_text(cfg)
pt = json.loads(subprocess.check_output(['sfdisk', '--json', str(image)]))['partitiontable']
fs = str(image) + '@@' + str(pt['partitions'][0]['start'] * pt['sectorsize'])
subprocess.run(['mcopy', '-o', '-i', fs, str(cfg_path), '::/boot/grub/grub.cfg'], check=True)
reader = subprocess.Popen(['mtype', '-i', fs, '::/EFI/Linux/kestrel-live.efi'], stdout=subprocess.PIPE)
packed_sha = hashlib.file_digest(reader.stdout, 'sha256').hexdigest()
assert reader.wait() == 0 and packed_sha == expected
assert subprocess.check_output(['mtype', '-i', fs, '::/boot/grub/grub.cfg']).decode() == cfg
cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53', '-accel', 'tcg',
       '-m', '2048', '-smp', '2', '-bios', str(T / 'uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd'),
       '-device', 'qemu-xhci', '-drive', 'if=none,id=stick,format=raw,file=' + str(image),
       '-device', 'usb-storage,drive=stick', '-nographic', '-no-reboot', '-monitor', 'none']
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
start = time.monotonic()
output = b''
sent = False
reason = 'deadline'
with log_path.open('xb') as log:
    try:
        while time.monotonic() - start < args.deadline and proc.poll() is None:
            if not select.select([proc.stdout], [], [], 1)[0]:
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                reason = 'eof'
                break
            output += chunk
            log.write(chunk)
            log.flush()
            clean = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', output)
            multi = bool(re.search(rb'Reached target [^\r\n]*Multi-User System', clean))
            if not sent and re.search(rb'(?:^|[\r\n])KESTREL-TEXT# ', clean) and multi:
                # This arrives through the getty TTY after Bash startup; no init= shell.
                command = 'kestrel-proof; printf "\\nKESTREL_INPUT_ROUNDTRIP\\n"; sleep 5; sync; poweroff\n'
                proc.stdin.write(command.encode())
                proc.stdin.flush()
                sent = True
            if b'Kernel panic' in output:
                reason = 'kernel-panic'
                break
            if b'Falling back to interactive prompt' in output:
                reason = 'initramfs-emergency'
                break
            if b'reboot: Power down' in output:
                reason = 'poweroff'
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        rest = proc.stdout.read()
        output += rest
        log.write(rest)
extract.mkdir()
copy = subprocess.run(['mcopy', '-s', '-i', fs, '::/Logs/*', str(extract) + '/'], text=True, capture_output=True)
files = {p.relative_to(extract).as_posix(): p.stat().st_size for p in extract.rglob('*') if p.is_file()}


def read(leaf):
    matches = list(extract.rglob(leaf))
    return matches[0].read_text(errors='replace') if len(matches) == 1 else ''


text = output.decode(errors='replace')
clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
startup = read('06-text-startup.txt')
typed = read('07-typed-command.txt')
status = read('00-status.txt')
modules = typed.split('=== runtime modules ===')[-1].split('=== enumerated input devices')[0]
checks = {
    'fixture_candidate_readback_verified': packed_sha == expected,
    'native_entry_normal_init_retained': 'init=' not in entry,
    'firmware_flag_removed_for_virtual_test': 'kestrel_efilog=1' not in entry,
    'firmware_capture_off': 'firmware=0' in read('checkpoint-status.log'),
    'grub_menu': 'KESTREL_EFI_MENU_REACHED' in text,
    'kernel_started': 'Linux version 7.3.0-rc3' in read('01-kernel-kmsg.log'),
    'text_staged': 'KESTREL_TEXT_CONSOLE_STAGED' in text,
    'multi_user_reached': bool(re.search(r'Reached target [^\r\n]*Multi-User System', clean)),
    'prompt_and_target_before_input': sent,
    'bash_startup_recovered': 'KESTREL_BASH_STARTED' in startup and 'shell_comm=bash' in startup,
    'typed_command_proof_recovered': 'KESTREL_TYPED_COMMAND_OK' in typed,
    'normal_systemd_pid1': 'pid1=systemd' in startup and 'pid1=systemd' in typed,
    'live_overlay': 'fstype=overlay' in typed,
    'getty_tty': 'tty=/dev/ttyAMA0' in typed,
    'bash_not_pid1': bool(re.search(r'^shell_pid=(?!1$)[0-9]+$', typed, re.M)),
    'userspace_logger_started': 'KESTREL_USERSPACE_LOGGER_STARTED' in status,
    'userspace_journal_captured': bool(read('03-userspace-journal.log')),
    'overlay_mount_recorded': 'KESTREL_OVERLAY_ROOT_READY' in status,
    'no_panic_or_wsl_init': not any(s in text for s in ['Kernel panic', 'init-distro', 'WSL (']),
    'normal_shutdown': 'reboot: Power down' in text,
    'shutdown_observed_before_deadline': reason == 'poweroff',
    'multi_user_active_at_typed_proof': 'multi_user=active' in typed,
    'captured_logs_copy_succeeded': copy.returncode == 0,
}
for module in ['gpi', 'i2c_qcom_geni', 'phy_nxp_ptn3222', 'qrtr', 'qrtr_smd', 'i2c_hid', 'i2c_hid_of', 'hid_generic']:
    checks['runtime_' + module] = bool(re.search(r'^' + module + r'\s+\d+\s', modules, re.M))
report = {'passed': all(checks.values()), 'revision': 'v2-dt24', 'uki_sha256': expected,
          'checks': checks, 'stop_reason': reason, 'seconds': round(time.monotonic() - start, 2),
          'deadline_seconds': args.deadline, 'qemu_exit': proc.returncode, 'command': cmd,
          'log': str(log_path), 'captured_files': files, 'extract': str(extract),
          'native_entry_number': 8, 'native_hardware_validated': False,
          'physical_firmware_writes': 0, 'physical_keyboard_input_validated': False}
with result_path.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
print('SERIAL_END\n' + text[-3500:])
raise SystemExit(0 if report['passed'] else 1)
