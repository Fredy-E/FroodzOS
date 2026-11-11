#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Rebuild SHA256SUMS from the files actually present (every file except SHA256SUMS itself).

Run after adding or changing files, then run tools/verify-publication.py. The historical
publication-manifest.json (the 19 October source manifest) is hashed like any other file but is never
rewritten: per docs/PUBLICATION.md it keeps its historical meaning and current integrity uses SHA256SUMS.
This tool only hashes and lists files; it never decides what is safe to publish. The verifier refuses
binaries, keys, private paths and oversized files, and review is still required before anything is pushed.
"""
import argparse
import hashlib
import json
from pathlib import Path

CHECKSUMS = 'SHA256SUMS'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    entries = {}
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if '.git' in rel.parts or path.is_symlink() or not path.is_file() or rel.as_posix() == CHECKSUMS:
            continue
        entries[rel.as_posix()] = digest(path)
    (root / CHECKSUMS).write_bytes(''.join('%s  %s\n' % (entries[n], n) for n in sorted(entries)).encode('ascii'))
    print(json.dumps({'checksum_entries': len(entries)}, indent=2))


if __name__ == '__main__':
    main()
