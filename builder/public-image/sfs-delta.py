#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare two 'unsquashfs -ll' listings (dates stripped) and classify every difference."""
import collections, json, re, sys

def load(p):
    d = {}
    for line in open(p, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        m = re.match(r'^(\S+) (\S+) +(\d+) (squashfs-root.*)$', line)
        if not m:
            continue
        mode, own, size, rest = m.groups()
        path = rest.split(' -> ')[0].split(' link to ')[0]
        d[path[len('squashfs-root/'):] if path.startswith('squashfs-root/') else path] = (mode, own, size, rest)
    return d

old, new = load(sys.argv[1]), load(sys.argv[2])
removed = sorted(set(old) - set(new))
added = sorted(set(new) - set(old))
changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])

def cls(p):
    if p.startswith('usr/lib/firmware/updates'):
        return 'vendor firmware (updates/)'
    m = re.match(r'var/lib/pacman/local/(linux-firmware-[a-z]+)-', p)
    if m:
        return 'pacman db: removed firmware pkg'
    if p.startswith('usr/lib/firmware/'):
        return 'removed firmware files'
    if 'cachyos' in p:
        return 'cachyos-named path'
    if 'gnupg/private-keys' in p or 'openpgp-revocs' in p:
        return 'keyring private material'
    return 'OTHER'

c = collections.Counter(cls(p) for p in removed)
print('old', len(old), 'new', len(new), 'removed', len(removed), 'added', len(added), 'changed', len(changed))
print('removed by class:', dict(c))
print('OTHER removed:', [p for p in removed if cls(p) == 'OTHER'][:25])
print('added:', added[:25])
print('changed:', changed[:25])
fw = [p for p in removed if cls(p) == 'removed firmware files']
dirs = collections.Counter(p.split('/')[3] if len(p.split('/')) > 3 else p for p in fw)
print('removed firmware top entries:', dict(dirs.most_common(8)))
json.dump({'removed': removed, 'added': added, 'changed': changed}, open(sys.argv[3], 'w'), indent=0)
