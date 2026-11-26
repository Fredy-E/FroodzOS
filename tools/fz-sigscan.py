#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Classify a FroodzOS boot-log folder against the local signature catalog.

Usage:
    fz-sigscan.py <boot-folder> [--top N] [--json] [--learn]
                  [--catalog tools/data/fz-signatures.json]

The catalog lives in ``tools/data/fz-signatures.json`` next to this tool (or is
given with ``--catalog``). Regexes are generic and are matched case-insensitively
against one whitespace-normalised message after its timestamp/priority prefix is
removed. Later signatures with a higher ``priority`` win, so a named issue is
reported before a generic family.

UNKNOWN clusters are always normalised before printing: MAC addresses, UUIDs,
IPv4/IPv6 addresses, SSIDs, serials, usernames, home paths, e-mail addresses and
tokens are replaced by placeholders. ``--learn`` prints those clusters with a
draft regex so a new generic signature can be added without copying a value.

Both layouts are read: v2 (``01-kernel-kmsg.log``, ``smart/*journal*.log.gz``,
``03-userspace-journal.log``) and v3 (``streams/<name>/*.jsonl|log``).

Standard library only. Read-only. Exit 0 on a readable folder, 2 when missing.
"""
import argparse
import gzip
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CATALOG = HERE / "data" / "fz-signatures.json"

KMSG_RE = re.compile(r"^(\d+),(\d+),(\d+),([^;]*);(.*)$")
MONO_PROG_RE = re.compile(r"^\[\s*(\d+\.\d+)\]\s+(\S+)\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")
MONO_RE = re.compile(r"^\[\s*(\d+\.\d+)\]\s*(.*)$")
WALL_PROG_RE = re.compile(r"^([A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d(?:\.\d+)?)\s+\S+\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")
ISO_PROG_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[,.]\d+)?(?:Z|[+-]\d\d:?\d\d))\s+\S+\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
MAC_RE = re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b|\b[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\b")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
NODE_RE = re.compile(r"\b[0-9a-f]{5,8}\.(?=[a-zA-Z])")
ATADDR_RE = re.compile(r"@[0-9a-f]{4,}\b")
LONGHEX_RE = re.compile(r"\b[0-9a-fA-F]{12,}\b")
NUM_RE = re.compile(r"(?<![\w])-?\d+(?:\.\d+)?(?![\w])")
PCT_RE = re.compile(r"\b\d+(?:\.\d+)?%")
TIME_RE = re.compile(r"\b\d\d:\d\d:\d\d(?:\.\d+)?\b")
BRACKET_PID_RE = re.compile(r"\[(\d+)\]")
DEV_RE = re.compile(r"/dev/(?:sd[a-z]\d*|mmcblk\d+(?:p\d+)?|nvme\d+n\d+(?:p\d+)?|loop\d+|dm-\d+|tty\w+|input/\w+|dri/\w+|kmsg)")
HOME_RE = re.compile(r"(?:/run/[^\s]*?)?/home/[^/\s)]+")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z0-9.-]*\.[A-Za-z]{2,}\b")
BUILDHOST_RE = re.compile(r"\([A-Za-z0-9._-]+@[A-Za-z0-9._-]+\)")
SERIALNUM_RE = re.compile(r"(?i)(SerialNumber:\s*)\S+")
UID_SERIAL_RE = re.compile(r"\bUID[0-9A-Za-z_]{6,}\b")
SSID_ANY_RE = re.compile(r"(?i)((?<![A-Za-z])(?:ssid|access point|connection)\s*[=:]\s*['\"]?)[^'\",)\s]+")
SERIAL_KV_RE = re.compile(r"(?i)\b(serial(?:\s*number)?|serialno|s/n)\s*([=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
SSID_Q_RE = re.compile(r"(?i)((?:ssid|access point|connection)[^'\"]{0,24}['\"])[^'\"]{1,64}(['\"])")
SSID_WPA_RE = re.compile(r"(?i)(SSID=')[^']*'")
NM_CONN_RE = re.compile(r"(?i)((?:connection|access point)\s+')[^']+'")
NM_SET_RE = re.compile(r"(?i)(policy: set\s+')[^']+(')")
NM_NET_RE = re.compile(r'(?i)(Connected to wireless network\s+")[^"]+"')
NM_NAME_RE = re.compile(r'(?i)(name=)"[^"]+"')
NM_CONN_DQ_RE = re.compile(r'(?i)(connection\s+)"[^"]+"')
USERNAME_RE = re.compile(r"(sudo:\s*)\S+(\s*:)")
USER_VAR_RE = re.compile(r"\bUSER=(?!root\b)\S+")
PAM_USER_RE = re.compile(r"pam_unix\(sudo:[^:)]+:")
SECRET_KV_RE = re.compile(
    r"(?i)\b(psk|passphrase|password|passwd|token|secret|api[_-]?key|wep-key[0-3]?|"
    r"wifi-sec\.psk|802-11-wireless-security\.psk)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)")
AUTH_RE = re.compile(r"(?i)\b(authorization|proxy-authorization)(\s*:\s*)(\S+)(?:\s+(\S+))?")

CLASS_RANK = {"KNOWN-ISSUE": 3, "UNKNOWN/INVESTIGATE": 2, "BENIGN-NOISE": 1}
V3_STREAM_DIRS = ("kernel", "journal", "systemd", "udev", "network", "power", "waydroid", "ui")


def read_text(path, limit=None):
    try:
        with path.open("rb") as fh:
            data = fh.read(-1 if limit is None else limit)
        return data.decode("utf-8", "replace")
    except OSError:
        return ""


def read_gz(path):
    try:
        with gzip.open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except (OSError, EOFError):
        return ""


def light(text):
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = re.sub(r"\\x[0-9a-fA-F]{2}", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalise(msg, program=None):
    text = light(msg)
    text = UID_SERIAL_RE.sub("<serial>", text)
    text = SERIALNUM_RE.sub(r"\1<serial>", text)
    text = SERIAL_KV_RE.sub(r"\1\2<serial>", text)
    text = AUTH_RE.sub(lambda m: m.group(1) + m.group(2) + "<credential>", text)
    text = SECRET_KV_RE.sub(lambda m: m.group(1) + m.group(2) + "<secret>", text)
    text = NM_CONN_RE.sub(r"\1<ssid>'", text)
    text = NM_SET_RE.sub(r"\1<ssid>\2", text)
    text = NM_NET_RE.sub(r'\1<ssid>"', text)
    text = NM_NAME_RE.sub(r'\1"<ssid>"', text)
    text = NM_CONN_DQ_RE.sub(r'\1"<ssid>"', text)
    text = SSID_WPA_RE.sub(r"\1<ssid>'", text)
    text = SSID_Q_RE.sub(r"\1<ssid>\2", text)
    text = SSID_ANY_RE.sub(r"\1<ssid>", text)
    text = EMAIL_RE.sub("<email>", text)
    text = BUILDHOST_RE.sub("(<user>@<host>)", text)
    text = HOME_RE.sub("/home/<user>", text)
    text = PAM_USER_RE.sub("pam_unix(sudo:<user>:", text)
    text = USERNAME_RE.sub(r"\1<user>\2", text)
    text = USER_VAR_RE.sub("USER=<user>", text)
    text = UUID_RE.sub("<uuid>", text)
    text = MAC_RE.sub("<mac>", text)
    text = IP_RE.sub("<ip>", text)
    text = HEX_RE.sub("<hex>", text)
    text = NODE_RE.sub("<addr>.", text)
    text = ATADDR_RE.sub("@<addr>", text)
    text = LONGHEX_RE.sub("<hex>", text)
    text = BRACKET_PID_RE.sub("[<n>]", text)
    text = DEV_RE.sub("/dev/<dev>", text)
    text = TIME_RE.sub("<time>", text)
    text = PCT_RE.sub("<pct>", text)
    text = NUM_RE.sub("<n>", text)
    if program:
        text = program + ": " + text
    text = re.sub(r"\s+", " ", text).strip()
    return text[:260] + "..." if len(text) > 260 else text


def suggest_regex(normalised):
    draft = re.escape(normalised)
    parts = {
        "<n>": r"\d+",
        "<hex>": r"0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}",
        "<addr>": r"[0-9a-f]{5,8}",
        "<mac>": r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}",
        "<uuid>": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "<ip>": r"\d{1,3}(?:\.\d{1,3}){3}",
        "<pct>": r"\d+(?:\.\d+)?%",
        "<time>": r"\d\d:\d\d:\d\d(?:\.\d+)?",
        "<user>": r"\S+",
        "<host>": r"\S+",
        "<ssid>": r"[^'\"]+",
        "<secret>": r"\S+",
        "<credential>": r"\S+",
        "<serial>": r"\S+",
        "<email>": r"\S+@\S+",
        "<dev>": r"\S+",
    }
    for key in sorted(parts, key=len, reverse=True):
        draft = draft.replace(re.escape(key), parts[key])
    draft = draft.replace(r"\ ", r"\s+").replace("  ", r"\s+")
    return "^.*" + draft + ".*$"


def load_catalog(path):
    data = json.loads(read_text(Path(path)))
    if isinstance(data, dict):
        entries = data.get("signatures", [])
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError("catalog must be a list or an object with a signatures list")
    signatures = []
    seen = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError("catalog entry is not an object")
        for key in ("id", "regex", "subsystem", "severity", "class", "issue", "note"):
            if key not in raw:
                raise ValueError("catalog entry missing %s" % key)
        if raw["id"] in seen:
            raise ValueError("duplicate signature id: %s" % raw["id"])
        seen.add(raw["id"])
        item = dict(raw)
        item["_rx"] = re.compile(str(raw["regex"]), re.I)
        item["_priority"] = int(raw.get("priority", CLASS_RANK.get(str(raw["class"]), 0) * 10))
        signatures.append(item)
    signatures.sort(key=lambda s: (-s["_priority"], s["id"]))
    return signatures


def boot_meta(path):
    status = read_text(path / "00-status.txt")
    image = re.search(r"^BOOT_IMAGE=(\S+)", status, re.M)
    root = re.search(r"\barchisobasedir=(\S+)", status)
    kernel = re.search(r"^Linux \(none\) (\S+)|Linux version (\S+)", status, re.M)
    boot_json = read_text(path / "boot.json")
    boot_id = path.name[5:] if path.name.startswith("boot-") else path.name
    if boot_json:
        try:
            obj = json.loads(boot_json)
            if isinstance(obj, dict):
                boot_id = str(obj.get("boot_id") or boot_id)
                kernel = kernel or (re.match(r"(\S+)", str(obj.get("kernel"))) if obj.get("kernel") else None)
        except (ValueError, TypeError):
            pass
    return {
        "boot": boot_id,
        "image": image.group(1).rsplit("/", 1)[-1] if image else "?",
        "root": root.group(1) if root else "?",
        "kernel": (kernel.group(1) or kernel.group(2)) if kernel else "?",
        "layout": "v3" if (path / "streams").is_dir() else ("v2" if (path / "smart").is_dir() or (path / "01-kernel-kmsg.log").is_file() else "unknown"),
    }


def _parse_text(source, text, program=None):
    for raw in text.splitlines():
        if not raw.strip():
            continue
        m = KMSG_RE.match(raw)
        if m:
            yield source, m.group(5), None
            continue
        m = MONO_PROG_RE.match(raw)
        if m:
            yield source, m.group(4), re.sub(r"\[\d+\]$", "", m.group(3))
            continue
        m = MONO_RE.match(raw)
        if m:
            yield source, m.group(2), None
            continue
        m = ISO_PROG_RE.match(raw) or WALL_PROG_RE.match(raw)
        if m:
            yield source, m.group(3), re.sub(r"\[\d+\]$", "", m.group(2))
            continue
        yield source, raw, program


def _parse_jsonl(source, text):
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            yield source, raw, None
            continue
        if not isinstance(obj, dict):
            continue
        program = obj.get("SYSLOG_IDENTIFIER") or obj.get("tag") or obj.get("unit")
        message = ""
        for key in ("MESSAGE", "msg", "message", "event", "text", "line"):
            if obj.get(key) not in (None, ""):
                message = obj[key]
                break
        if not message:
            continue
        if isinstance(message, (dict, list)):
            message = json.dumps(message, sort_keys=True, ensure_ascii=False)
        yield source, str(message), str(program) if program else None


def iter_lines(path):
    seen = set()

    def emit(items):
        for source, msg, program in items:
            msg = light(msg)
            if not msg:
                continue
            key = (source, msg[:300])
            if key in seen:
                continue
            seen.add(key)
            yield source, msg, program

    for name in ("01-kernel-kmsg.log", "03-userspace-journal.log"):
        p = path / name
        if p.is_file():
            yield from emit(_parse_text(name, read_text(p)))
    for p in sorted((path / "smart").glob("journal-*.log.gz")) if (path / "smart").is_dir() else []:
        yield from emit(_parse_text(p.name, read_gz(p)))
    for p in sorted(path.glob("journal-*.log.gz")):
        yield from emit(_parse_text(p.name, read_gz(p)))
    streams = path / "streams"
    if streams.is_dir():
        for name in V3_STREAM_DIRS:
            stream_dir = streams / name
            if not stream_dir.is_dir():
                continue
            for p in sorted(stream_dir.iterdir()):
                if not p.is_file() or p.suffix not in (".jsonl", ".log", ".gz"):
                    continue
                text = read_gz(p) if p.suffix == ".gz" else read_text(p)
                if "\x00" in text:
                    continue
                source = "streams/%s/%s" % (name, p.name)
                if p.suffix == ".jsonl":
                    yield from emit(_parse_jsonl(source, text))
                else:
                    yield from emit(_parse_text(source, text))


def resolve_boot(value, logs_dir):
    path = Path(value)
    if path.is_dir():
        return path
    if logs_dir:
        candidate = Path(logs_dir) / value
        if candidate.is_dir():
            return candidate
        hits = [p for p in Path(logs_dir).iterdir() if p.is_dir() and p.name.startswith("boot-") and value in p.name]
        if len(hits) == 1:
            return hits[0]
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Classify a FroodzOS boot-log folder against the local signature catalog.")
    ap.add_argument("boot", help="boot folder, or a prefix under --logs-dir")
    ap.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    ap.add_argument("--logs-dir", default=os.environ.get("FZ_LOGS_DIR"))
    ap.add_argument("--top", type=int, default=30, help="maximum unknown clusters to list")
    ap.add_argument("--learn", action="store_true", help="print UNKNOWN clusters with a draft regex")
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    boot = resolve_boot(args.boot, args.logs_dir)
    if boot is None:
        print("fz-sigscan: boot folder not found: %s" % args.boot, file=sys.stderr)
        return 2
    try:
        signatures = load_catalog(args.catalog)
    except (OSError, ValueError, re.error) as exc:
        print("fz-sigscan: bad catalog: %s" % exc, file=sys.stderr)
        return 2

    meta = boot_meta(boot)
    counts = {s["id"]: 0 for s in signatures}
    by_issue = {}
    unknown = {}
    total = 0
    matched = 0
    sources = {"kernel": 0, "userspace": 0}
    for source, msg, program in iter_lines(boot):
        total += 1
        sources["kernel" if source in ("01-kernel-kmsg.log", "early-kmsg.log") or "/kernel/" in source else "userspace"] += 1
        text = light(msg)
        if program:
            text = program + ": " + text
        hit = None
        for signature in signatures:
            if signature["_rx"].match(text):
                hit = signature
                break
        if hit is None:
            key = normalise(msg, program)
            unknown.setdefault(key, {"count": 0, "sources": set()})
            unknown[key]["count"] += 1
            unknown[key]["sources"].add(source)
        else:
            matched += 1
            counts[hit["id"]] += 1
            if hit["class"] == "KNOWN-ISSUE":
                by_issue[hit["issue"]] = by_issue.get(hit["issue"], 0) + 1

    class_lines = {"UNKNOWN/INVESTIGATE": sum(item["count"] for item in unknown.values()),
                   "KNOWN-ISSUE": 0, "BENIGN-NOISE": 0}
    class_sigs = {"UNKNOWN/INVESTIGATE": len(unknown), "KNOWN-ISSUE": 0, "BENIGN-NOISE": 0}
    issue_notes = {}
    for signature in signatures:
        if signature["class"] == "KNOWN-ISSUE":
            issue_notes.setdefault(signature["issue"], signature["note"])
    top_matching = []
    for signature in sorted(signatures, key=lambda s: (-counts[s["id"]], s["id"])):
        if counts[signature["id"]]:
            class_lines[signature["class"]] += counts[signature["id"]]
            class_sigs[signature["class"]] += 1
            top_matching.append({"id": signature["id"], "count": counts[signature["id"]],
                                 "class": signature["class"], "subsystem": signature["subsystem"],
                                 "note": signature["note"]})
    unknown_rows = [{"pattern": key, "count": value["count"],
                     "sources": sorted(value["sources"]),
                     "suggested_regex": suggest_regex(key)}
                    for key, value in sorted(unknown.items(), key=lambda kv: (-kv[1]["count"], kv[0]))][: args.top]
    payload = {
        "schema": "fz-sigscan/1",
        "boot": meta,
        "catalog": {"path": str(Path(args.catalog).resolve()), "signatures": len(signatures)},
        "lines": total,
        "sources": sources,
        "matched": matched,
        "coverage_percent": round(100.0 * matched / total, 1) if total else 0.0,
        "class_lines": class_lines,
        "class_signatures": class_sigs,
        "unknown": unknown_rows,
        "known_issues": [{"issue": key, "count": value}
                         for key, value in sorted(by_issue.items(), key=lambda kv: (-kv[1], kv[0]))],
        "top_matching": top_matching[:12],
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("FroodzOS sigscan")
    print("boot  : %s" % payload["boot"]["boot"])
    print("layout: %s   image: %s   root: %s   kernel: %s"
          % (payload["boot"]["layout"], payload["boot"]["image"], payload["boot"]["root"], payload["boot"]["kernel"]))
    print("lines : %d (kernel %d, userspace %d), matched %d (%.1f%%), catalog %d"
          % (total, sources["kernel"], sources["userspace"], matched, payload["coverage_percent"], len(signatures)))
    print()
    print("UNKNOWN/INVESTIGATE: %d lines in %d clusters (never printed raw)"
          % (class_lines["UNKNOWN/INVESTIGATE"], class_sigs["UNKNOWN/INVESTIGATE"]))
    if unknown_rows:
        for row in unknown_rows:
            print("  %6d  %s" % (row["count"], row["pattern"][:200]))
            if args.learn:
                print("          sources: %s" % ", ".join(row["sources"][:4]))
                print("          draft:   %s" % row["suggested_regex"][:240])
    else:
        print("  (none)")
    if args.learn:
        print()
        print("Add a generic regex to %s and re-run; keep the count and source list out of the catalog." % args.catalog)
    print()
    print("KNOWN-ISSUE: %d lines across %d issues" % (class_lines["KNOWN-ISSUE"], len(by_issue)))
    for row in payload["known_issues"][: args.top]:
        print("  %6d  %-34s %s" % (row["count"], row["issue"], issue_notes.get(row["issue"], "")[:100]))
    print()
    print("BENIGN-NOISE: %d lines in %d signatures (suppressed)"
          % (class_lines["BENIGN-NOISE"], class_sigs["BENIGN-NOISE"]))
    print()
    print("Top matching signatures:")
    shown = 0
    for row in top_matching:
        if shown >= 10:
            break
        print("  %6d  %-7s %-24s %s" % (row["count"], row["class"], row["id"], row["note"][:90]))
        shown += 1
    if not shown:
        print("  (none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
