#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable QEMU boot of the firmware-free public image (run in the CachyOSBuilder distro; no real media).

A copy of the image is made and ONLY /boot/grub/grub.cfg inside the copy is replaced by a test variant (timeout 1, serial
console added to the kernel lines). Everything else (GRUB binary, UKIs, root squashfs) is the exact image under test.
QEMU virt is not the laptop: this proves the image boots, the identity and the pruning, not any hardware behaviour.
"""
import hashlib, json, os, re, select, shutil, subprocess, sys, time
from pathlib import Path

C = Path('/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110'); B = Path('/mnt/d/FroodzOS-build')
IMG = B / os.environ.get('FZ_IMG', 'FroodzOS-0.1.0-dev-maverick-arm64-83n3-nofw.img'); TEST = B / 'qemu-public-test.img'
EXPECT_BUILD = os.environ.get('FZ_EXPECT_BUILD', 'maverick-public-dev')
FW = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd')
tag = os.environ.get('FZ_TAG', 'public-image-qemu-1'); log_path = C / 'output' / (tag + '.log'); res_path = C / 'output' / (tag + '-result.json')
img_sha = hashlib.file_digest(IMG.open('rb'), 'sha256').hexdigest()
cfg = (C / 'output' / os.environ.get('FZ_CFG', 'grub.cfg.public')).read_text(encoding='utf-8')
cfg = cfg.replace('set timeout=10', 'set timeout=1').replace(' kestrel_efilog=0', ' kestrel_efilog=0 console=ttyAMA0,115200')
tcfg = B / 'grub.cfg.qemu'; tcfg.write_text(cfg, encoding='utf-8', newline='\n')
shutil.copyfile(IMG, TEST)
fs = str(TEST) + '@@1M'
subprocess.run(['mcopy', '-i', fs, '-o', str(tcfg), '::/boot/grub/grub.cfg'], check=True)
cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53', '-accel', 'tcg', '-m', '3072', '-smp', '2',
       '-bios', str(FW), '-device', 'qemu-xhci', '-drive', 'if=none,id=stick,format=raw,snapshot=on,file=' + str(TEST),
       '-device', 'usb-storage,drive=stick', '-nographic', '-no-reboot', '-monitor', 'none']
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
start = time.monotonic(); out = b''; reason = 'deadline'; mu_at = None; typed = False; end_at = None
CMDS = [b'live\n', b'live\n',
        b'echo ===ID===; grep -E "^(PRETTY_NAME|BUILD_ID|ID)=" /etc/os-release; uname -r; pacman -Q linux-froodzos-arm64; pacman -Q | wc -l\n',
        b'echo ===PRUNED===; ls /usr/lib/firmware/updates 2>&1 | head -2; sudo -n ls -A /etc/pacman.d/gnupg/private-keys-v1.d | wc -l; ls /usr/lib/firmware | wc -l; ls /usr/lib/firmware/ath12k 2>&1 | head -3\n',
        b'echo ===PHASE1===; pacman -Q firefox 2>&1 | head -1; ls /usr/share/pixmaps | grep -c archlinux; grep -E "^(NAME|VERSION_ID|BUILD_ID)=" /usr/lib/os-release; pacman -Q ark okular gwenview libreoffice-fresh falkon haruna mpv 2>&1 | wc -l; command -v 7zz unrar bsdtar; echo ===PHASE1END===\n',
        b'echo ===R3===; ls /opt/helium/helium /opt/zen/zen /usr/local/bin/helium; pacman -Q chromium 2>&1 | head -1; pacman -Q falkon 2>&1 | head -1; ls /etc/mpv/mpv.conf /usr/local/bin/fz-mount-image /etc/sysctl.d/90-froodzos-userns.conf; command -v udisksctl; grep -c chromium /etc/xdg/mimeapps.list; systemctl is-enabled fz-smartlog; ls /run/fz-smartlog | head -4; echo ===R3END===\n',
        b'echo ===DBCHECK===; pacman -Dk 2>&1 | tail -n 6; echo dbrc=$?\n',
        b'echo ===UNITS===; systemctl is-enabled fz-touchpad; systemctl --failed --no-legend | head -8\n',
        b'echo ===SELFTEST===; sudo -n python3 /usr/local/sbin/fz-touchpad.py --selftest; echo rc=$?\n',
        b'echo ===MOUNTS===; findmnt -no SOURCE,FSTYPE / ; ls /run/archiso/bootmnt | head -8; echo ===END===\n']
with log_path.open('xb') as log:
    while time.monotonic() - start < 1500 and proc.poll() is None:
        cleanw = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
        if mu_at and not typed and b'login:' in cleanw and time.monotonic() - mu_at > 25:
            typed = True; reason = 'logged-in'
            for line in CMDS:
                proc.stdin.write(line); proc.stdin.flush(); time.sleep(12)
            end_at = time.monotonic() + 30
        if not select.select([proc.stdout], [], [], 1)[0]:
            if end_at and time.monotonic() > end_at: break
            continue
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk: reason = 'eof'; break
        out += chunk; log.write(chunk); log.flush()
        clean = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
        if b'Falling back to interactive prompt' in out: reason = 'initramfs-mount-failure'; break
        if b'---[ end Kernel panic' in out: reason = 'kernel-panic'; break
        if mu_at is None and re.search(rb'Reached target [^\r\n]*Multi-User System', clean): mu_at = time.monotonic()
    if proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    out += proc.stdout.read()
text = out.decode(errors='replace'); clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text).replace('\r', '')
seg = lambda a, b: clean[clean.rfind(a):clean.rfind(b)] if a in clean else ''
markers = {
    'grub_started': 'GNU GRUB' in text or 'Booting' in text or 'EFI stub' in text,
    'multi_user': mu_at is not None,
    'logged_in_and_ran': '===END===' in clean,
    'identity_public_build': EXPECT_BUILD in clean and 'firmware-free public build' in clean,
    'no_firefox': "package 'firefox' was not found" in seg('===PHASE1===', '===PHASE1END==='),
    'no_arch_logo': '\n0\n' in seg('===PHASE1===', '===PHASE1END==='),
    'handlers_installed': '\n7\n' in seg('===PHASE1===', '===PHASE1END==='),
    'r3_chromium_no_falkon': ('/opt/helium/helium' in seg('===R3===', '===R3END===')) and ('/opt/zen/zen' in seg('===R3===', '===R3END===')) and ("package 'chromium' was not found" in seg('===R3===', '===R3END===')) and ("package 'falkon' was not found" in seg('===R3===', '===R3END===')),
    'r3_files': all(x in seg('===R3===', '===R3END===') for x in ('/etc/mpv/mpv.conf', '/usr/local/bin/fz-mount-image', '90-froodzos-userns.conf', 'udisksctl')),
    'smartlog_running': 'enabled' in seg('===R3===', '===R3END===') and 'events.log' in seg('===R3===', '===R3END==='),
    'kernel_package_renamed': 'linux-froodzos-arm64 7.3.0rc3-1' in clean,
    'no_vendor_firmware_dir': bool(re.search(r'===PRUNED===\s*\n[^\n]*No such file', clean)),
    'no_private_keyring_key': bool(re.search(r'===PRUNED===[^\n]*\n[^\n]*No such file[^\n]*\n[^\n]*\n?\s*0\b', clean)) or '\n0\n' in seg('===PRUNED===', '===DBCHECK==='),
    'selftest_pass': 'fz-touchpad: SELFTEST PASS' in clean,
    'panic': 'Kernel panic' in text,
}
passed = all(markers[k] for k in ('multi_user', 'logged_in_and_ran', 'identity_public_build', 'kernel_package_renamed', 'selftest_pass', 'no_firefox', 'no_arch_logo', 'handlers_installed', 'r3_chromium_no_falkon', 'r3_files', 'smartlog_running')) and not markers['panic']
tail = clean[clean.rfind('===ID==='):] if '===ID===' in clean else clean[-3500:]
summary = {'tag': tag, 'seconds': round(time.monotonic() - start, 1), 'stop_reason': reason, 'markers': markers, 'passed': passed,
           'image_sha256': img_sha, 'hardware_validated': False,
           'scope': 'QEMU TCG virt; the image under test is the real public image except grub.cfg (test variant: timeout 1, serial console). No laptop hardware behaviour is tested.'}
res_path.write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=2)); print('--- GUEST OUTPUT:'); print(tail[:5000])
TEST.unlink(missing_ok=True)
