#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail when a tracked file looks like a boot log or leaks an identifier.

This is the path-and-shape layer that the line-pattern privacy scan cannot
provide. It never prints file content: a finding is a path and a reason.

Checks:
* path-shaped boot artifacts: ``Logs/``, ``boot-<id>/`` log files,
  ``streams/<name>/NNNNNN.jsonl|log``, ``events/<stamp>/...``, journal/kmsg
  exports, ``snap-*.txt``, ``event-*-up*.txt``, ``history.tsv``,
  ``*.typescript`` and screenshot directories;
* MAC-address-shaped strings and serial/PSK-shaped key/value pairs outside the
  documented synthetic fixture folder;
* renamed boot logs: a text file over 64 KiB with at least 20 kernel/journal
  line-shaped records.

Allowlist: ``tests/fixtures/logs/`` contains synthetic fixtures only (fake
secrets, fake MACs and fake serials), ``docs/history/`` is already-public
historical conversation text, and ``testing/boot-failure/`` is frozen,
hash-pinned failure evidence that already contains public device strings; both
of the latter are exempt from content findings only, not from path rules.

Default mode reads ``git ls-files``. ``--root DIR`` scans a plain directory
(used by the tests) and does not need Git. Never writes anything.

Run from the repository root::
    python -B tools/check-log-leaks.py
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PREFIX = "tests/fixtures/logs/"
HISTORY_PREFIX = "docs/history/"
BASELINE_PREFIXES = ("testing/boot-failure/",)
MAX_CONTENT_BYTES = 10 * 1024 * 1024
LOG_HEURISTIC_BYTES = 64 * 1024
LOG_HEURISTIC_LINES = 20

