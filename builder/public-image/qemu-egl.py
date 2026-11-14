#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable QEMU boot with a ramfb display: run tools/egltest.py under three graphics environments (run in the CachyOSBuilder distro).

    FZ_UKI=<boot image.efi> FZ_TAG=<name> qemu-egl.py

A copy of the release image gets the boot image and a serial-console grub.cfg; the script logs in over the serial console and runs
egltest.py (EGL on the firmware-framebuffer DRM device) with: (1) LIBGL_ALWAYS_SOFTWARE=1, (2) MESA_LOADER_DRIVER_OVERRIDE=kms_swrast,
(3) only GALLIUM_DRIVER=llvmpipe. Emulator only.
"""
import os, re, select, shutil, subprocess, time
from pathlib import Path

C = Path('/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110'); B = Path('/mnt/d/FroodzOS-build')
IMG = B / os.environ.get('FZ_IMG', 'FroodzOS-0.1.0-dev.2-maverick-arm64-83n3.img'); TEST = B / 'qemu-egl-test.img'
UKI = Path(os.environ['FZ_UKI']); tag = os.environ.get('FZ_TAG', 'egl')
FW = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd')
log_path = C / 'output' / ('qemu-egl-%s.log' % tag); res_path = C / 'output' / ('qemu-egl-%s.txt' % tag)
cfg = (C / 'output/grub.cfg.public').read_text(encoding='utf-8')
cfg = cfg.replace('set timeout=10', 'set timeout=1').replace(' kestrel_efilog=0', ' kestrel_efilog=0 console=ttyAMA0,115200')
tcfg = B / 'grub.cfg.qemu-egl'; tcfg.write_text(cfg, encoding='utf-8', newline='\n')
shutil.copyfile(IMG, TEST)
fs = str(TEST) + '@@1M'
subprocess.run(['mcopy', '-i', fs, '-o', str(tcfg), '::/boot/grub/grub.cfg'], check=True)
subprocess.run(['mcopy', '-i', fs, '-o', str(UKI), '::/EFI/Linux/froodzos-maverick-tp.efi'], check=True)
subprocess.run(['mcopy', '-i', fs, '-o', str(C / 'tools/egltest.py'), '::/egltest.py'], check=True)
cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53', '-accel', 'tcg', '-m', '3072', '-smp', '4',
       '-bios', str(FW), '-device', 'ramfb', '-device', 'qemu-xhci', '-device', 'usb-kbd',
       '-drive', 'if=none,id=stick,format=raw,snapshot=on,file=' + str(TEST), '-device', 'usb-storage,drive=stick',
       '-display', 'none', '-serial', 'stdio', '-no-reboot', '-monitor', 'none']
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
T = b'python3 /run/archiso/bootmnt/egltest.py 2>&1 | tail -n 9'
NL = b'\n'
CMDS = [b'echo ===EGL0===; ls /dev/dri 2>&1; dmesg | grep -iE "simpledrm|simple-framebuffer|drm" | head -4 | cut -c1-150; echo ===EGL0END===' + NL,
        b'echo ===EGL1===; sudo -n env LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe ' + T + b'; echo ===EGL1END===' + NL,
        b'echo ===EGL2===; sudo -n env GALLIUM_DRIVER=llvmpipe MESA_LOADER_DRIVER_OVERRIDE=kms_swrast ' + T + b'; echo ===EGL2END===' + NL,
        b'echo ===EGL3===; sudo -n env GALLIUM_DRIVER=llvmpipe ' + T + b'; echo ===EGL3END===' + NL]
start = time.monotonic(); out = b''; mu_at = None; stage = 0; next_at = None
with log_path.open('wb') as log:
    while time.monotonic() - start < 1500 and proc.poll() is None:
        cleanw = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
        if mu_at is None and re.search(rb'Reached target [^\r\n]*Multi-User System', cleanw):
            mu_at = time.monotonic()
        if mu_at and stage == 0 and b'login:' in cleanw and time.monotonic() - mu_at > 20:
            for line in (b'live' + NL, b'live' + NL):
                proc.stdin.write(line); proc.stdin.flush(); time.sleep(5)
            for c in CMDS:
                proc.stdin.write(c); proc.stdin.flush(); time.sleep(25)
            stage = 1; next_at = time.monotonic() + 40
        elif stage == 1 and time.monotonic() > next_at:
            break
        if not select.select([proc.stdout], [], [], 1)[0]:
            continue
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            break
        out += chunk; log.write(chunk); log.flush()
        if b'---[ end Kernel panic' in out or b'Falling back to interactive prompt' in out:
            break
proc.terminate()
try:
    proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    proc.kill(); proc.wait()
text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', out.decode(errors='replace')).replace('\r', '')
res = []
for n in range(0, 4):
    a, b = text.rfind('===EGL%d===' % n), text.rfind('===EGL%dEND===' % n)
    res.append(text[a:b] if a >= 0 and b > a else '(EGL%d not captured)' % n)
summary = '\n'.join(res) + '\nstage reached: %d; seconds %.0f\n' % (stage, time.monotonic() - start)
res_path.write_text(summary, encoding='utf-8')
print(summary)
TEST.unlink(missing_ok=True)
