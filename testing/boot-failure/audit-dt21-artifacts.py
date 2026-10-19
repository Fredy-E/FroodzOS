#!/usr/bin/env python3
"""Gate dt21 module-only provenance against the recovered native dt20 build."""
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
OLD = Path('/home/builder/uki-v2-dt20/vmlinuz-live.efi')
NEW = Path('/home/builder/uki-v2-dt21/vmlinuz-live.efi')


def sections(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    machine, count = struct.unpack_from('<HH', data, pe + 4)
    assert machine == 0xaa64
    opt = struct.unpack_from('<H', data, pe + 20)[0]
    result = {}
    for index in range(count):
        header = pe + 24 + opt + 40 * index
        name = data[header:header + 8].rstrip(b'\0').decode()
        size = struct.unpack_from('<I', data, header + 8)[0]
        raw_size, ptr = struct.unpack_from('<II', data, header + 16)
        assert size <= raw_size or raw_size == 0
        result[name] = data[ptr:ptr + size]
    return data, result


old_data, old = sections(OLD)
data, new = sections(NEW)
for name in ('.linux', '.hwids', '.cmdline', '.text'):
    assert old[name] == new[name], 'Unexpected non-initramfs change: ' + name
assert new['.initrd'] != old['.initrd']
assert new['.dtbauto'] != old['.dtbauto']
board = json.loads((T / 'dt21-dtb-build-result.json').read_text())
assert board['passed'] and board['only_allowed_compiled_properties_changed']
assert hashlib.sha256(new['.dtbauto']).hexdigest() == board['dtb_sha256']
assert new['.linux'] == (K / 'arch/arm64/boot/Image').read_bytes()
assert new['.dtbauto'] == (K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb').read_bytes()
assert new['.initrd'] == Path('/home/builder/uki-v2-dt21/live-initramfs.img').read_bytes()
assert b'efi-pstore.pstore_disable=1' in new['.cmdline']
args = ['python3', str(P / 'builder/validate-live-initramfs.py'),
        '/home/builder/uki-v2-dt21/live-initramfs.img', '--require-local-firmware',
        '--require-log-capture', '--require-platform-usb']
validation = json.loads(subprocess.check_output(args, text=True))
assert validation['passed']
# The bounded logger must remain byte-identical, not merely contain its GUID.
with tempfile.TemporaryDirectory(prefix='dt21-old-', dir='/home/builder/boot-failure-tests') as a, \
     tempfile.TemporaryDirectory(prefix='dt21-new-', dir='/home/builder/boot-failure-tests') as b:
    for path, target in [('/home/builder/uki-v2-dt20/live-initramfs.img', a),
                         ('/home/builder/uki-v2-dt21/live-initramfs.img', b)]:
        subprocess.run(['lsinitcpio', '-x', path], cwd=target, capture_output=True, check=True)
    for name in ('usr/bin/kestrel-checkpoint', 'hooks/kestrel_efilog', 'hooks/kestrel_log'):
        assert (Path(a) / name).read_bytes() == (Path(b) / name).read_bytes(), name
    for name in ('gpi', 'i2c-qcom-geni', 'phy-nxp-ptn3222', 'qrtr', 'qrtr-smd'):
        result = subprocess.run(['modprobe', '-d', b, '-S', '7.3.0-rc3',
                                 '--show-depends', name], capture_output=True, text=True, check=True)
        assert 'insmod ' in result.stdout, (name, result.stdout)

report = {
    'passed': True, 'revision': 'v2-dt21', 'uki_bytes': len(data),
    'uki_sha256': hashlib.sha256(data).hexdigest(),
    'old_uki_sha256': hashlib.sha256(old_data).hexdigest(),
    'kernel_stub_cmdline_unchanged_from_dt20': True,
    'board_dependencies': board,
    'checkpoint_binary_and_hooks_unchanged_from_dt20': True,
    'module_dependency_resolution': True,
    'initramfs_validation': validation,
    'embedded_inputs': {name: {'bytes': len(new[name]), 'sha256': hashlib.sha256(new[name]).hexdigest()}
                        for name in ('.linux', '.dtbauto', '.initrd')},
    'native_hardware_validated': False,
}
with (T / 'dt21-artifact-audit.json').open('x') as output:
    json.dump(report, output, indent=2)
with (T / 'dt21-candidate.efi').open('xb') as output:
    output.write(data)
print(json.dumps(report, indent=2))
