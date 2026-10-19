#!/usr/bin/env python3
"""Gate dt24 provenance, input closure, scoped DT changes and unchanged logger."""
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
OUT = Path('/home/builder/uki-v2-dt24')


def sections(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    machine, count = struct.unpack_from('<HH', data, pe + 4)
    assert machine == 0xaa64
    opt = struct.unpack_from('<H', data, pe + 20)[0]
    result = {}
    for index in range(count):
        off = pe + 24 + opt + 40 * index
        name = data[off:off + 8].rstrip(b'\0').decode()
        size = struct.unpack_from('<I', data, off + 8)[0]
        raw_size, ptr = struct.unpack_from('<II', data, off + 16)
        assert size <= raw_size or raw_size == 0
        result[name] = data[ptr:ptr + size]
    return data, result


_, old = sections(Path('/home/builder/uki-v2-dt23/vmlinuz-live.efi'))
data, new = sections(OUT / 'vmlinuz-live.efi')
for name in ['.linux', '.hwids', '.cmdline', '.text']:
    assert old[name] == new[name], 'Unexpected boot/kernel change: ' + name
assert old['.dtbauto'] != new['.dtbauto'] and old['.initrd'] != new['.initrd']
assert new['.dtbauto'] == (K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb').read_bytes()
assert new['.initrd'] == (OUT / 'live-initramfs.img').read_bytes()
board = json.loads((T / 'dt24-dtb-build-result.json').read_text())
assert board['passed'] and board['only_allowed_compiled_properties_changed']
validation = json.loads(subprocess.check_output(['python3', str(P / 'builder/validate-live-initramfs.py'),
    str(OUT / 'live-initramfs.img'), '--require-local-firmware', '--require-log-capture',
    '--require-platform-usb', '--require-platform-input'], text=True))
assert validation['passed']
with tempfile.TemporaryDirectory(prefix='dt24-old-', dir='/home/builder/boot-failure-tests') as a, \
     tempfile.TemporaryDirectory(prefix='dt24-new-', dir='/home/builder/boot-failure-tests') as b:
    for image, dest in [('/home/builder/uki-v2-dt23/live-initramfs.img', a), (str(OUT / 'live-initramfs.img'), b)]:
        subprocess.run(['lsinitcpio', '-x', image], cwd=dest, capture_output=True, check=True)
    for name in ['usr/bin/kestrel-checkpoint', 'hooks/kestrel_efilog', 'hooks/kestrel_log',
                 'usr/bin/kestrel-init-log', 'usr/bin/kestrel-root-log', 'usr/bin/kestrel-pid1',
                 'etc/kestrel-usb-log.service']:
        assert (Path(a) / name).read_bytes() == (Path(b) / name).read_bytes(), 'Logger changed: ' + name
    for packed, source in [('hooks/kestrel_text', 'builder/initcpio/hooks/kestrel_text'),
                           ('etc/kestrel-text-login', 'builder/diagnostics/kestrel-text-login.sh'),
                           ('etc/kestrel-text-proof', 'builder/diagnostics/kestrel-text-proof.sh'),
                           ('etc/kestrel-text-bashrc', 'builder/diagnostics/kestrel-text-bashrc'),
                           ('etc/kestrel-text-getty.conf', 'builder/diagnostics/kestrel-text-getty.conf')]:
        assert (Path(b) / packed).read_bytes() == (P / source).read_bytes(), packed
    for module in ['gpi', 'i2c-qcom-geni', 'phy-nxp-ptn3222', 'qrtr', 'qrtr-smd', 'i2c-hid', 'i2c-hid-of', 'hid-generic']:
        text = subprocess.check_output(['modprobe', '-d', b, '-S', '7.3.0-rc3', '--show-depends', module], text=True)
        assert 'insmod ' in text, module
report = {'passed': True, 'revision': 'v2-dt24', 'uki_bytes': len(data),
          'uki_sha256': hashlib.sha256(data).hexdigest(), 'kernel_stub_hwids_base_cmdline_unchanged': True,
          'dtb_scope': board, 'initramfs_validation': validation, 'logger_and_pid1_wrapper_unchanged': True,
          'text_hook_and_helpers_byte_exact': True, 'module_dependencies_resolve': True,
          'native_hardware_validated': False}
with (T / 'dt24-artifact-audit.json').open('x') as stream:
    json.dump(report, stream, indent=2)
with (T / 'dt24-candidate.efi').open('xb') as stream:
    stream.write(data)
print(json.dumps(report, indent=2))
