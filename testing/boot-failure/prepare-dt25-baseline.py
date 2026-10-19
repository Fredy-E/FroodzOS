#!/usr/bin/env python3
"""Freeze dt24 provenance before dt25 work; never touch USB or firmware."""
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
BASE = Path('/home/builder/boot-failure-tests/dt25-baseline')
OLD = Path('/home/builder/uki-v2-dt24')
SOURCE = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
DTB = SOURCE.with_suffix('.dtb')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pe_sections(path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    assert struct.unpack_from('<H', data, pe + 4)[0] == 0xaa64
    count = struct.unpack_from('<H', data, pe + 6)[0]
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    sections = {}
    for i in range(count):
        pos = pe + 24 + optional + 40 * i
        name = data[pos:pos + 8].rstrip(b'\0').decode('ascii')
        size = struct.unpack_from('<I', data, pos + 8)[0]
        raw_size, offset = struct.unpack_from('<II', data, pos + 16)
        assert 0 <= size <= raw_size and offset + size <= len(data)
        sections[name] = data[offset:offset + size]
    return sections


def main():
    assert not BASE.exists(), 'Fresh baseline required; preserve prior evidence'
    assert not (T / 'dt25-baseline.json').exists()
    assert not Path('/home/builder/uki-v2-dt25').exists()
    assert shutil.disk_usage('/mnt/d').free > 10 * 1024**3, 'Host free-space gate'
    manifest = json.loads((T / 'dt24-update-manifest.json').read_text())
    uki = OLD / 'vmlinuz-live.efi'
    assert sha(uki) == manifest['uki_sha256']
    sections = pe_sections(uki)
    assert sections['.linux'] == (K / 'arch/arm64/boot/Image').read_bytes()
    assert sections['.dtbauto'] == DTB.read_bytes()
    assert sections['.initrd'] == (OLD / 'live-initramfs.img').read_bytes()
    packed = {
        'hooks/kestrel_log': 'builder/initcpio/hooks/kestrel_log',
        'hooks/kestrel_efilog': 'builder/initcpio/hooks/kestrel_efilog',
        'hooks/kestrel_text': 'builder/initcpio/hooks/kestrel_text',
        'usr/bin/kestrel-init-log': 'builder/diagnostics/kestrel-init-log.sh',
        'usr/bin/kestrel-root-log': 'builder/diagnostics/kestrel-root-log.sh',
        'usr/bin/kestrel-pid1': 'builder/diagnostics/kestrel-pid1.sh',
        'etc/kestrel-text-login': 'builder/diagnostics/kestrel-text-login.sh',
        'etc/kestrel-text-proof': 'builder/diagnostics/kestrel-text-proof.sh',
        'etc/kestrel-text-bashrc': 'builder/diagnostics/kestrel-text-bashrc',
        'etc/kestrel-text-getty.conf': 'builder/diagnostics/kestrel-text-getty.conf',
    }
    packed_hashes = {}
    with tempfile.TemporaryDirectory(prefix='dt25-baseline-', dir='/home/builder/boot-failure-tests') as tmp:
        subprocess.run(['lsinitcpio', '-x', str(OLD / 'live-initramfs.img')], cwd=tmp, check=True, capture_output=True)
        for name, relative in packed.items():
            actual = Path(tmp) / name
            assert actual.read_bytes() == (P / relative).read_bytes(), 'Source differs from accepted dt24: ' + name
            packed_hashes[name] = sha(actual)
        packed_hashes['usr/bin/kestrel-checkpoint'] = sha(Path(tmp) / 'usr/bin/kestrel-checkpoint')
    BASE.mkdir()
    copies = [(SOURCE, 'board.dts'), (DTB, 'board.dtb'), (K / '.config', 'kernel.config')]
    for relative in list(packed.values()) + ['builder/build-live-uki.sh', 'builder/validate-live-initramfs.py',
            'builder/platform_usb_gate.py', 'builder/platform_input_gate.py', 'builder/diagnostics/kestrel-checkpoint.c']:
        copies.append((P / relative, relative))
    files = {}
    for source, name in copies:
        target = BASE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        files[name] = {'source': str(source), 'sha256': sha(target), 'bytes': target.stat().st_size}
    report = {'passed': True, 'revision': 'dt25-preparation', 'accepted_native_fallback': 'v2-dt24',
              'native_boot_id': '9c31cdbb-5aad-4802-9ea7-8101066b591e',
              'dt24_uki_sha256': sha(uki), 'kernel_sha256': hashlib.sha256(sections['.linux']).hexdigest(),
              'dtb_sha256': sha(DTB), 'baseline_dir': str(BASE), 'files': files,
              'packed_dt24_hashes': packed_hashes,
              'usb_modified': False, 'firmware_modified': False, 'native_graphics_validated': False}
    with (T / 'dt25-baseline.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))
    print('DT25_DT24_BASELINE_PRESERVED')


if __name__ == '__main__':
    main()
