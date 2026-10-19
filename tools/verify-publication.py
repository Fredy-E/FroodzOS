#!/usr/bin/env python3
"""Verify a fresh source checkout/ZIP without requiring Git or native hardware."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

FORBIDDEN_SUFFIXES = {'.key', '.pem', '.p12', '.pfx', '.vhdx', '.iso', '.img', '.fat', '.raw', '.bin', '.efi', '.dtb', '.sfs', '.squashfs', '.deb', '.pyc', '.pyo', '.gz', '.xz', '.zst', '.zip', '.tar', '.tgz', '.bz2', '.7z', '.fd', '.exe', '.dll', '.sys', '.cat', '.mod'}
FORBIDDEN_PARTS = {'keys', '.gnupg', '.ssh', 'private', '__pycache__'}

def checksum_entries(text):
    entries = {}
    for number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError('Malformed SHA256SUMS line %d' % number)
        digest, name = match.groups()
        pure = PurePosixPath(name)
        if pure.is_absolute() or '..' in pure.parts or '\\' in name or ':' in name or str(pure) != name or name == 'SHA256SUMS':
            raise ValueError('Unsafe checksum filename on line %d' % number)
        if name in entries:
            raise ValueError('Duplicate checksum filename: ' + name)
        entries[name] = digest
    if not entries:
        raise ValueError('Empty checksum manifest')
    return entries

def verify(root):
    root = Path(root).resolve()
    sums = root / 'SHA256SUMS'
    if not sums.is_file():
        raise ValueError('Missing SHA256SUMS')
    raw = sums.read_bytes()
    if b'\r' in raw:
        raise ValueError('SHA256SUMS must use LF, not CRLF')
    entries = checksum_entries(raw.decode('ascii'))
    found = set()
    errors = []
    for path in root.rglob('*'):
        rel = path.relative_to(root).as_posix()
        if '.git' in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            errors.append('Symlink is not allowed: ' + rel)
            continue
        if not path.is_file() or rel == 'SHA256SUMS':
            continue
        found.add(rel)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or FORBIDDEN_PARTS.intersection(path.relative_to(root).parts) or path.name == '.env' or path.name.startswith('.env.'):
            errors.append('Forbidden private/binary file: ' + rel)
        if path.stat().st_size > 25 * 1024 * 1024:
            errors.append('Unexpected large source file: ' + rel)
        if rel not in entries:
            errors.append('Unlisted file: ' + rel)
            continue
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != entries[rel]:
            errors.append('Checksum mismatch: ' + rel)
    for missing in sorted(set(entries) - found):
        errors.append('Missing file: ' + missing)
    if errors:
        raise ValueError('\n'.join(errors))
    return {'passed': True, 'files_verified': len(found), 'git_required': False, 'binary_release': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root), indent=2))
    except (ValueError, OSError, UnicodeError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
