#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable QEMU boot with a ramfb display to see whether the Plasma graphics session survives (run in the CachyOSBuilder distro).

    FZ_UKI=<variant.efi> FZ_TAG=<name> qemu-graphics.py

A copy of the release image gets the variant boot image and a serial-console grub.cfg; QEMU boots it with a firmware framebuffer, the
script logs in over the serial console, reads the graphics supervisor and KWin messages twice, takes a screenshot (PNG) and stops.
Emulator only: it shows whether KWin starts with the given environment, not how the laptop behaves.
"""
import json, os, re, select, shutil, socket, struct, subprocess, sys, time, zlib
from pathlib import Path

C = Path('/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110'); B = Path('/mnt/c/FroodzOS-build')
IMG = B / os.environ.get('FZ_IMG', 'FroodzOS-0.1.0-dev.2-maverick-arm64-83n3.img'); TEST = B / 'qemu-gfx-test.img'
UKI = Path(os.environ['FZ_UKI']); tag = os.environ.get('FZ_TAG', 'gfx')
FW = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd')
log_path = C / 'output' / ('qemu-gfx-%s.log' % tag); png_path = C / 'output' / ('qemu-gfx-%s.png' % tag); res_path = C / 'output' / ('qemu-gfx-%s.txt' % tag)
cfg = (C / 'output/grub.cfg.public').read_text(encoding='utf-8')
cfg = cfg.replace('set timeout=10', 'set timeout=1').replace(' kestrel_efilog=0', ' kestrel_efilog=0 console=ttyAMA0,115200')
tcfg = B / 'grub.cfg.qemu-gfx'; tcfg.write_text(cfg, encoding='utf-8', newline='\n')
shutil.copyfile(IMG, TEST)
fs = str(TEST) + '@@1M'
subprocess.run(['mcopy', '-i', fs, '-o', str(tcfg), '::/boot/grub/grub.cfg'], check=True)
subprocess.run(['mcopy', '-i', fs, '-o', str(UKI), '::/EFI/Linux/froodzos-maverick-tp.efi'], check=True)
sock = '/tmp/qgfx-%d.sock' % os.getpid()
cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53', '-accel', 'tcg', '-m', '3072', '-smp', '4',
       '-bios', str(FW), '-device', 'ramfb', '-device', 'qemu-xhci', '-device', 'usb-kbd',
       '-drive', 'if=none,id=stick,format=raw,snapshot=on,file=' + str(TEST), '-device', 'usb-storage,drive=stick',
       '-display', 'none', '-serial', 'stdio', '-no-reboot', '-monitor', 'unix:%s,server,nowait' % sock]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)


def mon(c):
    s = socket.socket(socket.AF_UNIX); s.connect(sock); s.settimeout(3)
    try: s.recv(4096)
    except Exception: pass
    s.sendall((c + '\n').encode()); time.sleep(1.0)
    try: s.recv(4096)
    except Exception: pass
    s.close()


def ppm_to_png(ppm, png):
    d = Path(ppm).read_bytes()
    parts = d.split(None, 4)
    w, h = int(parts[1]), int(parts[2]); pix = parts[4][-w * h * 3:] if len(parts) > 4 else b''
    pix = d[-w * h * 3:]
    raw = b''.join(b'\x00' + pix[y * w * 3:(y + 1) * w * 3] for y in range(h))
    def chunk(t, x): return struct.pack('>I', len(x)) + t + x + struct.pack('>I', zlib.crc32(t + x) & 0xffffffff)
    png.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))
    return w, h


start = time.monotonic(); out = b''; mu_at = None; stage = 0; next_at = None
GRAB = (b'echo ===GFX%d===; date +%%T; systemctl is-active kestrel-graphics; pgrep -a kwin_wayland | head -2 | cut -c1-80; '
        b'journalctl -b --no-pager | grep -E "kwin_wayland|MESA|KESTREL_GRAPHICS|plasmashell|startplasma" | tail -n 16 | cut -c1-190; echo ===GFX%dEND===\n')
with log_path.open('wb') as log:
    while time.monotonic() - start < 1500 and proc.poll() is None:
        cleanw = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
        if mu_at is None and re.search(rb'Reached target [^\r\n]*Multi-User System', cleanw):
            mu_at = time.monotonic()
        if mu_at and stage == 0 and b'login:' in cleanw and time.monotonic() - mu_at > 20:
            for line in (b'live\n', b'live\n'):
                proc.stdin.write(line); proc.stdin.flush(); time.sleep(5)
            proc.stdin.write(GRAB % (1, 1)); proc.stdin.flush(); stage = 1; next_at = time.monotonic() + 50
        elif stage == 1 and time.monotonic() > next_at:
            proc.stdin.write(GRAB % (2, 2)); proc.stdin.flush(); stage = 2; next_at = time.monotonic() + 25
        elif stage == 2 and time.monotonic() > next_at:
            ppm = Path('/tmp/qgfx.ppm'); mon('screendump ' + str(ppm)); time.sleep(2)
            size = ppm_to_png(ppm, png_path) if ppm.exists() else None
            stage = 3; next_at = time.monotonic() + 3
        elif stage == 3 and time.monotonic() > next_at:
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
try: proc.wait(timeout=10)
except subprocess.TimeoutExpired: proc.kill(); proc.wait()
text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', out.decode(errors='replace')).replace('\r', '')
res = []
for n in (1, 2):
    a, b = text.rfind('===GFX%d===' % n), text.rfind('===GFX%dEND===' % n)
    res.append(text[a:b] if a >= 0 and b > a else '(stage %d not captured)' % n)
summary = '\n'.join(res) + '\nstage reached: %d; seconds %.0f; png: %s\n' % (stage, time.monotonic() - start, png_path if png_path.exists() else 'none')
res_path.write_text(summary, encoding='utf-8')
print(summary)
TEST.unlink(missing_ok=True)
