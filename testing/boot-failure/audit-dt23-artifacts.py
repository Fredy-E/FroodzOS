#!/usr/bin/env python3
"""Gate dt23 PID1-wrapper provenance: kernel/DT/stub/cmdline identical to dt21."""
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
OLD = Path('/home/builder/uki-v2-dt22/vmlinuz-live.efi')
NEW = Path('/home/builder/uki-v2-dt23/vmlinuz-live.efi')


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
for name in ('.linux', '.hwids', '.cmdline', '.text', '.dtbauto'):
    assert old[name] == new[name], 'Non-initramfs change (must stay dt21-identical): ' + name
assert new['.initrd'] != old['.initrd']
assert new['.linux'] == (K / 'arch/arm64/boot/Image').read_bytes()
assert new['.dtbauto'] == (K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb').read_bytes()
assert new['.initrd'] == Path('/home/builder/uki-v2-dt23/live-initramfs.img').read_bytes()
assert b'efi-pstore.pstore_disable=1' in new['.cmdline']
board = json.loads(Path('/home/builder/boot-failure-tests/dt23-dtb-prebuild-check.json').read_text())
assert board['passed']
args = ['python3', str(P / 'builder/validate-live-initramfs.py'),
        '/home/builder/uki-v2-dt23/live-initramfs.img', '--require-local-firmware',
        '--require-log-capture', '--require-platform-usb']
validation = json.loads(subprocess.check_output(args, text=True))
assert validation['passed']
with tempfile.TemporaryDirectory(prefix='dt23-old-', dir='/home/builder/boot-failure-tests') as a, \
     tempfile.TemporaryDirectory(prefix='dt23-new-', dir='/home/builder/boot-failure-tests') as b:
    for path, target in [('/home/builder/uki-v2-dt22/live-initramfs.img', a),
                         ('/home/builder/uki-v2-dt23/live-initramfs.img', b)]:
        subprocess.run(['lsinitcpio', '-x', path], cwd=target, capture_output=True, check=True)
    for name in ('usr/bin/kestrel-checkpoint', 'hooks/kestrel_efilog',
                 'hooks/kestrel_log', 'usr/bin/kestrel-init-log',
                 'usr/bin/kestrel-root-log'):
        assert (Path(a) / name).read_bytes() == (Path(b) / name).read_bytes(), name
    pid1 = (Path(b) / 'usr/bin/kestrel-pid1').read_bytes()
    assert pid1 == (P / 'builder/diagnostics/kestrel-pid1.sh').read_bytes()
    assert (Path(b) / 'usr/bin/kestrel-pid1').stat().st_mode & 0o111
    hook = (Path(b) / 'hooks/kestrel_log').read_text()
    assert 'KESTREL_PID1_STAGED' in hook and 'KESTREL_PRESWITCH_RECORDED' in hook
    assert 'cp /usr/bin/kestrel-pid1 /sysroot/usr/local/sbin/kestrel-pid1' in hook
    for name in ('gpi', 'i2c-qcom-geni', 'phy-nxp-ptn3222', 'qrtr', 'qrtr-smd'):
        result = subprocess.run(['modprobe', '-d', b, '-S', '7.3.0-rc3',
                                 '--show-depends', name], capture_output=True, text=True, check=True)
        assert 'insmod ' in result.stdout, (name, result.stdout)

report = {
    'passed': True, 'revision': 'v2-dt23', 'uki_bytes': len(data),
    'uki_sha256': hashlib.sha256(data).hexdigest(),
    'old_uki_sha256': hashlib.sha256(old_data).hexdigest(),
    'kernel_dtb_stub_cmdline_unchanged_from_dt22': True,
    'board_dependencies': board,
    'pid1_wrapper_present_executable': True,
    'preswitch_log_present_in_hook': True,
    'checkpoint_and_efilog_unchanged_from_dt21': True,
    'module_dependency_resolution': True,
    'initramfs_validation': validation,
    'embedded_inputs': {name: {'bytes': len(new[name]), 'sha256': hashlib.sha256(new[name]).hexdigest()}
                        for name in ('.linux', '.dtbauto', '.initrd')},
    'native_hardware_validated': False,
}
with (T / 'dt23-artifact-audit.json').open('x') as output:
    json.dump(report, output, indent=2)
with (T / 'dt23-candidate.efi').open('xb') as output:
    output.write(data)
print(json.dumps(report, indent=2))
