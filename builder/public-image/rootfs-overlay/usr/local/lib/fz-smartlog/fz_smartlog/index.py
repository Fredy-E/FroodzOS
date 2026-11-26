# SPDX-License-Identifier: GPL-2.0-or-later
"""index.json / index.partial.json (schema 3, W4 sec.18)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

from .writer import parse_jsonl

SCHEMA = 3
SNAP_RE = re.compile(r"^snap-(\d{3})-up(\d+)\.txt$")
EVENT_TXT_RE = re.compile(r"^event-(.+)-up(\d+)\.txt$")
STREAM_FILE_RE = re.compile(r"^\d{6,}\.jsonl$")


def _iso(wall=None):
    wall = time.time() if wall is None else wall
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(wall))


def atomic_write(path, data):
    path = os.path.abspath(path)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp.%d" % os.getpid()
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        fsync = getattr(os, "fdatasync", None) or getattr(os, "fsync", None)
        if fsync:
            try:
                fsync(fh.fileno())
            except OSError:
                pass
    os.replace(tmp, path)
    _fsync_dir(directory)


def atomic_write_json(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n").encode(
        "utf-8", "replace")
    atomic_write(path, data)


def _fsync_dir(directory):
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        fsync = getattr(os, "fsync", None)
        if fsync:
            fsync(fd)
    except OSError:
        pass
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def sha256_file(path):
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _file_hash(path, cache):
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = ("hash", path, st.st_size, st.st_mtime_ns)
    if key in cache:
        return cache[key]
    value = sha256_file(path)
    cache[key] = value
    return value


def _read_head_tail(path, limit=65536):
    try:
        size = os.stat(path).st_size
        with open(path, "rb") as fh:
            head = fh.read(limit)
            if size > limit:
                fh.seek(max(0, size - limit))
                tail = fh.read(limit)
            else:
                tail = head
    except OSError:
        return b"", b""
    return head, tail


def _mono_of(record):
    value = record.get("mono")
    if isinstance(value, (int, float)):
        return float(value)
    ts = record.get("t")
    if isinstance(ts, (int, float)):
        return float(ts)
    return None


def inspect_segment(path, cache, active=False):
    try:
        st = os.stat(path)
    except OSError:
        return {"file": path, "bytes": 0, "complete": not active}
    key = ("segment", path, st.st_size, st.st_mtime_ns)
    if key in cache and not active:
        return dict(cache[key])
    head, tail = _read_head_tail(path)
    first_mono = last_mono = None
    records, _bad, _trailing = parse_jsonl(head)
    data_records = [r for r in records if "_fz" not in r and _mono_of(r) is not None]
    if data_records:
        first_mono = _mono_of(data_records[0])
    records, _bad, _trailing = parse_jsonl(tail)
    data_records = [r for r in records if "_fz" not in r and _mono_of(r) is not None]
    if data_records:
        last_mono = _mono_of(data_records[-1])
    count = None
    if not active or st.st_size <= (4 << 20):
        try:
            count = 0
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    count += chunk.count(b"\n")
        except OSError:
            count = None
    info = {
        "bytes": st.st_size,
        "first_mono": first_mono,
        "last_mono": last_mono,
        "records": count,
        "complete": not active,
    }
    cache[key] = dict(info)
    return info


def scan_streams(streams_dir, active_paths=(), cache=None):
    cache = cache if cache is not None else {}
    active = {os.path.abspath(p) for p in active_paths}
    result = {}
    try:
        names = sorted(os.listdir(streams_dir))
    except OSError:
        return result
    for stream in names:
        stream_dir = os.path.join(streams_dir, stream)
        if not os.path.isdir(stream_dir):
            continue
        files = []
        try:
            entries = sorted(n for n in os.listdir(stream_dir) if STREAM_FILE_RE.match(n))
        except OSError:
            entries = []
        total = 0
        segments = []
        for name in entries:
            path = os.path.join(stream_dir, name)
            is_active = os.path.abspath(path) in active
            info = inspect_segment(path, cache, active=is_active)
            total += int(info.get("bytes") or 0)
            segment = {
                "file": "streams/%s/%s" % (stream, name),
                "bytes": int(info.get("bytes") or 0),
                "first_mono": info.get("first_mono"),
                "last_mono": info.get("last_mono"),
                "records": info.get("records"),
                "complete": not is_active,
            }
            if segment["complete"]:
                digest = _file_hash(path, cache)
                if digest:
                    segment["sha256"] = digest
            segments.append(segment)
        result[stream] = {"total_bytes": total, "segments": segments, "gaps": []}
    return result


def scan_snapshots(smart_dir):
    out = []
    try:
        names = sorted(os.listdir(smart_dir))
    except OSError:
        return out
    for name in names:
        path = os.path.join(smart_dir, name)
        if not os.path.isfile(path):
            continue
        match = SNAP_RE.match(name)
        if match:
            seq, uptime, partial = int(match.group(1)), int(match.group(2)), False
            kind = "snapshot"
        else:
            match = EVENT_TXT_RE.match(name)
            if not match:
                continue
            seq, uptime, partial = None, int(match.group(2)), False
            kind = "event"
        try:
            with open(path, "rb") as fh:
                head = fh.read(2 << 20).decode("utf-8", "replace")
            partial = ("TRUNCATED" in head) or ("SNAPSHOT_PARTIAL" in head)
        except OSError:
            head = ""
        out.append({
            "file": "smart/%s" % name,
            "kind": kind,
            "seq": seq,
            "uptime": uptime,
            "bytes": os.path.getsize(path),
            "partial": partial,
        })
    return out


def scan_event_dirs(events_dir):
    out = []
    try:
        names = sorted(os.listdir(events_dir))
    except OSError:
        return out
    for name in names:
        path = os.path.join(events_dir, name)
        meta = os.path.join(path, "event.json")
        if not os.path.isdir(path) or not os.path.isfile(meta):
            continue
        try:
            with open(meta, "r", encoding="utf-8", errors="replace") as fh:
                event = json.load(fh)
        except (OSError, ValueError):
            event = {}
        out.append({
            "utc": event.get("utc"),
            "mono": event.get("mono"),
            "reason": event.get("reason") or name.split("-", 1)[-1],
            "severity": event.get("severity"),
            "dir": "events/%s" % name,
        })
    return out


def scan_files(boot_dir, cache=None):
    cache = cache if cache is not None else {}
    out = []
    for root, dirs, files in os.walk(boot_dir):
        dirs[:] = [d for d in dirs if d not in ("streams",)]
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, boot_dir).replace(os.sep, "/")
            if rel in ("index.json", "index.partial.json") or rel.endswith(".tmp"):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            kind = "file"
            if rel.startswith("smart/snap-"):
                kind = "snapshot"
            elif rel.startswith("smart/event-"):
                kind = "event"
            elif rel.endswith("summary.txt"):
                kind = "summary"
            elif rel.endswith("summary.json"):
                kind = "summary-json"
            elif rel.endswith("history.tsv"):
                kind = "history"
            elif rel.endswith("alive.txt"):
                kind = "alive"
            out.append({
                "path": rel,
                "kind": kind,
                "bytes": size,
                "sha256": _file_hash(path, cache) if size <= (32 << 20) else None,
            })
    return out


def read_boot_json(boot_dir):
    try:
        with open(os.path.join(boot_dir, "boot.json"), "r", encoding="utf-8",
                  errors="replace") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def read_summary_json(boot_dir):
    try:
        with open(os.path.join(boot_dir, "summary.json"), "r", encoding="utf-8",
                  errors="replace") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def build_index(boot_dir, boot_id=None, started_utc=None, complete=False,
                dest_kind=None, dest_path=None, destinations=None, gaps=None,
                active_paths=(), outcome="unknown", cmdline=None, build_id=None,
                kernel=None, summary=None, pruned=None, cache=None, now=None,
                ended_utc=None):
    cache = cache if cache is not None else {}
    boot = read_boot_json(boot_dir)
    boot_id = boot_id or boot.get("boot_id") or "unknown"
    started_utc = started_utc or boot.get("started_utc") or _iso()
    started_epoch = boot.get("started_epoch")
    now = time.time() if now is None else now
    duration = int(max(0, now - float(started_epoch))) if started_epoch else None
    streams = scan_streams(os.path.join(boot_dir, "streams"), active_paths, cache)
    if gaps:
        for stream, stream_gaps in gaps.items():
            streams.setdefault(stream, {"total_bytes": 0, "segments": [],
                                        "gaps": []})
            streams[stream]["gaps"] = list(stream_gaps)
    index = {
        "schema": SCHEMA,
        "complete": bool(complete),
        "boot_id": boot_id,
        "started_utc": started_utc,
        "ended_utc": ended_utc or _iso(now),
        "duration_s": duration,
        "outcome": outcome,
        "build_id": build_id or boot.get("build_id") or "unknown",
        "kernel": kernel or boot.get("kernel") or "unknown",
        "cmdline": list(cmdline if cmdline is not None else boot.get("cmdline", [])),
        "destinations": list(destinations or []),
        "dest_kind": dest_kind or boot.get("dest_kind"),
        "dest_path": dest_path or boot.get("dest_path"),
        "streams": streams,
        "snapshots": scan_snapshots(os.path.join(boot_dir, "smart")),
        "events": scan_event_dirs(os.path.join(boot_dir, "events")),
        "summary": summary if summary is not None else read_summary_json(boot_dir),
        "files": scan_files(boot_dir, cache),
        "pruned": list(pruned or []),
    }
    return index


def write_index(boot_dir, index, partial=False):
    name = "index.partial.json" if partial else "index.json"
    atomic_write_json(os.path.join(boot_dir, name), index)
    return os.path.join(boot_dir, name)
