#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Render one fz-term-record session from tmpfs to a redacted transcript and JSONL.

Usage: render.py SESSION_DIR [OUT_DIR] [--keep-raw]

The raw util-linux `script` typescript is output-only. Command rows written by the
shell hook are merged by an invisible OSC marker (6973) that carries only a
sequence number, the exit status and the end time. Every record is redacted with
fz_smartlog.redact when the shared core is installed, else with the bundled
fz_term_redact fallback. Raw and timing files are removed after a good render.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
for candidate in ("/usr/local/lib/fz-smartlog", "/usr/local/lib"):
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

DEFAULT_TEXT_BYTES = 8 << 20
DEFAULT_STREAM_BYTES = 32 << 20
DEFAULT_SEGMENT_BYTES = 8 << 20
HEAD_TAIL_LINES = 5
HEAD_TAIL_CHARS = 1024

MARK_RE = re.compile(r"\x1b\]6973;FZ;E;(\d+);(-?\d+);([0-9][0-9.,]*)\x07")
SCRIPT_START_RE = re.compile(r"\AScript started on [^\n]*\n")
SCRIPT_DONE_RE = re.compile(r"\nScript done on [^\n]*\n?\Z")
OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
DCS_RE = re.compile(r"\x1b[P^_].*?\x1b\\", re.S)
CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ESC_RE = re.compile(r"\x1b[@-_]")


def _redactor():
    module = None
    try:
        from fz_smartlog import redact as module  # type: ignore
    except Exception:
        try:
            import fz_term_redact as module  # type: ignore
        except Exception:
            return lambda text: text
    if hasattr(module, "Redactor"):
        key = os.environ.get("FZ_REDACT_KEY", "").strip()
        try:
            keyb = bytes.fromhex(key) if key else b"fz-term-record-no-key"
        except ValueError:
            keyb = key.encode("utf-8", "surrogateescape") or b"fz-term-record-no-key"

        def _run(text: str) -> str:
            try:
                instance = module.Redactor(keyb, redact_private_ips=False)
            except TypeError:
                instance = module.Redactor(keyb)
            return instance.text(text)

        return _run
    if hasattr(module, "redact"):
        return module.redact
    return lambda text: text


def strip_ansi(text: str) -> str:
    text = OSC_RE.sub("", text)
    text = DCS_RE.sub("", text)
    text = CSI_RE.sub("", text)
    text = ESC_RE.sub("", text)
    return text


def resolve_text(raw: str) -> str:
    text = strip_ansi(raw).replace("\r\n", "\n")
    lines = []
    for line in text.split("\n"):
        if "\r" in line:
            line = line.split("\r")[-1]
        out = []
        for ch in line:
            if ch == "\b":
                if out:
                    out.pop()
            elif ch == "\t":
                out.append(" " * (8 - (len(out) % 8)))
            elif ord(ch) < 32:
                continue
            else:
                out.append(ch)
        lines.append("".join(out))
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def truncate_utf8(text: str, limit: int) -> tuple[str, bool]:
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text, False
    data = data[:limit]
    cut = data.rfind(b"\n")
    if cut > 0:
        data = data[:cut]
    try:
        out = data.decode("utf-8")
    except UnicodeDecodeError:
        out = data.decode("utf-8", "ignore")
    return out + "\n[truncated]\n", True


def parse_epoch(value: str) -> float | None:
    if not value:
        return None
    value = value.strip().replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def iso_to_epoch(value: str) -> float | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).timestamp()
        except (TypeError, ValueError):
            pass
    return None


def mono_for(epoch: float) -> float:
    try:
        uptime = float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
    except Exception:
        return 0.0
    return round(max(0.0, uptime - (time.time() - epoch)), 3)


def strip_script_frame(raw: str) -> str:
    raw = SCRIPT_START_RE.sub("", raw, count=1)
    raw = SCRIPT_DONE_RE.sub("\n", raw, count=1)
    return raw


def read_timing(session_dir: Path) -> list[tuple[float, int]]:
    events: list[tuple[float, int]] = []
    try:
        text = (session_dir / "session.timing").read_text(encoding="ascii", errors="replace")
    except OSError:
        return events
    total = 0.0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            delay = float(parts[0].replace(",", "."))
            size = int(parts[1])
        except ValueError:
            continue
        total += max(0.0, delay)
        events.append((total, size))
    return events


def timing_offset(events: list[tuple[float, int]], offset: int) -> float:
    position = 0
    for stamp, size in events:
        position += size
        if offset <= position:
            return stamp
    return events[-1][0] if events else 0.0


