#!/usr/bin/env python3
"""Exact dt22 EFI/live-root shell and full systemd logging regressions."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
B = Path('/home/builder/boot-failure-tests')
REV = 'v2-dt22'
MENU = T / 'dt22-grub.cfg'
UKI = Path('/home/builder/uki-' + REV + '/vmlinuz-live.efi')
expected = json.loads((T / 'dt22-artifact-audit.json').read_text())['uki_sha256']
assert hashlib.file_digest(UKI.open('rb'), 'sha256').hexdigest() == expected
INIT = 'init=/usr/local/sbin/kestrel-pid1'

for systemd, budget in [(False, 360), (True, 600)]:
    mode = 'systemd' if systemd else 'shell'
    tag = 'qemu-dt22-menu8-' + mode + '-fw-off-v1'
    subprocess.run(['python3', str(T / 'prepare-log-validation.py'), '--revision', REV,
                    '--tag', tag, '--menu', str(MENU), '--systemd'], check=True)
    image = B / (tag + '.fat')
    cfgfile = T / (tag + '-grub.cfg')
    cfg = cfgfile.read_text()
    cfg = re.sub(r'^set default=\d+$', 'set default=7', cfg, flags=re.M)
    cfg = cfg.replace('kestrel_efilog=1', '')
    if systemd:
        cfg = cfg.replace(INIT, '')
    entry = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', cfg, re.M | re.S)[7]
    assert (INIT in entry) == (not systemd)
    assert 'kestrel_efilog=1' not in entry
    cfgfile.write_text(cfg)
    pt = json.loads(subprocess.check_output(['sfdisk', '--json', str(image)]))['partitiontable']
    fs = str(image) + '@@' + str(pt['partitions'][0]['start'] * pt['sectorsize'])
    subprocess.run(['mcopy', '-o', '-i', fs, str(cfgfile), '::/boot/grub/grub.cfg'], check=True)
    packed = subprocess.check_output(['mtype', '-i', fs, '::/EFI/Linux/kestrel-live.efi'])
    assert hashlib.sha256(packed).hexdigest() == expected
    packed_menu = subprocess.check_output(['mtype', '-i', fs, '::/boot/grub/grub.cfg']).decode()
    assert packed_menu == cfg
    args = ['python3', str(T / 'run-efi-log-validation.py'), '--image', str(image),
            '--tag', tag, '--deadline', str(budget)]
    args += ['--systemd'] if systemd else ['--require-platform-usb']
    run = subprocess.run(args)
    result_file = T / (tag + '-result.json')
    if result_file.exists():
        result = json.loads(result_file.read_text())
        result.update({'uki_sha256': expected, 'native_entry_number': 8,
                       'fixture_candidate_readback_verified': True,
                       'firmware_flag_removed_for_this_test': True,
                       'init_pid1_removed_for_systemd_regression': systemd})
        if not systemd:
            serial = Path(result['log']).read_text(errors='replace')
            assert 'KESTREL_PID1_ENTER' in serial and 'KESTREL_PID1_EXEC_BASH' in serial, \
                'PID1 wrapper left no trace in QEMU shell serial log'
            result.update({'pid1_enter_in_serial_log': 'KESTREL_PID1_ENTER' in serial,
                           'pid1_exec_bash_in_serial_log': 'KESTREL_PID1_EXEC_BASH' in serial})
        result_file.write_text(json.dumps(result, indent=2))
    run.check_returncode()
    print('DT22_BOOT_PHASE_PASSED', mode, flush=True)
