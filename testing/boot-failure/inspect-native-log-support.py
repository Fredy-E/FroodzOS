"""Inspect the built kernel/rootfs, not the WSL guest's runtime logs."""
import json
from pathlib import Path
import re
import subprocess

P = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
K = Path('/home/builder/src/ksrc')
R = Path('/home/builder/imgroot')
config = (K / '.config').read_text()
patterns = ('PSTORE', 'EFI_VARS', 'WATCHDOG', 'QCOM_WDT', 'SERIAL_EARLYCON', 'DRM_MSM', 'DRM_SIMPLEDRM')
config_lines = [line for line in config.splitlines() if any(token in line for token in patterns)]
print('BUILT_KERNEL_CONFIG\n' + '\n'.join(config_lines))
journal_files = [R / 'etc/systemd/journald.conf']
journal_files += list((R / 'etc/systemd/journald.conf.d').glob('*.conf'))
journal_files += list((R / 'usr/lib/systemd/journald.conf.d').glob('*.conf'))
journal_settings = []
for path in journal_files:
    if path.is_file():
        lines = [line for line in path.read_text(errors='replace').splitlines()
                 if re.search(r'Storage=|ForwardToConsole=|ForwardToKMsg=|SystemMaxUse=|RuntimeMaxUse=', line)]
        journal_settings.append({'path': str(path.relative_to(R)), 'settings': lines})
print('ROOTFS_JOURNAL_SETTINGS\n' + json.dumps(journal_settings, indent=2))
logdirs = []
for d in [R / 'var/log', R / 'var/log/journal', R / 'var/lib/systemd/pstore']:
    if d.exists():
        logdirs.append({'path': str(d.relative_to(R)), 'entries': [p.name for p in d.iterdir()]})
print('IMAGE_LOG_DIRECTORIES\n' + json.dumps(logdirs, indent=2))
result = subprocess.run(['lsinitcpio', '-l', '/home/builder/uki-v2-nls/live-initramfs.img'],
                        check=True, capture_output=True, text=True)
archive_hits = [line for line in result.stdout.splitlines()
                if re.search(r'pstore|ramoops|efi_pstore|capture|crash|initramfs.*log', line, re.I)]
print('FINAL_INITRAMFS_CAPTURE_SUPPORT\n' + '\n'.join(archive_hits))
dts = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
dts_lines = dts.read_text().splitlines()
selected = [{'line': i+1, 'text': line} for i, line in enumerate(dts_lines)
            if re.search(r'ramoops|pstore|watchdog|wdt|reserved-memory', line)]
print('BOARD_DTS_SUPPORT\n' + json.dumps(selected, indent=2))
out = {'source': 'Built kernel, rootfs and initramfs configuration; NOT native crash logs',
       'kernel_config': config_lines, 'journal_settings': journal_settings,
       'image_log_directories': logdirs, 'initramfs_capture_support': archive_hits, 'board_dts_matches': selected}
(P / 'native-log-support.json').write_text(json.dumps(out, indent=2))
