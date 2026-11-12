#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Estimate what installing candidate packages would add to a root (read-only, from pacman sync and local databases).

    pkg-resolve.py <extracted root dir containing var/lib/pacman> pkg [pkg ...]

Prints availability, version, licences, download and installed size, and the dependency closure not yet installed.
Virtual dependencies are resolved to the first provider found, so the closure is an estimate; pacman does the real resolution.
"""
import os, re, sys, tarfile

root, wanted = sys.argv[1], sys.argv[2:]
sync, local = os.path.join(root, 'var/lib/pacman/sync'), os.path.join(root, 'var/lib/pacman/local')


def parse(text):
    d, key = {}, None
    for line in text.splitlines():
        m = re.match(r'^%([A-Z0-9]+)%$', line)
        if m:
            key = m.group(1); d[key] = []
        elif line and key:
            d[key].append(line)
    return d


repo = {}
for db in sorted(os.listdir(sync)):
    if not db.endswith('.db'):
        continue
    with tarfile.open(os.path.join(sync, db)) as t:
        for m in t.getmembers():
            if m.name.endswith('/desc'):
                f = t.extractfile(m)
                if f is None:
                    continue
                d = parse(f.read().decode('utf-8', 'replace'))
                if 'NAME' not in d:
                    continue
                n = d['NAME'][0]
                repo.setdefault(n, (db[:-3], d))
installed = set()
provided = {}
for e in os.listdir(local):
    p = os.path.join(local, e, 'desc')
    if os.path.isfile(p):
        d = parse(open(p, encoding='utf-8', errors='replace').read())
        installed.add(d['NAME'][0])
        for pr in d.get('PROVIDES', []):
            provided[re.split(r'[<>=]', pr)[0]] = d['NAME'][0]
prov = {}
for n, (r, d) in repo.items():
    for pr in d.get('PROVIDES', []):
        prov.setdefault(re.split(r'[<>=]', pr)[0], n)


def resolve(dep):
    name = re.split(r'[<>=]', dep)[0]
    if name in installed or name in provided:
        return None
    if name in repo:
        return name
    return prov.get(name, '?' + name)


closure, queue, missing = {}, list(wanted), []
while queue:
    n = queue.pop()
    if n in closure or n in installed:
        continue
    if n.startswith('?') or n not in repo:
        missing.append(n.lstrip('?')); continue
    closure[n] = repo[n]
    for dep in repo[n][1].get('DEPENDS', []):
        r = resolve(dep)
        if r:
            queue.append(r)
print('%-24s %-12s %-10s %-9s %-9s %s' % ('package', 'version', 'repo', 'download', 'installed', 'licences'))
tot_c = tot_i = 0
for n in wanted:
    if n in repo:
        r, d = repo[n]
        print('%-24s %-12s %-10s %6.1f MB %6.1f MB %s' % (n, d['VERSION'][0], r, int(d['CSIZE'][0]) / 1e6, int(d['ISIZE'][0]) / 1e6, ' '.join(d.get('LICENSE', []))[:60]))
    elif n in installed:
        print('%-24s already installed' % n)
    else:
        print('%-24s NOT IN THE SYNC DATABASES' % n)
for n, (r, d) in closure.items():
    tot_c += int(d['CSIZE'][0]); tot_i += int(d['ISIZE'][0])
print('\nclosure to add: %d packages, download %.0f MB, installed %.0f MB' % (len(closure), tot_c / 1e6, tot_i / 1e6))
print('unresolved:', sorted(set(missing)))
print('closure:', ' '.join(sorted(closure)))
if os.environ.get('FZ_LICENCES'):
    print('\nclosure licences:')
    for n in sorted(closure):
        r, d = closure[n]
        print('%-28s %-12s %-8s %6.1f MB  %s' % (n, d['VERSION'][0], r, int(d['CSIZE'][0]) / 1e6, ' '.join(d.get('LICENSE', []))))