PATH_RULES = (
    ("Logs directory", re.compile(r"(^|/)Logs/")),
    ("boot-folder log artifact", re.compile(
        r"(^|/)boot-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){0,4}(?:-[0-9a-fA-F]{12})?/"
        r"(?:[^/]*\.(?:log|jsonl|kmsg|journal|typescript|txt|gz)|history\.tsv|summary\.(?:txt|json)|"
        r"index(?:\.partial)?\.json|boot\.json|alive\.txt|events\.log)$")),
    ("recorder stream segment", re.compile(r"(^|/)streams/[^/]+/\d{6}\.(?:jsonl|log)(?:\.gz)?$")),
    ("recorder event bundle", re.compile(
        r"(^|/)events/\d{8}T\d{6}Z-[^/]+/(?:event\.json|snapshot\.txt|dmesg-tail\.txt|journal-tail\.jsonl|state\.json)$")),
    ("journal export", re.compile(r"(^|/)(?:journal|dmesg)-[^/]*\.log(?:\.gz)?$")),
    ("kernel kmsg export", re.compile(r"(^|/)(?:01-kernel-kmsg|03-userspace-journal|kernel-warnings|journal-errors)(?:\.\d+)?\.log$")),
    ("session status dump", re.compile(r"(^|/)(?:00-status|04-userspace-status|06-text-startup|07-typed-command|checkpoint-status)\.(?:txt|log)$")),
    ("snapshot/event text", re.compile(r"(^|/)(?:snap-\d{3}-up\d+|event-[a-z]+-up\d+)\.txt$")),
    ("history export", re.compile(r"(^|/)history\.tsv$")),
    ("terminal typescript", re.compile(r"(^|/)[^/]+\.typescript$")),
    ("journal raw directory", re.compile(r"(^|/)journal-raw/")),
    ("live/previous boot text", re.compile(r"(^|/)(?:journal-live|prevboot)-[^/]*$")),
    ("screenshot directory", re.compile(r"(^|/)(?:screenshots?|screencaps?)/")),
    ("webp evidence image", re.compile(r"(^|/)[^/]+\.webp$")),
)
MAC_RE = re.compile(r"\b(?!00:00:00:00:00:00)(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
SERIAL_RE = re.compile(
    r"(?i)\b(serial(?:\s*number)?|serialno|s/n|iserial)\s*[=:]\s*[\"']?([A-Za-z0-9][A-Za-z0-9._-]{5,})")
PSK_RE = re.compile(
    r"(?i)\b(password|passwd|passphrase|psk|wep-key[0-3]?|private_key_passwd)\s*[=:]\s*"
    r"[\"']?([^\"'\s]{6,})")
PLACEHOLDER_RE = re.compile(
    r"(?i)(?:<|>|\$|\{|\}|%|redacted|placeholder|changeme|"
    r"not-a-secret|correct-horse|xxxx|\*\*\*)")
KMSG_LINE_RE = re.compile(r"^\d+,\d+,\d+,[^;]*;", re.M)
MONO_LINE_RE = re.compile(r"^\[\s*\d+\.\d+\]\s", re.M)
JOURNAL_LINE_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d\s+\S+\s+\S+:", re.M)
SYSTEMD_LINE_RE = re.compile(r"systemd\[\d+\]:")


# Redaction tests that must contain fake secrets to prove they are removed.
# Every value in them is synthetic (locally administered test MAC,
# FAKE-* passwords); keep real values out of these files.
SYNTHETIC_TEST_FILES = frozenset((
    "tests/test_smartlog_v3.py",
    "tests/test_term_record.py",
    "tests/test_ui_capture.py",
))


def allowed(rel, root=None):
    if rel.startswith(FIXTURE_PREFIX) or rel in SYNTHETIC_TEST_FILES:
        return True
    if root is not None:
        try:
            root_rel = Path(root).resolve().relative_to(ROOT).as_posix().rstrip("/")
        except ValueError:
            return False
        if root_rel == FIXTURE_PREFIX.rstrip("/") or root_rel.startswith(FIXTURE_PREFIX):
            return True
    return False


def looks_like_serial(value):
    value = value.strip()
    if len(value) < 8 or len(value) > 64 or PLACEHOLDER_RE.search(value):
        return False
    digits = sum(ch.isdigit() for ch in value)
    return digits >= 4


def looks_like_psk(value):
    return bool(value) and not value.endswith("_") and not PLACEHOLDER_RE.search(value)


def path_findings(rel):
    reasons = []
    for name, rx in PATH_RULES:
        if rx.search(rel):
            reasons.append("path looks like a boot-log artifact (%s)" % name)
    return reasons


def content_findings(rel, text):
    reasons = []
    if rel.startswith(BASELINE_PREFIXES):
        return reasons
    for match in MAC_RE.finditer(text):
        reasons.append("contains a MAC-address-shaped string")
        break
    for match in SERIAL_RE.finditer(text):
        if looks_like_serial(match.group(2)):
            reasons.append("contains a serial-number-shaped value")
            break
    for match in PSK_RE.finditer(text):
        if looks_like_psk(match.group(2)):
            reasons.append("contains a PSK/password-shaped value")
            break
    if rel.startswith(HISTORY_PREFIX) or len(text) < LOG_HEURISTIC_BYTES:
        return reasons
    counts = (
        len(KMSG_LINE_RE.findall(text)),
        len(MONO_LINE_RE.findall(text)),
        len(JOURNAL_LINE_RE.findall(text)),
        len(SYSTEMD_LINE_RE.findall(text)),
    )
    if max(counts) >= LOG_HEURISTIC_LINES:
        reasons.append("looks like a renamed boot log (%d line-shaped records)" % max(counts))
    return reasons


def scan_file(rel, data, root=None):
    if allowed(rel, root):
        return []
    findings = list(path_findings(rel))
    if b"\x00" in data[:65536] or len(data) > MAX_CONTENT_BYTES:
        return findings
    text = data.decode("utf-8", "replace")
    for reason in content_findings(rel, text):
        if reason not in findings:
            findings.append(reason)
    return findings


def collect(root, tracked):
    root = Path(root).resolve()
    if tracked:
        result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
        if result.returncode == 0:
            names = result.stdout.decode("utf-8", "replace").split("\x00")
            return [(name, root / name) for name in names if name]
        print("check-log-leaks: git ls-files failed, scanning the worktree", file=sys.stderr)
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or not path.is_file():
            continue
        files.append((rel.as_posix(), path))
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fail when a tracked file looks like a FroodzOS boot log or leaks an identifier.")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository or fixture root")
    ap.add_argument("--worktree", action="store_true", help="scan the filesystem instead of git ls-files")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print("check-log-leaks: not a directory: %s" % root, file=sys.stderr)
        return 2
    tracked = not args.worktree and (root / ".git").exists()
    findings = []
    for rel, path in collect(root, tracked):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for reason in scan_file(rel, data, root):
            findings.append({"path": rel, "reason": reason})
    findings.sort(key=lambda item: (item["path"], item["reason"]))
    if args.json:
        print(json.dumps({"passed": not findings, "findings": findings}, indent=2))
    else:
        for item in findings:
            print("%s: %s" % (item["path"], item["reason"]))
        print("%d finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
