#!/usr/bin/env python3
"""Exact dt22 firmware regression using disposable QEMU USB and pflash only."""
import base64
import hashlib
import json
import os
import re
import select
import shutil
import socket
import struct
import subprocess
import time
import zlib
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
TAG = 'dt22-logger-v2-v1'
OUT = B / TAG
if OUT.exists():
    raise SystemExit('Existing evidence retained; use fresh tag')
OUT.mkdir()
REV = 'v2-dt22'
UKI = Path('/home/builder/uki-' + REV + '/vmlinuz-live.efi')
subprocess.run(['python3', str(T / 'prepare-partitioned-validation.py'), '--revision', REV], check=True)
IMAGE = B / ('qemu-' + REV + '-shell.fat')
pt = json.loads(subprocess.check_output(['sfdisk', '--json', str(IMAGE)]))['partitiontable']
FS = str(IMAGE) + '@@' + str(pt['partitions'][0]['start'] * pt['sectorsize'])
FW = T / 'uefi-package/usr/share/AAVMF'
VARS = OUT / 'vars.fd'
shutil.copyfile(FW / 'AAVMF_VARS.fd', VARS)
GUID = '674b8af1-da8e-4c2b-a84c-467e2d36c97c'
menu = (T / 'dt22-grub.cfg').read_text()
entry = re.findall(r'^menuentry .*?(?=^menuentry |\Z)', menu, re.M | re.S)[7]
line = re.search(r'^\s+linux (.+)$', entry, re.M).group(1)
line = line.replace('$platform_cmdline', 'clk_ignore_unused pd_ignore_unused efi-pstore.pstore_disable=1')
line = line.replace('console=tty0', 'console=ttyAMA0,115200')
assert line.count('init=/usr/local/sbin/kestrel-pid1') == 1


def decode(raw):
    assert raw[:4] == bytes([7, 0, 0, 0])
    data = bytearray(raw[4:])
    assert data[:8] == b'KSTRLOG1' and 80 <= len(data) <= 1024
    version, slot, length, crc = struct.unpack_from('<IIII', data, 8)
    assert version == 1 and slot < 4 and len(data) == 80 + length
    data[20:24] = bytes(4)
    assert zlib.crc32(data) == crc
    return {'slot': slot, 'boot_id': bytes(data[32:68]).decode(),
            'reason': bytes(data[68:80]).rstrip(b'\0').decode(),
            'uptime_ms': struct.unpack_from('<Q', data, 24)[0],
            'text': bytes(data[80:]).decode(errors='replace'),
            'sha256': hashlib.sha256(raw).hexdigest()}