def read_meta(session_dir: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        for line in (session_dir / "meta").read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                meta[key.strip()] = value.strip()
    except OSError:
        pass
    return meta


def read_rows(session_dir: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    try:
        text = (session_dir / "commands.raw.tsv").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            seq = int(parts[0])
            exit_code = int(parts[3])
        except ValueError:
            continue
        rows[seq] = {
            "start": parse_epoch(parts[1]),
            "end": parse_epoch(parts[2]),
            "exit": exit_code,
            "cwd": parts[4],
            "cmd": "\t".join(parts[5:]),
        }
    return rows


def find_markers(raw: str) -> dict[int, dict]:
    markers: dict[int, dict] = {}
    previous_end = 0
    for match in MARK_RE.finditer(raw):
        seq = int(match.group(1))
        markers[seq] = {
            "start": previous_end,
            "end": match.start(),
            "end_time": parse_epoch(match.group(3)),
            "exit": int(match.group(2)),
        }
        previous_end = match.end()
    return markers


def field_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.split("\n")]
    return [line for line in lines if line]


def head_tail(lines: list[str]) -> tuple[str, str]:
    head = "\n".join(lines[:HEAD_TAIL_LINES])
    tail = "\n".join(lines[-HEAD_TAIL_LINES:])
    if len(head) > HEAD_TAIL_CHARS:
        head = head[:HEAD_TAIL_CHARS] + "..."
    if len(tail) > HEAD_TAIL_CHARS:
        tail = "..." + tail[-HEAD_TAIL_CHARS:]
    return head, tail


class ShimWriter:
    """Fallback for tests and for an image without the fz_smartlog core."""

    def __init__(self, stream: str, fallback_dir: Path):
        log_dir = os.environ.get("FZ_LOG_DIR", "").strip()
        target = (Path(log_dir) / stream) if log_dir else fallback_dir
        target.mkdir(parents=True, exist_ok=True)
        self._fh = open(target / "000001.jsonl", "a", encoding="utf-8", newline="\n")

    def write(self, record: dict) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def flush(self) -> None:
        self._fh.flush()
        try:
            os.fsync(self._fh.fileno())
        except OSError:
            pass

    def close(self) -> None:
        try:
            self.write({"_fz": "stream_closed", "reason": "session_end"})
            self.flush()
        finally:
            self._fh.close()


def load_log_env() -> None:
    """Adopt the smartlog environment contract when the caller (a user shell) did not inherit it.

    fz-smartlog writes /run/fz-smartlog/env (KEY='value' lines) for plug-in writers; a Konsole or tty
    shell never has FZ_LOG_DIR in its own environment, so without this the terminal stream would
    silently go to the fallback directory instead of the boot folder on the stick."""
    if os.environ.get("FZ_LOG_DIR"):
        return
    path = os.environ.get("FZ_RENDER_ENV_FILE", "/run/fz-smartlog/env")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                key, sep, value = line.strip().partition("=")
                if not sep or not key.startswith("FZ_LOG_"):
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    except OSError:
        pass


def open_writer(session: str, fallback_dir: Path):
    load_log_env()
    max_bytes = int(os.environ.get("FZ_LOG_MAX_STREAM_BYTES", DEFAULT_STREAM_BYTES))
    segment_bytes = int(os.environ.get("FZ_LOG_SEGMENT_BYTES", DEFAULT_SEGMENT_BYTES))
    try:
        from fz_smartlog.writer import StreamWriter  # type: ignore
        try:
            return StreamWriter("terminal", max_bytes=max_bytes, segment_bytes=segment_bytes)
        except TypeError:
            return StreamWriter("terminal")
    except Exception:
        return ShimWriter("terminal", fallback_dir)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:120] or "session"


