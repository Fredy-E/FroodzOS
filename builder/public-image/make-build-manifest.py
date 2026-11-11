#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Write an exact-build manifest (release/manifests/<build-id>.json) from measured values.

    make-build-manifest.py --id <build-id> --facts facts.json --artifact label=path [--artifact label=path ...] --out <file>

`facts.json` carries what cannot be measured from files (source revision, toolchain versions, test receipts, limitations).
Artifact sizes and SHA-256 digests are measured here. Nothing is copied from approval claims: `publication.status` is
always 'unpublished' and the three authorisation flags are false until the owner changes them in a separate step.
"""
import argparse, hashlib, json, pathlib, sys

ap = argparse.ArgumentParser()
ap.add_argument('--id', required=True)
ap.add_argument('--facts', required=True)
ap.add_argument('--artifact', action='append', default=[], help='label=path')
ap.add_argument('--out', required=True)
a = ap.parse_args()
facts = json.load(open(a.facts, encoding='utf-8'))
arts = []
for spec in a.artifact:
    label, path = spec.split('=', 1)
    p = pathlib.Path(path)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    arts.append({'label': label, 'file': p.name, 'bytes': p.stat().st_size, 'sha256': h.hexdigest()})
man = {
    'build_id': a.id,
    'schema': 'froodzos-build-manifest/1',
    'product': {'version': '0.1.0-dev', 'codename': 'Maverick'},
    'source': facts['source'],
    'inputs': facts['inputs'],
    'toolchain': facts['toolchain'],
    'board_profile': facts['board_profile'],
    'artifacts': arts,
    'test_receipts': facts['test_receipts'],
    'limitations': facts['limitations'],
    'publication': {'status': 'unpublished', 'owner_authorised': False, 'rights_cleared': False, 'qualified_release': False},
}
pathlib.Path(a.out).write_text(json.dumps(man, indent=2) + '\n', encoding='utf-8')
print('wrote', a.out, len(arts), 'artifact(s)')
