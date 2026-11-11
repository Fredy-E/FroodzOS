#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""List the packages of an extracted live root by origin repository, packager and licence (read-only).

Input: a directory that contains var/lib/pacman (local and sync databases) as extracted from airootfs.sfs.
Output: a JSON file with every package (name, version, repo guess, packager, licences, url) and a summary on stdout.
"""
import json, os, re, sys, tarfile, collections

root = sys.argv[1]
out = sys.argv[2]
local = os.path.join(root, 'var/lib/pacman/local')
sync = os.path.join(root, 'var/lib/pacman/sync')


def parse_desc(text):
    d, key = {}, None
    for line in text.splitlines():
        m = re.match(r'^%([A-Z0-9]+)%$', line)
        if m:
            key = m.group(1)
            d[key] = []
        elif line and key:
            d[key].append(line)
    return d


repo_of = {}
for db in sorted(os.listdir(sync)):
    if not db.endswith('.db'):
        continue
    repo = db[:-3]
    try:
        with tarfile.open(os.path.join(sync, db)) as t:
            for m in t.getmembers():
                if m.name.endswith('/desc'):
                    d = parse_desc(t.extractfile(m).read().decode('utf-8', 'replace'))
                    n = d.get('NAME', [''])[0]
                    repo_of.setdefault(n, []).append(repo)
    except Exception as e:  # unreadable database
        print('warning: cannot read', db, e, file=sys.stderr)

pk = []
for entry in sorted(os.listdir(local)):
    p = os.path.join(local, entry, 'desc')
    if not os.path.isfile(p):
        continue
    d = parse_desc(open(p, encoding='utf-8', errors='replace').read())
    name = d.get('NAME', [entry])[0]
    pk.append({
        'name': name,
        'version': d.get('VERSION', [''])[0],
        'repos': repo_of.get(name, []),
        'packager': d.get('PACKAGER', [''])[0],
        'licenses': d.get('LICENSE', []),
        'url': d.get('URL', [''])[0],
        'size': int(d.get('SIZE', ['0'])[0]),
        'reason': d.get('REASON', ['0'])[0],
    })
json.dump(pk, open(out, 'w', encoding='utf-8'), indent=1)

by_repo = collections.Counter(','.join(x['repos']) or '(none)' for x in pk)
by_pk = collections.Counter(x['packager'] for x in pk)
print('packages:', len(pk))
print('by repo:', dict(by_repo))
print('by packager:', dict(by_pk.most_common(8)))
for x in pk:
    if not x['repos'] or any(r not in ('core', 'extra') for r in x['repos']):
        print('NONSTD', x['name'], x['version'], ','.join(x['repos']) or '(none)', '|', x['packager'][:50], '|', ' '.join(x['licenses'])[:50])
