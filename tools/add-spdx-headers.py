#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Add SPDX licence headers to the project's ORIGINAL source files (dry run by default).

Only the directories listed in INCLUDE are touched. Third-party or derived material (third_party/, pkgs/,
kernel patches, the device tree, stubble sources, mkinitcpio-derived hooks that already carry a licence) and frozen
evidence under testing/boot-failure/ and research/ are never modified: editing them would change hashed evidence
or relicense code the project does not own.

A file is skipped if it already contains any SPDX-License-Identifier line, is not valid UTF-8, or contains NUL bytes.
BOM and line endings (LF or CRLF) are preserved. The header goes after a BOM, a shebang and a PEP 263 coding line.

Usage:  python tools/add-spdx-headers.py            # list what would change
        python tools/add-spdx-headers.py --apply    # write the headers
After --apply run tools/regenerate-publication.py (SHA256SUMS) and tools/verify-publication.py.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENT = 'GPL-2.0-or-later'
# (directory relative to ROOT, suffix list or None for "extensionless files too", recurse?)
INCLUDE = [
    ('builder', ('.sh', '.py'), False),
    ('builder/initcpio/hooks', None, False),
    ('tools', ('.sh', '.py', '.ps1'), False),
    ('tests', ('.py',), False),
    ('testing/control', ('.sh', '.ps1', '.py'), False),
    ('boards/lenovo-83n3/touchpad', ('.py', '.service'), False),
]
CODING = re.compile(rb'^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)')


def candidates():
    for rel, suffixes, recurse in INCLUDE:
        base = ROOT / rel
        if not base.is_dir():
            continue
        it = base.rglob('*') if recurse else base.iterdir()
        for p in sorted(it):
            if p.is_file() and (suffixes is None or p.suffix in suffixes):
                yield p


def plan(path):
    data = path.read_bytes()
    if b'\x00' in data:
        return None, 'binary'
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return None, 'not utf-8'
    if 'SPDX-License-Identifier' in text:
        return None, 'already tagged'
    bom = '﻿' if text.startswith('﻿') else ''
    body = text[len(bom):]
    eol = '\r\n' if '\r\n' in body else '\n'
    lines = body.split(eol)
    at = 0
    if lines and lines[0].startswith('#!'):
        at = 1
    if len(lines) > at and CODING.match(lines[at].encode('utf-8')):
        at += 1
    header = ['# SPDX-License-Identifier: ' + IDENT]
    new = bom + eol.join(lines[:at] + header + lines[at:])
    return new, 'add'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='write the headers (default: dry run)')
    args = ap.parse_args()
    changed = skipped = 0
    for p in candidates():
        new, why = plan(p)
        rel = p.relative_to(ROOT).as_posix()
        if new is None:
            skipped += 1
            if why != 'already tagged':
                print('skip %s (%s)' % (rel, why))
            continue
        changed += 1
        print('%s %s' % ('tag ' if args.apply else 'would tag', rel))
        if args.apply:
            p.write_bytes(new.encode('utf-8'))
    print('%d file(s) %s, %d skipped' % (changed, 'tagged' if args.apply else 'would be tagged', skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