def boot(label, on=False, unplug=False):
    args = line if on else line.replace('kestrel_efilog=1', '')
    cfg = OUT / (label + '.cfg')
    cfg.write_text('set timeout=1\nset default=0\nterminal_output console\n'
                   'menuentry "logger test ' + label + '" {\n linux ' + args + '\n boot\n}\n')
    subprocess.run(['mcopy', '-o', '-i', FS, str(cfg), '::/boot/grub/grub.cfg'], check=True)
    sockpath = OUT / 'qmp.sock'
    if sockpath.exists():
        sockpath.unlink()
    cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53',
           '-accel', 'tcg', '-m', '2048', '-smp', '2',
           '-drive', 'if=pflash,format=raw,unit=0,readonly=on,file=' + str(FW / 'AAVMF_CODE.no-secboot.fd'),
           '-drive', 'if=pflash,format=raw,unit=1,file=' + str(VARS), '-device', 'qemu-xhci',
           '-drive', 'if=none,id=stick,format=raw,file=' + str(IMAGE),
           '-device', 'usb-storage,id=bootusb,drive=stick',
           '-qmp', 'unix:' + str(sockpath) + ',server=on,wait=off',
           '-nographic', '-no-reboot', '-monitor', 'none']
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    output = b''
    start = time.monotonic()
    sent = done = removed = False
    sock = None
    try:
        for _ in range(100):
            if sockpath.exists():
                break
            time.sleep(.05)
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(str(sockpath))
        sock.settimeout(10)
        qmp = sock.makefile('rwb', buffering=0)
        json.loads(qmp.readline())
        qmp.write(b'{"execute":"qmp_capabilities"}\n')
        while 'return' not in json.loads(qmp.readline()):
            pass
        with (OUT / (label + '.log')).open('wb') as log:
            while time.monotonic() - start < 300 and proc.poll() is None:
                if not select.select([proc.stdout], [], [], 1)[0]:
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                output += chunk
                log.write(chunk)
                log.flush()
                if unplug and not removed and b'KESTREL_RAM_CAPTURE_ACTIVE v2' in output:
                    qmp.write(b'{"execute":"device_del","arguments":{"id":"bootusb"}}\n')
                    removed = True
                if unplug:
                    if b'KESTREL_FW_SAVED slot=3' in output and b'KESTREL_RAM_CAPTURE_STOPPED v2' in output:
                        done = True
                        break
                elif not sent and (b'no job control' in output or b'bash-' in output[-1024:]):
                    shell = ("printf '\\nKST_ROOT_OK\\n'; mount -t efivarfs efivarfs /sys/firmware/efi/efivars 2>/dev/null; "
                             "cat /run/kestrel-capture/checkpoint-status.log 2>/dev/null; "
                             "for f in /sys/firmware/efi/efivars/KestrelBoot*-" + GUID + "; do "
                             "[ -f \"$f\" ] || continue; printf 'KSTVAR|%s|' \"${f##*/}\"; "
                             "base64 -w0 \"$f\"; printf '\\n'; done; printf '\\nKST_DONE\\n'\n")
                    proc.stdin.write(shell.encode())
                    proc.stdin.flush()
                    sent = True
                if not unplug and re.search(rb'^KST_DONE\r?$', output, re.M):
                    done = True
                    break
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=20)
        if sock:
            sock.close()
    assert done, f'{label} failed; inspect {OUT / (label + ".log")}'
    assert b'Kernel panic' not in output
    records = {}
    for name, data in re.findall(rb'^KSTVAR\|([^|\r\n]+)\|([A-Za-z0-9+/=]+)\r?$', output, re.M):
        raw = base64.b64decode(data, validate=True)
        decode(raw)
        records[name.decode()] = raw
        (OUT / (label + '-' + name.decode() + '.bin')).write_bytes(raw)
    if unplug:
        assert b'device did not show up' in output and b'Falling back to interactive prompt' in output
        assert removed
    print('DT21_EFI_PHASE', label, 'seconds', round(time.monotonic() - start, 2), flush=True)
    return {'label': label, 'seconds': round(time.monotonic() - start, 2),
            'emulated_usb_removed': removed, 'timeout_observed': b'device did not show up' in output,
            'disarmed': b'KESTREL_FW_DISARMED' in output,
            'records': {name: decode(raw) for name, raw in records.items()}}, records


results = []
r, off = boot('flag-off')
results.append(r)
assert not off
r, _ = boot('no-usb', on=True, unplug=True)
results.append(r)
r, recovered = boot('recovery')
results.append(r)
assert len(recovered) == 4
late = decode(next(raw for name, raw in recovered.items() if name.startswith('KestrelBoot03-')))
assert 'capture=v2' in late['text'] and 'external_usb=0' in late['text'] and 'label=missing' in late['text']
assert 'initramfs_boot_device_timeout=seen' in late['text'], late
assert late['reason'] == 'timeout' and late['uptime_ms'] >= 55000
r, unchanged = boot('existing-records', on=True)
results.append(r)
assert r['disarmed'] and unchanged == recovered
summary = {'passed': True, 'revision': REV,
           'uki_sha256': hashlib.file_digest(UKI.open('rb'), 'sha256').hexdigest(),
           'results': results, 'hardware_validated': False, 'physical_firmware_writes': 0,
           'abrupt_stop_persistence': True}
with (T / (TAG + '-result.json')).open('x') as output:
    json.dump(summary, output, indent=2)
print(json.dumps(summary, indent=2))
