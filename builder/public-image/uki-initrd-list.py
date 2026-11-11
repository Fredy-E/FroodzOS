#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Summarise the initramfs (newc cpio) inside a UKI: top-level sizes, firmware vendors, and non-standard files (read-only)."""
import collections, struct, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
data = open(sys.argv[1], 'rb').read()
pe = struct.unpack_from('<I', data, 0x3c)[0]
nsec = struct.unpack_from('<H', data, pe + 6)[0]
optsz = struct.unpack_from('<H', data, pe + 20)[0]
off = pe + 24 + optsz
blob = None
for i in range(nsec):
    name, vsz, va, rsz, rptr = struct.unpack_from('<8sIIII', data, off + 40 * i)
    if name.rstrip(b'\0') == b'.initrd':
        blob = data[rptr:rptr + vsz]
pos, files, sizes = 0, [], collections.Counter()
while pos + 110 <= len(blob):
    if blob[pos:pos + 6] != b'070701':
        break
    f = [int(blob[pos + 6 + 8 * k:pos + 14 + 8 * k], 16) for k in range(13)]
    mode, filesize, namesize = f[1], f[6], f[11]
    name = blob[pos + 110:pos + 110 + namesize - 1].decode('utf-8', 'replace')
    pos += 110 + namesize
    pos = (pos + 3) & ~3
    if name == 'TRAILER!!!':
        # a second cpio archive may follow (concatenated); keep scanning
        pos = (pos + 3) & ~3
        continue
    files.append((name, filesize, mode))
    top = '/'.join(name.split('/')[:3])
    sizes[top] += filesize
    pos += filesize
    pos = (pos + 3) & ~3
print('entries:', len(files), ' total bytes:', sum(s for _, s, _ in files))
for k, v in sizes.most_common(14):
    print('%10d  %s' % (v, k))
fw = [n for n, s, m in files if 'firmware' in n and s > 0]
print('firmware files:', len(fw))
vend = collections.Counter(n.split('firmware/')[1].split('/')[0] for n in fw if 'firmware/' in n)
print('firmware top dirs:', dict(vend.most_common(12)))
odd = [n for n, s, m in files if any(x in n for x in ('kestrel', 'private', '.key', 'secret', 'shadow', 'passwd', '.ssh', 'gnupg'))]
print('suspicious names:', odd[:20])
