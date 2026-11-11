#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Scan for secrets and personal data before anything is published.

Default mode checks only the lines ADDED relative to a base ref (what a pull request introduces), so the historical
evidence already in the tree does not make every run fail:

    python tools/check-privacy.py --base origin/main

`--all` scans the whole working tree and only reports (exit status 0) so the existing baseline can be reviewed.
It is a pattern check, not a guarantee: a clean result does not replace review. Patterns: access tokens and private
key blocks, e-mail addresses (other than noreply/example), real Windows profile paths, MAC addresses, IPv4 addresses in
private ranges. Add a justified exception to ALLOW below in the same pull request that needs it.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'github token': re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b'),
    'aws key id': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'slack token': re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b'),
    'generic api key': re.compile(r'\bsk-[A-Za-z0-9]{32,}\b'),
    'private key block': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'e-mail address': re.compile(r'\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|example\.|noreply\.)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?!(?:service|socket|target|timer|mount|path|slice|scope|device|swap|py|sh)\b)[A-Za-z]{2,}\b'),
    'windows profile path': re.compile(r'[A-Za-z]:\\+Users\\+(?!Public\b|Default\b|<|%|\$|USERNAME\b|user\b)[A-Za-z0-9._-]{2,}\\'),
    'mac address': re.compile(r'\b(?!00:00:00:00:00:00)(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'),
    'private ipv4': re.compile(r'\b(?:192\.168|10\.\d{1,3})\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b'),
}
# Allowed findings: (file prefix, pattern name, reason). Keep this list short and justified.
ALLOW = [
    ('docs/history/', 'windows profile path', 'historical conversation transcripts already public'),
    ('testing/', 'windows profile path', 'frozen evidence, hash-pinned'),
    ('docs/dt20-native-log-comparison.md', 'windows profile path', 'already public'),
    ('docs/decisions.md', 'e-mail address', 'public upstream contact (CachyOS admin), not personal'),
    ('docs/project-brief.md', 'e-mail address', 'public upstream contact (CachyOS admin), not personal'),
    ('docs/research/original-package-strategy.md', 'e-mail address', 'public upstream contact (CachyOS admin), not personal'),
    ('docs/phase1-results.md', None, 'public Arch Linux ARM signing identity and a generic WSL subnet'),
    ('tools/check-privacy.py', None, 'the patterns themselves'),
    ('SECURITY.md', 'e-mail address', 'reporting contact, if present'),
]


def allowed(rel, name):
    return any(rel.startswith(p) and n in (None, name) for p, n, _ in ALLOW)


def scan_text(rel, text, out):
    for ln, line in enumerate(text.splitlines(), 1):
        for name, rx in PATTERNS.items():
            if rx.search(line) and not allowed(rel, name):
                out.append((rel, ln, name, line.strip()[:120]))


def added_lines(base):
    diff = subprocess.run(['git', 'diff', '--unified=0', '--no-color', base + '...HEAD', '--'],
                          cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if diff.returncode != 0:
        sys.exit('git diff failed: ' + diff.stderr.strip())
    rel, ln, out = None, 0, []
    for line in diff.stdout.splitlines():
        if line.startswith('+++ b/'):
            rel = line[6:]
        elif line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            ln = int(m.group(1)) - 1 if m else 0
        elif line.startswith('+') and not line.startswith('+++') and rel:
            ln += 1
            scan_text_line(rel, ln, line[1:], out)
    return out


def scan_text_line(rel, ln, line, out):
    for name, rx in PATTERNS.items():
        if rx.search(line) and not allowed(rel, name):
            out.append((rel, ln, name, line.strip()[:120]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='origin/main', help='base ref for the added-lines scan')
    ap.add_argument('--all', action='store_true', help='scan the whole tree, report only')
    args = ap.parse_args()
    out = []
    if args.all:
        listing = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
        for rel in listing:
            p = ROOT / rel
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if b'\x00' in data or len(data) > 5_000_000:
                continue
            scan_text(rel, data.decode('utf-8', errors='replace'), out)
    else:
        out = added_lines(args.base)
    for rel, ln, name, snippet in out:
        print('%s:%d: %s: %s' % (rel, ln, name, snippet))
    print('%d finding(s)%s' % (len(out), ' (report only)' if args.all else ''))
    return 0 if args.all or not out else 1


if __name__ == '__main__':
    sys.exit(main())
