#!/usr/bin/env python3
"""Apply the reviewed DTS-only delta, build one DTB and constrain its scope."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

K = Path('/home/builder/src/ksrc')
P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
REL = 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
source = K / REL
dtb = source.with_suffix('.dtb')
baseline = T / 'dt21-source-before.dts'
expected = T / 'dt21-source-work.dts'
assert source.read_bytes() == baseline.read_bytes(), 'Source changed since snapshot'
out = Path('/home/builder/boot-failure-tests/dt21-board-build-v2')
out.mkdir()
old_dtb = out / 'dt20.dtb'
shutil.copyfile(dtb, old_dtb)
image = K / 'arch/arm64/boot/Image'
image_hash = hashlib.file_digest(image.open('rb'), 'sha256').hexdigest()
patch = P / 'pkgs/linux-cachyos-arm64/patches/0018-diagnostic-usb-i2c5-dependencies.patch'
for dry in (True, False):
    args = ['patch', '--batch', '--forward', '-p1', '-d', str(K), '-i', str(patch)]
    if dry:
        args.append('--dry-run')
    subprocess.run(args, check=True)
assert source.read_bytes() == expected.read_bytes(), 'Patch/source mismatch'
with (T / 'build-dt21-dtb.log').open('x') as log:
    run = subprocess.run(['make', 'ARCH=arm64', 'CROSS_COMPILE=', '-j2',
                          'qcom/x126100-lenovo-ideapad-slim3.dtb'], cwd=K,
                         stdout=log, stderr=subprocess.STDOUT)
run.check_returncode()
assert hashlib.file_digest(image.open('rb'), 'sha256').hexdigest() == image_hash
subprocess.run(['python3', str(T / 'check-dt21-board.py'), str(dtb),
                '--result', str(T / 'dt21-board-dependency-green.json')], check=True)


def get(path, prop):
    return subprocess.check_output(['fdtget', '-t', 's', str(dtb), path, prop], text=True).strip()


i2c = get('/__symbols__', 'i2c5')
gpi = get('/__symbols__', 'gpi_dma0')
allowed = {(i2c, 'interconnects'), (i2c, 'interconnect-names'), (gpi, 'status')}


def normalized(path):
    text = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(path)],
                                   text=True, stderr=subprocess.DEVNULL)
    stack = []
    result = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith('{'):
            name = stripped[:-1].strip().split()[-1]
            parent = stack[-1] if stack else ''
            stack.append('/' if name == '/' else parent.rstrip('/') + '/' + name)
        if '=' in stripped and stack:
            prop = stripped.split('=', 1)[0].strip()
            if (stack[-1], prop) in allowed:
                continue
        result.append(line)
        if stripped == '};':
            stack.pop()
    assert not stack
    return '\n'.join(result)


assert normalized(old_dtb) == normalized(dtb), 'Unexpected compiled DT changes outside I2C5/GPI0'
# Prove the generated patch reverses exactly to the saved series baseline.
reverted = subprocess.check_output(['patch', '--batch', '--silent', '-R', '-p1', '--output=-',
                                    str(source), str(patch)], cwd=K)
assert reverted == baseline.read_bytes(), 'Patch reverse reproduction failed'
report = {'passed': True, 'kernel_unchanged': True,
          'allowed_changed_properties': sorted([list(item) for item in allowed]),
          'only_allowed_compiled_properties_changed': True,
          'patch_forward_and_reverse_verified': True,
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'dtb_sha256': hashlib.sha256(dtb.read_bytes()).hexdigest(),
          'dtb_bytes': dtb.stat().st_size,
          'old_dtb': str(old_dtb), 'native_hardware_validated': False}
with (T / 'dt21-dtb-build-result.json').open('x') as output:
    json.dump(report, output, indent=2)
print(json.dumps(report, indent=2))