def build(session_dir: Path, out_dir: Path, keep_raw: bool = False) -> int:
    meta = read_meta(session_dir)
    session = safe_name(meta.get("session") or session_dir.name)
    raw_path = session_dir / "session.raw"
    try:
        raw = raw_path.read_bytes().decode("utf-8", "replace")
    except OSError:
        raw = ""
    raw = strip_script_frame(raw)
    redact = _redactor()
    rows = read_rows(session_dir)
    markers = find_markers(raw)
    timing = read_timing(session_dir)
    fallback_epoch = iso_to_epoch(meta.get("start_utc", ""))
    if fallback_epoch is None:
        try:
            fallback_epoch = raw_path.stat().st_mtime
        except OSError:
            fallback_epoch = time.time()

    seqs = sorted(set(rows) | set(markers))
    records: list[dict] = []
    sections: list[str] = []
    for seq in seqs:
        row = rows.get(seq, {})
        marker = markers.get(seq, {})
        segment = raw[marker["start"]:marker["end"]] if marker else ""
        text = resolve_text(segment)
        redacted_text = redact(text)
        cmd = redact(row.get("cmd", ""))
        cwd = redact(row.get("cwd", ""))
        rc = row.get("exit", marker.get("exit"))
        start = row.get("start")
        end = row.get("end") or marker.get("end_time")
        if timing and marker:
            base = fallback_epoch or 0.0
            start_byte = len(raw[:marker["start"]].encode("utf-8", "replace"))
            end_byte = len(raw[:marker["end"]].encode("utf-8", "replace"))
            if start is None:
                start = base + timing_offset(timing, start_byte)
            if end is None:
                end = base + timing_offset(timing, end_byte)
        if end is None:
            end = fallback_epoch
        dur_ms = int(round((end - start) * 1000)) if (start is not None and end is not None) else 0
        lines = field_lines(redacted_text)
        head, tail = head_tail(lines)
        record = {
            "schema": 3,
            "ts": iso_utc(end),
            "mono": mono_for(end),
            "session": session,
            "tty": meta.get("tty", ""),
            "user": redact(meta.get("user", "")),
            "seq": seq,
            "cwd": cwd,
            "cmd": cmd,
            "exit": rc,
            "dur_ms": max(0, dur_ms),
            "out_head": head,
            "out_tail": tail,
            "out_lines": len(lines),
            "out_bytes": len(text.encode("utf-8")),
        }
        records.append(record)
        title = "### %s cwd=%s exit=%s dur=%dms seq=%d" % (
            record["ts"], cwd or meta.get("cwd", ""), rc, record["dur_ms"], seq)
        body = redacted_text if redacted_text.strip() else ("$ " + cmd if cmd else "")
        sections.append(title + "\n" + body + "\n")

    header = [
        "# FroodzOS terminal session %s" % session,
        "# user=%s uid=%s tty=%s term=%s shell=%s" % (
            redact(meta.get("user", "")), meta.get("uid", ""), meta.get("tty", ""),
            meta.get("term", ""), meta.get("shell", "")),
        "# boot=%s start=%s mode=%s" % (
            meta.get("boot_id", ""), meta.get("start_utc", ""), meta.get("mode", "")),
    ]
    if not sections:
        full = resolve_text(raw)
        sections = ["### untracked session\n" + redact(full) + "\n"]
    limit = int(os.environ.get("FZ_TERM_TEXT_BYTES", DEFAULT_TEXT_BYTES))
    transcript, truncated = truncate_utf8("\n".join(header) + "\n\n" + "\n".join(sections), limit)
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_name = "transcript-%s.txt" % session
    (out_dir / transcript_name).write_text(transcript, encoding="utf-8", newline="\n")

    try:
        with open(out_dir / "commands.tsv", "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                fields = [
                    record["ts"], str(record["dur_ms"]), record["cwd"], str(record["exit"]),
                    record["cmd"], str(record["out_lines"]), record["out_head"], record["out_tail"],
                ]
                handle.write("\t".join(f.replace("\t", " ").replace("\n", "\\n") for f in fields) + "\n")
    except OSError:
        pass

    writer = open_writer(session, out_dir / "terminal")
    try:
        for record in records:
            writer.write(record)
        writer.flush()
    finally:
        writer.close()

    if not keep_raw and not os.environ.get("FZ_TERM_KEEP_RAW"):
        for name in ("session.raw", "session.timing", "commands.raw.tsv"):
            try:
                (session_dir / name).unlink()
            except OSError:
                pass
    return 1 if truncated else 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--keep-raw"]
    keep_raw = "--keep-raw" in argv[1:]
    if not args:
        print("usage: render.py SESSION_DIR [OUT_DIR] [--keep-raw]", file=sys.stderr)
        return 2
    session_dir = Path(args[0])
    out_dir = Path(args[1]) if len(args) > 1 else session_dir
    if not session_dir.is_dir():
        print("render.py: %s is not a directory" % session_dir, file=sys.stderr)
        return 2
    try:
        return build(session_dir, out_dir, keep_raw)
    except Exception as exc:
        print("render.py: render failed: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
