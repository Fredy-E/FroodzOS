#!/usr/bin/env python3
"""Read-only parent inventory for the next native graphical candidate."""
import json
import subprocess
from pathlib import Path

ROOT = Path('/home/builder/imgroot')
K = Path('/home/builder/src/ksrc')
print('ROOTFS_BINARIES', json.dumps({n: (ROOT / 'usr/bin' / n).exists() for n in ['python', 'python3', 'kwin_wayland', 'startplasma-wayland', 'sddm', 'dbus-run-session', 'login', 'timeout', 'systemd-run']}))
print('ROOTFS_PACKAGES')
subprocess.run(['chroot', str(ROOT), 'pacman', '-Q', 'kwin', 'plasma-workspace', 'mesa', 'sddm', 'python', 'libseat', 'systemd', 'qt6-declarative'], check=False)
for relative in ['usr/lib/systemd/system/sddm.service', 'usr/share/wayland-sessions/plasma.desktop', 'etc/sddm.conf', 'etc/sddm.conf.d/autologin.conf', 'usr/lib/systemd/user/plasma-kwin_wayland.service', 'usr/bin/startplasma-wayland']:
    p = ROOT / relative
    print('ROOTFS_FILE', relative)
    if p.is_file() and p.stat().st_size < 32000:
        data = p.read_bytes()
        if b'\0' not in data:
            print(data.decode(errors='replace'))
        else:
            print('BINARY', len(data))
    else:
        print('ABSENT_OR_NOT_SMALL_TEXT')
print('KERNEL_CONFIG')
for line in (K / '.config').read_text().splitlines():
    if any(t in line for t in ['CONFIG_DRM_SIMPLEDRM=', 'CONFIG_DRM_MSM=', 'CONFIG_QCOM_TSENS=', 'CONFIG_THERMAL=', 'CONFIG_HWMON=', 'CONFIG_FRAMEBUFFER_CONSOLE=', 'CONFIG_QCOM_SPMI_TEMP_ALARM=', 'CONFIG_QCOM_SPMI_ADC_TM5=']):
        print(line)
print('SPACE')
subprocess.run(['df', '-B1', '/mnt/d', '/home/builder'], check=True)
print('ACTIVE_CANDIDATE_PROCESSES')
for d in Path('/proc').iterdir():
    if not d.name.isdigit():
        continue
    try:
        name = (d / 'comm').read_text().strip()
        if name in ['qemu-system-aarc', 'mkinitcpio', 'make', 'cc1', 'xz']:
            print(d.name, name)
    except (OSError, ProcessLookupError):
        pass
print('DT25_INSPECTION_COMPLETE')
