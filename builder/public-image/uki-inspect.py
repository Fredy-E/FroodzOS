#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""List the sections of a UKI (PE/COFF) and look for vendor firmware inside its initramfs (read-only)."""
import gzip, lzma, struct, sys, zlib

def sections(data):
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe + 4] == b'PE\0\0'
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    optsz = struct.unpack_from('<H', data, pe + 20)[0]
    off = pe + 24 + optsz
    out = []
    for i in range(nsec):
        name, vsz, va, rsz, rptr = struct.unpack_from('<8sIIII', data, off + 40 * i)
        out.append((name.rstrip(b'\0').decode('ascii', 'replace'), vsz, rptr, rsz))
    return out

def decomp(blob):
    if blob[:2] == b'\x1f\x8b':
        return 'gzip', gzip.decompress(blob)
    if blob[:6] == b'\xfd7zXZ\x00':
        return 'xz', lzma.decompress(blob)
    if blob[:4] == b'\x28\xb5\x2f\xfd':
        return 'zstd', None
    if blob[:6] == b'070701':
        return 'cpio', blob
    return 'unknown %r' % blob[:4], None

path = sys.argv[1]
data = open(path, 'rb').read()
print(path, len(data), 'bytes')
for n, vsz, rptr, rsz in sections(data):
    print('  %-10s virt=%9d file=%9d' % (n, vsz, rsz))
for n, vsz, rptr, rsz in sections(data):
    if n == '.initrd':
        blob = data[rptr:rptr + min(vsz, rsz) if vsz else rsz]
        kind, raw = decomp(blob)
        print('  initrd compression:', kind)
        if raw is None and kind == 'zstd':
            print('  (zstd: inspect in the builder with zstd -dc | cpio -t)')
        else:
            for needle in (b'LENOVO', b'83N3', b'qcadsp', b'qccdsp', b'x1p42100', b'firmware/updates', b'.mbn'):
                print('  contains %-18r %s' % (needle, needle in raw))
