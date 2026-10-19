#!/usr/bin/env python3
"""Preserve the exact dt23 source/DT baseline before the scoped dt24 repair."""
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
ROOT = Path('/home/builder/imgroot')
SOURCE = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
DTB = SOURCE.with_suffix('.dtb')
OUT = Path('/home/builder/boot-failure-tests/dt24-baseline')
OUT.mkdir()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


old = Path('/home/builder/uki-v2-dt23/vmlinuz-live.efi')
expected = json.loads((T / 'dt23-update-manifest.json').read_text())['uki_sha256']
assert sha(old) == expected, 'Previous UKI differs from installed manifest'
data = old.read_bytes()
pe = struct.unpack_from('<I', data, 0x3c)[0]
count = struct.unpack_from('<H', data, pe + 6)[0]
opt = struct.unpack_from('<H', data, pe + 20)[0]
sections = {}
for i in range(count):
    off = pe + 24 + opt + 40 * i
    name = data[off:off + 8].rstrip(b'\0').decode()
    size = struct.unpack_from('<I', data, off + 8)[0]
    ptr = struct.unpack_from('<I', data, off + 20)[0]
    sections[name] = data[ptr:ptr + size]
assert sections['.dtbauto'] == DTB.read_bytes(), 'Current DTB is not dt23'
assert sections['.linux'] == (K / 'arch/arm64/boot/Image').read_bytes()
for src, name in [(SOURCE, 'dt23.dts'), (DTB, 'dt23.dtb'), (P / 'builder/build-live-uki.sh', 'build-live-uki.sh'),
                  (P / 'builder/initcpio/hooks/kestrel_log', 'kestrel_log'),
                  (P / 'builder/initcpio/install/kestrel_log', 'kestrel_log.install')]:
    shutil.copyfile(src, OUT / name)
shutil.copyfile(SOURCE, T / 'dt24-source-before.dts')


def get(node, prop, kind='s'):
    proc = subprocess.run(['fdtget', '-t', kind, str(DTB), node, prop], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


checks = []
for label in ['i2c9', 'gpi_dma1', 'vreg_misc_3p3', 'vreg_l12b_1p2', 'tlmm', 'gem_noc', 'pcie3', 'pcie6a', 'pcie5', 'pcie4']:
    node = get('/__symbols__', label)
    props = {prop: get(node, prop, kind) for prop, kind in [('status', 's'), ('phandle', 'x'), ('dmas', 'x'), ('dma-channel-mask', 'x'), ('gpios', 'x'), ('regulator-min-microvolt', 'u'), ('regulator-max-microvolt', 'u'), ('vin-supply', 'x'), ('interconnects', 'x')]}
    checks.append({'label': label, 'node': node, 'properties': props})
for row in checks:
    print(json.dumps(row))
module_paths = {}
for name in ['i2c-hid-of', 'i2c-hid', 'hid-generic', 'gpi']:
    path = subprocess.check_output(['modinfo', '-k', '7.3.0-rc3', '-n', name], text=True).strip()
    module_paths[name] = path
    print('AVAILABLE_MODULE', name, path)
for relative in ['usr/lib/systemd/system/getty@.service', 'usr/lib/systemd/system/serial-getty@.service',
                 'usr/lib/systemd/system/debug-shell.service', 'etc/pam.d/login']:
    path = ROOT / relative
    print('LIVE_UNIT', relative)
    print(path.read_text() if path.exists() else 'ABSENT')
print(subprocess.check_output(['chroot', str(ROOT), '/usr/lib/systemd/systemd', '--version'], text=True))
report = {'passed': True, 'dt23_uki_sha256': expected, 'baseline': str(OUT),
          'source_sha256': sha(SOURCE), 'dtb_sha256': sha(DTB),
          'kernel_sha256': sha(K / 'arch/arm64/boot/Image'), 'modules_available': module_paths,
          'compiled_nodes': checks, 'native_hardware_validated': False}
with (T / 'dt24-baseline.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print('DT24_BASELINE_PRESERVED')
