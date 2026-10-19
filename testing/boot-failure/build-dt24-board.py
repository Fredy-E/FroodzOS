#!/usr/bin/env python3
"""Apply/build the scoped keyboard DT repair and prove every other node unchanged."""
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
baseline = T / 'dt24-source-before.dts'
assert source.read_bytes() == baseline.read_bytes(), 'Source changed after baseline'
image_hash = hashlib.sha256((K / 'arch/arm64/boot/Image').read_bytes()).hexdigest()
old_dtb = Path('/home/builder/boot-failure-tests/dt24-baseline/dt23.dtb')
patch = P / 'pkgs/linux-cachyos-arm64/patches/0019-diagnostic-keyboard-i2c9-dependencies.patch'
for dry in [True, False]:
    cmd = ['patch', '--batch', '--forward', '-p1', '-d', str(K), '-i', str(patch)]
    subprocess.run(cmd + (['--dry-run'] if dry else []), check=True)
assert source.read_bytes() == (T / 'dt24-source-work.dts').read_bytes()
with (T / 'build-dt24-dtb.log').open('x') as log:
    subprocess.run(['make', 'ARCH=arm64', 'CROSS_COMPILE=', '-j2',
                    'qcom/x126100-lenovo-ideapad-slim3.dtb'], cwd=K,
                   stdout=log, stderr=subprocess.STDOUT, check=True)
assert hashlib.sha256((K / 'arch/arm64/boot/Image').read_bytes()).hexdigest() == image_hash
subprocess.run(['python3', str(T / 'check-dt24-board.py'), str(dtb),
                '--result', str(T / 'dt24-board-green.json')], check=True)
subprocess.run(['python3', str(T / 'check-dt21-board.py'), str(dtb),
                '--result', str(T / 'dt24-usb-retained-green.json')], check=True)


def symbol(name):
    return subprocess.check_output(['fdtget', '-t', 's', str(dtb), '/__symbols__', name], text=True).strip()


allowed = {(symbol('i2c9'), 'interconnects'), (symbol('i2c9'), 'interconnect-names'),
           (symbol('gpi_dma1'), 'status'), (symbol('vreg_misc_3p3'), 'status')}


def normalized(path):
    text = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(path)],
                                   text=True, stderr=subprocess.DEVNULL)
    stack, result = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith('{'):
            name = stripped[:-1].strip().split()[-1]
            parent = stack[-1] if stack else ''
            stack.append('/' if name == '/' else parent.rstrip('/') + '/' + name)
        if '=' in stripped and stack and (stack[-1], stripped.split('=', 1)[0].strip()) in allowed:
            continue
        result.append(line)
        if stripped == '};':
            stack.pop()
    assert not stack
    return '\n'.join(result)


assert normalized(old_dtb) == normalized(dtb), 'Compiled changes outside four approved properties'
reverted = subprocess.check_output(['patch', '--batch', '--silent', '-R', '-p1', '--output=-',
                                   str(source), str(patch)], cwd=K)
assert reverted == baseline.read_bytes()
report = {'passed': True, 'kernel_unchanged': True,
          'allowed_changed_properties': sorted([list(x) for x in allowed]),
          'only_allowed_compiled_properties_changed': True,
          'patch_forward_and_reverse_verified': True,
          'dtb_sha256': hashlib.sha256(dtb.read_bytes()).hexdigest(), 'dtb_bytes': dtb.stat().st_size,
          'kernel_sha256': image_hash, 'native_hardware_validated': False}
with (T / 'dt24-dtb-build-result.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
