#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read a FroodzOS boot-log folder and print a short, safe digest.

Usage:
    fz-digest.py <Logs/boot-folder> [--prev <folder>] [--json] [--lines N]

Read-only and standard library only. It understands both layouts:

* v2: ``smart/`` (or the older root layout) with ``summary.txt``,
  ``history.tsv``, ``events.log``, ``snap-*.txt``, ``01-kernel-kmsg.log``,
  ``03-userspace-journal.log`` and the gzip exports.
* v3: ``index.json`` / ``index.partial.json``, ``summary.json``, ``boot.json``,
  ``streams/<name>/NNNNNN.jsonl|log`` and ``events/<stamp>-<reason>/``.

All log text is untrusted data. The tool escapes control characters, quotes
every excerpt and flags prompt-injection-like lines; it never prints a log line
as if it were an instruction. ``--json`` emits the same model.

Exit status: 0 on a readable folder, 2 when the folder is missing.
"""
import argparse
import datetime as _dt
import gzip
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "fz-digest/1"
MAX_TEXT = 240
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")

KMSG_RE = re.compile(r"^(\d+),(\d+),(\d+),([^;]*);(.*)$")
MONO_RE = re.compile(r"^\[\s*(\d+\.\d+)\]\s*(.*)$")
MONO_PROG_RE = re.compile(r"^\[\s*(\d+\.\d+)\]\s+(\S+)\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")
WALL_PROG_RE = re.compile(r"^([A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d(?:\.\d+)?)\s+\S+\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")
ISO_PROG_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[,.]\d+)?(?:Z|[+-]\d\d:?\d\d))\s+\S+\s+([\w\-.@/]+(?:\[\d+\])?):\s?(.*)$")
ISO_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:[,.]\d+)?(?:Z|[+-]\d\d:?\d\d))\s+(.*)$")
WALL_RE = re.compile(r"^([A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d(?:\.\d+)?)\s+(.*)$")

OOPS_RE = re.compile(
    r"(\bOops\b|kernel BUG|BUG:|WARNING:|Call trace|Unable to handle|"
    r"Kernel panic|general protection fault|internal error|soft lockup|hung task)",
    re.I,
)
HARD_FAULT_RE = re.compile(
    r"(\bOops\b|kernel BUG|BUG:|Unable to handle|Kernel panic|"
    r"general protection fault|internal error|soft lockup|hung task|"
    r"Hardware became unavailable upon resume)",
    re.I,
)
WARNING_RE = re.compile(r"\bWARNING:", re.I)
MASK_RES = (
    (re.compile(r"(?i)\b(psk|passphrase|password|passwd|wep-key[0-3]?|private_key_passwd)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|\S+)"), r"\1\2<masked>"),
    (re.compile(r"(?i)\b(ssid)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|\S+)"), r"\1\2<masked>"),
    (re.compile(r"(?i)\b(serial(?:\s*number)?|serialno|s/n|iserial)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|\S+)"), r"\1\2<masked>"),
    (re.compile(r"(?i)\b((?:proxy-)?authorization)\s*:\s*\S+(?:\s+\S+)?"), r"\1: <masked>"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"), "<email>"),
    (re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b"), "<mac>"),
)
STRONG_ERROR_RE = re.compile(
    r"(\b(failed|failure|fatal|panic|oops|bug|error|timeout|timed out|denied|refused)\b|"
    r"\bEACCES\b|\bEIO\b|\bENOSPC\b|\bEROFS\b|\bENODEV\b)",
    re.I,
)
WAYDROID_RE = re.compile(
    r"(waydroid|binder_linux|libprocessgroup|surfaceflinger|android\.hardware|"
    r"init: |vold|apexd|logd|zygote|servicemanager|hwservicemanager|"
    r"Read-only file system)",
    re.I,
)
WIFI_RE = re.compile(
    r"(ath12k|wiphy|ieee80211|cfg80211|wlan|wlp|rfkill|NetworkManager|wpa_supplicant|"
    r"firmware.*ath|PM:.*phy0)",
    re.I,
)
SOUND_RE = re.compile(
    r"(snd[-_ ]|soundwire|ASoC|WSA|audio|pipewire|wireplumber|wcd9|q6apm|lpass)",
    re.I,
)
POWER_RE = re.compile(r"(PM:|suspend|resume|systemd-sleep|logind|power_supply|battery)", re.I)
STORAGE_RE = re.compile(
    r"(EXT4|vfat|FAT-fs|I/O error|blk_update_request|mmc[0-9]|nvme[0-9]|"
    r"No space left|read-only file system)",
    re.I,
)
INJECTION_RES = (
    ("override-instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|all)\b.{0,24}\b(instructions?|prompts?|rules?)\b", re.I)),
    ("role-switch", re.compile(r"\byou are now\b|\bact as (?:the )?(?:system|admin|developer)\b", re.I)),
    ("fake-role-prefix", re.compile(r"^\s*(system|assistant|developer|tool)\s*:", re.I)),
    ("prompt-exfiltration", re.compile(r"\b(reveal|print|show|leak|repeat)\b.{0,32}\b(system prompt|hidden instructions|api key|password|secret)\b", re.I)),
    ("command-execution", re.compile(r"\b(run|execute|eval)\b.{0,48}\b(curl|wget|bash|sh|powershell|python)\b", re.I)),
    ("pipe-to-shell", re.compile(r"\b(curl|wget)\b.{0,100}\|\s*(?:sudo\s+)?(?:ba|z|k)?sh\b", re.I)),
    ("destructive-command", re.compile(r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+/(?:\s|$)", re.I)),
    ("encoded-execution", re.compile(r"\bbase64\s+(?:-d|--decode)\b.{0,48}\|\s*(?:ba|z|k)?sh\b", re.I)),
    ("suppress-reporting", re.compile(r"\bdo not (?:tell|inform|warn|report)\b", re.I)),
    ("chat-template-token", re.compile(r"<\|im_(?:start|end)\|>|\[/?INST\]|<<SYS>>|###\s*instruction", re.I)),
)

SUMMARY_PREFIXES = (
    "BATTERY", "DSP", "DEFERRED", "SOUND", "THERMAL", "MEMORY", "LOAD",
    "BACKLIGHT", "SUSPEND", "WIFI", "SERVICES", "KERNEL", "WAYDROID",
    "FAILED UNITS", "DATA", "BUILD_ID", "VERSION_ID", "DEST", "DEGRADED",
)
UNIT_RE = re.compile(r"[A-Za-z0-9@_.:\\-]+\.(?:service|socket|timer|target|mount|path|slice|scope|device|swap)")
UNIT_SUFFIXES = ("service", "socket", "timer", "target", "mount", "path", "slice", "scope", "device", "swap")


def clean_text(value):
    text = str(value)
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub(lambda m: "\\x%02x" % ord(m.group(0)), text)
    text = BIDI_RE.sub(lambda m: "\\u%04x" % ord(m.group(0)), text)
    return text


def quote(value, width=MAX_TEXT):
    """Return log text as a single escaped, quoted data string."""
    text = clean_text(value)
    for rx, replacement in MASK_RES:
        text = rx.sub(replacement, text)
    text = " ".join(text.split())
    if len(text) > width:
        text = text[: width - 3] + "..."
    return '"' + text.replace('"', '\\"') + '"'


def fmt_ts(seconds):
    if seconds is None:
        return "?"
    try:
        seconds = max(0.0, float(seconds))
    except (TypeError, ValueError):
        return "?"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, s) if h else "%02d:%02d" % (m, s)


def read_text(path, limit=None):
    try:
        with path.open("rb") as fh:
            data = fh.read(-1 if limit is None else limit)
        return data.decode("utf-8", "replace")
    except OSError:
        return ""


def read_gz(path, limit=None):
    try:
        with gzip.open(path, "rb") as fh:
            data = fh.read(-1 if limit is None else limit)
        return data.decode("utf-8", "replace")
    except (OSError, EOFError):
        return ""


def read_maybe_gz(path, limit=None):
    return read_gz(path, limit) if path.suffix == ".gz" else read_text(path, limit)


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Entry:
    src: str
    msg: str
    ts: float = None
    wall: str = None
    prio: int = None
    seq: int = None
    order: int = 0
    stream: str = ""
    program: str = ""

    @property
    def subsystem(self):
        stream = self.stream.lower()
        if stream == "waydroid":
            return "waydroid"
        if stream == "network":
            return "wifi"
        if stream == "power":
            return "power"
        m = self.msg
        if WAYDROID_RE.search(m):
            return "waydroid"
        if WIFI_RE.search(m):
            return "wifi"
        if POWER_RE.search(m):
            return "power"
        if SOUND_RE.search(m):
            return "sound"
        if STORAGE_RE.search(m):
            return "storage"
        if OOPS_RE.search(m):
            return "kernel"
        return "other"

    def error(self):
        if self.prio is not None:
            return self.prio <= 3
        return bool(STRONG_ERROR_RE.search(self.msg))

    def warning(self):
        return self.prio == 4 or bool(WARNING_RE.search(self.msg))


@dataclass
class Boot:
    path: Path
    boot_id: str = "?"
    layout: str = "unknown"
    entries: list = field(default_factory=list)
    kernel: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    summary_lines: list = field(default_factory=list)
    history: list = field(default_factory=list)
    events: list = field(default_factory=list)
    status: dict = field(default_factory=dict)
    boot_meta: dict = field(default_factory=dict)
    index: dict = field(default_factory=dict)
    summary_json: dict = field(default_factory=dict)
    snapshots: list = field(default_factory=list)
    terminal: list = field(default_factory=list)
    stream_info: dict = field(default_factory=dict)
    destinations: list = field(default_factory=list)
    writer_markers: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    duration_s: float = None
    start_utc: str = None
    end_utc: str = None
    previous: "Boot" = None

    def find(self, *names):
        for name in names:
            for base in (self.path / "smart", self.path):
                p = base / name
                if p.is_file():
                    return p
            hits = sorted(self.path.rglob(name))
            if hits:
                return hits[0]
        return None

    def load(self):
        self.boot_id = self.path.name[5:] if self.path.name.startswith("boot-") else self.path.name
        self._load_meta()
        self._load_summary()
        self._load_history()
        self._load_events()
        self._load_kmsg()
        self._load_journal_like()
        self._load_snapshots()
        self._load_v3_streams()
        self._load_writer_markers()
        self._detect_layout()
        self._compute_times()
        self._compute_gaps()

    def _load_meta(self):
        status = read_text(self.find("00-status.txt") or Path("/nonexistent"))
        for line in status.splitlines():
            key, sep, val = line.partition("=")
            if sep and key.strip():
                self.status[key.strip()] = val.strip()
        if self.status.get("boot_id"):
            self.boot_id = self.status["boot_id"]

        boot_json = self.find("boot.json")
        if boot_json:
            try:
                obj = json.loads(read_text(boot_json))
                if isinstance(obj, dict):
                    self.boot_meta = obj
            except (ValueError, TypeError):
                self.boot_meta = {}
        if self.boot_meta.get("boot_id"):
            self.boot_id = str(self.boot_meta["boot_id"])

        index_path = self.find("index.json") or self.find("index.partial.json")
        if index_path:
            try:
                obj = json.loads(read_text(index_path))
            except (ValueError, TypeError):
                obj = {}
            if isinstance(obj, dict):
                self.index = obj
        if self.index.get("boot_id"):
            self.boot_id = str(self.index["boot_id"])

        sj = self.find("summary.json")
        if sj:
            try:
                obj = json.loads(read_text(sj))
                if isinstance(obj, dict):
                    self.summary_json = obj
            except (ValueError, TypeError):
                self.summary_json = {}

    def _load_summary(self):
        p = self.find("summary.txt")
        if p:
            text = read_text(p)
            self.summary_lines = [ln for ln in text.splitlines() if ln.strip()]
            for line in self.summary_lines:
                m = re.match(r"^([A-Z][A-Z ]+):\s*(.*)$", line)
                if m:
                    self.summary[m.group(1).strip()] = m.group(2).strip()
                    continue
                if line.startswith(SUMMARY_PREFIXES) and ":" in line:
                    key, _, val = line.partition(":")
                    self.summary[key.strip()] = val.strip()
            m = re.search(r"boot=(\S+).*uptime=(\d+)s.*written=(\S+)", text)
            if m:
                self.summary["boot_id"] = m.group(1)
                self.summary["uptime_s"] = m.group(2)
                self.summary["written"] = m.group(3)
            m = re.search(r"\bwhere=(\S+)", text)
            if m:
                self.summary["WHERE"] = m.group(1)
        merged = dict(self.summary_json)
        if isinstance(self.index.get("summary"), dict):
            for key, value in self.index["summary"].items():
                merged.setdefault(str(key), value)
        for key in ("failed_units", "suspend", "wifi", "sound", "kernel", "waydroid",
                    "dest", "destination", "degraded", "outcome", "build_id", "kernel_release"):
            if key in merged and key not in self.summary:
                value = merged[key]
                self.summary[key] = value if isinstance(value, (dict, list)) else str(value)

    def _load_history(self):
        p = self.find("history.tsv")
        if not p:
            return
        lines = read_text(p).splitlines()
        if len(lines) < 2:
            return
        header = lines[0].split("\t")
        for line in lines[1:]:
            cells = line.split("\t")
            if len(cells) >= 2:
                self.history.append(dict(zip(header, cells)))

    def _load_events(self):
        p = self.find("events.log")
        if p:
            for line in read_text(p).splitlines():
                m = re.match(r"^(\d\d:\d\d:\d\d)\s+up=(\d+)\s+(.*)$", line)
                if m:
                    text = re.sub(r"^event:\s*", "", m.group(3))
                    self.events.append({"wall": m.group(1), "up": float(m.group(2)),
                                        "text": text, "source": "events.log"})
                elif line.strip():
                    self.events.append({"wall": None, "up": None, "text": line.strip(),
                                        "source": "events.log"})
        for ev in (self.index.get("events") or []):
            if not isinstance(ev, dict):
                continue
            text = ev.get("text") or ev.get("reason") or ev.get("name") or "event"
            self.events.append({"wall": str(ev.get("utc") or ev.get("wall") or ""),
                                "up": as_float(ev.get("mono")), "text": str(text),
                                "source": "index.json"})
        events_dir = self.path / "events"
        if events_dir.is_dir():
            for ev_dir in sorted(events_dir.iterdir()):
                if not ev_dir.is_dir():
                    continue
                obj = {}
                p = ev_dir / "event.json"
                if p.is_file():
                    try:
                        obj = json.loads(read_text(p))
                    except (ValueError, TypeError):
                        obj = {}
                if not isinstance(obj, dict):
                    obj = {}
                reason = str(obj.get("reason") or ev_dir.name.split("-", 1)[-1] or "event")
                text = reason
                for key in ("detail", "summary", "message"):
                    if obj.get(key):
                        text = "%s: %s" % (reason, obj[key])
                        break
                self.events.append({"wall": str(obj.get("utc") or ""),
                                    "up": as_float(obj.get("mono")), "text": text,
                                    "source": "events/" + ev_dir.name})
        self.events.sort(key=lambda e: (e["up"] is None, e["up"] or 0, e["text"]))

    def _load_kmsg(self):
        p = self.find("01-kernel-kmsg.log")
        if not p:
            return
        last = None
        order = 0
        for raw in read_text(p).splitlines():
            m = KMSG_RE.match(raw)
            if m:
                prio, seq, usec, _flags, msg = m.groups()
                last = Entry("kmsg", msg, ts=float(usec) / 1_000_000.0,
                             prio=as_int(prio), seq=as_int(seq), order=order, stream="kernel")
                if last.msg.strip():
                    self.kernel.append(last)
                    self.entries.append(last)
                order += 1
            elif last is not None:
                last.msg += "\n" + raw
        self.entries[:] = [e for e in self.entries if e.msg.strip()]
        self.kernel[:] = [e for e in self.kernel if e.msg.strip()]

    def _load_journal_like(self):
        order = len(self.entries)
        for name, src in (
            ("kernel-warnings.log", "warnings"),
            ("journal-errors.log", "errors"),
            ("03-userspace-journal.log", "journal"),
        ):
            p = self.find(name)
            if not p:
                continue
            for raw in read_text(p).splitlines():
                if not raw.strip():
                    continue
                e = self._parse_journal_line(raw, src, order)
                if e:
                    self.entries.append(e)
                    order += 1
        for p in sorted(self.path.rglob("journal-*.log.gz")):
            for raw in read_gz(p).splitlines():
                if not raw.strip():
                    continue
                e = self._parse_journal_line(raw, p.name, order)
                if e:
                    self.entries.append(e)
                    order += 1

    @staticmethod
    def _parse_journal_line(raw, src, order):
        m = MONO_PROG_RE.match(raw)
        if m:
            return Entry(src, m.group(4), ts=float(m.group(1)), program=m.group(3),
                         order=order, stream="journal")
        m = MONO_RE.match(raw)
        if m:
            return Entry(src, m.group(2), ts=float(m.group(1)), order=order, stream="journal")
        m = ISO_PROG_RE.match(raw)
        if m:
            return Entry(src, m.group(3), wall=m.group(1), program=m.group(2),
                         order=order, stream="journal")
        m = WALL_PROG_RE.match(raw)
        if m:
            return Entry(src, m.group(3), wall=m.group(1), program=m.group(2),
                         order=order, stream="journal")
        m = ISO_RE.match(raw)
        if m:
            return Entry(src, m.group(2), wall=m.group(1), order=order, stream="journal")
        m = WALL_RE.match(raw)
        if m:
            return Entry(src, m.group(2), wall=m.group(1), order=order, stream="journal")
        if "kernel:" in raw or "systemd" in raw or raw.startswith("["):
            return Entry(src, raw, order=order, stream="journal")
        return None

    def _load_snapshots(self):
        for p in sorted(self.path.rglob("snap-*.txt")) + sorted(self.path.rglob("event-*.txt")):
            if "streams" in p.parts:
                continue
            text = read_text(p)
            if not text:
                continue
            first = text.splitlines()[0] if text.splitlines() else ""
            m = re.search(r"seq=(\S+)\s+uptime_s=(\d+).*where=(\S+)", first)
            self.snapshots.append({
                "name": p.name,
                "seq": m.group(1) if m else "?",
                "uptime": float(m.group(2)) if m else None,
                "where": m.group(3) if m else "?",
                "text": text,
                "bytes": p.stat().st_size,
            })
        self.snapshots.sort(key=lambda r: (r["uptime"] is None, r["uptime"] or 0, r["name"]))

    def _load_v3_streams(self):
        streams_dir = self.path / "streams"
        if not streams_dir.is_dir():
            return
        order = len(self.entries)
        for stream_dir in sorted(streams_dir.iterdir()):
            if not stream_dir.is_dir():
                continue
            name = stream_dir.name
            files = sorted(p for p in stream_dir.iterdir() if p.is_file() and p.suffix in (".jsonl", ".log", ".gz"))
            info = {"files": 0, "bytes": 0, "first_mono": None, "last_mono": None,
                    "errors": 0, "binary_segments": 0}
            for p in files:
                data_limit = 256 * 1024
                head = read_maybe_gz(p, data_limit) if p.suffix != ".gz" else read_gz(p, data_limit)
                if "\x00" in head:
                    info["binary_segments"] += 1
                    self.gaps.append("stream %s/%s is a binary segment and was not decoded"
                                     % (name, p.name))
                    continue
                info["files"] += 1
                try:
                    info["bytes"] += p.stat().st_size
                except OSError:
                    pass
                text = read_maybe_gz(p)
                if p.suffix == ".jsonl":
                    order = self._load_jsonl_stream(name, text, order)
                else:
                    order = self._load_text_stream(name, text, order)
            for e in self.entries:
                if e.stream != name:
                    continue
                if e.ts is not None:
                    info["first_mono"] = e.ts if info["first_mono"] is None else min(info["first_mono"], e.ts)
                    info["last_mono"] = e.ts if info["last_mono"] is None else max(info["last_mono"], e.ts)
                if e.error():
                    info["errors"] += 1
            self.stream_info[name] = info
        idx_streams = self.index.get("streams")
        if isinstance(idx_streams, dict):
            for name, value in idx_streams.items():
                if isinstance(value, dict):
                    merged = self.stream_info.setdefault(str(name), {})
                    for key in ("total_bytes", "gaps", "segments"):
                        if key in value:
                            merged[key] = value[key]

    def _load_jsonl_stream(self, name, text, order):
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except (ValueError, TypeError):
                self.gaps.append("unparsed record in stream %s" % name)
                continue
            if not isinstance(obj, dict):
                continue
            if name == "terminal" and ("cmd" in obj or "command" in obj):
                self.terminal.append(self._terminal_record(obj))
            msg = self._record_message(obj)
            if not msg:
                continue
            e = self._record_entry(name, obj, msg, order)
            self.entries.append(e)
            if name == "kernel":
                self.kernel.append(e)
            order += 1
        return order

    @staticmethod
    def _record_message(obj):
        for key in ("MESSAGE", "msg", "message", "event", "text", "line", "body"):
            if key in obj and obj[key] not in (None, ""):
                value = obj[key]
                if isinstance(value, (dict, list)):
                    return json.dumps(value, sort_keys=True, ensure_ascii=False)
                return str(value)
        return ""

    @staticmethod
    def _terminal_record(obj):
        cmd = obj.get("cmd", obj.get("command", ""))
        return {
            "ts": str(obj.get("ts", "")) if obj.get("ts") is not None else "",
            "mono": as_float(obj.get("mono")),
            "session": str(obj.get("session", obj.get("tty", ""))),
            "user": str(obj.get("user", "")),
            "cmd": str(cmd),
            "exit": as_int(obj.get("exit", obj.get("exit_code"))),
            "dur_ms": as_int(obj.get("dur_ms", obj.get("duration_ms"))),
            "stdout_tail": str(obj.get("stdout_tail", "")),
            "stderr_tail": str(obj.get("stderr_tail", "")),
        }

    @staticmethod
    def _record_entry(name, obj, msg, order):
        prio = as_int(obj.get("PRIORITY", obj.get("prio", obj.get("priority"))))
        level = str(obj.get("level") or "").upper()
        if prio is None and level:
            prio = {"F": 3, "E": 3, "W": 4, "I": 6, "D": 7}.get(level[:1])
        mono = as_float(obj.get("mono"))
        if mono is None and obj.get("__MONOTONIC_TIMESTAMP") is not None:
            usec = as_int(obj.get("__MONOTONIC_TIMESTAMP"))
            mono = usec / 1_000_000.0 if usec is not None else None
        wall = None
        if obj.get("ts") is not None:
            wall = str(obj.get("ts"))
        elif obj.get("__REALTIME_TIMESTAMP") is not None:
            usec = as_int(obj.get("__REALTIME_TIMESTAMP"))
            if usec is not None:
                try:
                    wall = _dt.datetime.fromtimestamp(usec / 1_000_000.0, _dt.timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ")
                except (OverflowError, OSError, ValueError):
                    wall = None
        program = str(obj.get("SYSLOG_IDENTIFIER") or obj.get("tag") or obj.get("unit") or "")
        return Entry(name, msg, ts=mono, wall=wall, prio=prio, order=order, stream=name, program=program)

    def _load_text_stream(self, name, text, order):
        for raw in text.splitlines():
            if not raw.strip():
                continue
            m = KMSG_RE.match(raw)
            if m:
                prio, seq, usec, _flags, msg = m.groups()
                e = Entry(name, msg, ts=float(usec) / 1_000_000.0, prio=as_int(prio),
                          seq=as_int(seq), order=order, stream=name)
            else:
                m = MONO_PROG_RE.match(raw)
                if m:
                    e = Entry(name, m.group(4), ts=float(m.group(1)), program=m.group(3),
                              order=order, stream=name)
                else:
                    m = MONO_RE.match(raw)
                    if m:
                        e = Entry(name, m.group(2), ts=float(m.group(1)), order=order, stream=name)
                    else:
                        m = ISO_PROG_RE.match(raw) or WALL_PROG_RE.match(raw)
                        if m:
                            e = Entry(name, m.group(3), wall=m.group(1), program=m.group(2),
                                      order=order, stream=name)
                        else:
                            m = ISO_RE.match(raw) or WALL_RE.match(raw)
                            if m:
                                e = Entry(name, m.group(2), wall=m.group(1), order=order, stream=name)
                            else:
                                e = Entry(name, raw, order=order, stream=name)
            if not e.msg.strip():
                continue
            self.entries.append(e)
            if name == "kernel":
                self.kernel.append(e)
            order += 1
        return order

    def _load_writer_markers(self):
        for name in ("05-writer.log", "writer.log"):
            p = self.find(name)
            if not p:
                continue
            for line in read_text(p).splitlines():
                if re.search(r"(DEST_CHANGED|RAM_CAP|STREAM_CAP|BUDGET_EXHAUSTED|DEGRADED|fallback|destination)", line, re.I):
                    self.writer_markers.append(line.strip())
        for line in read_text(self.find("alive.txt") or Path("/nonexistent")).splitlines():
            if "where=" in line:
                self.writer_markers.append("alive: " + line.strip())
        if self.summary_json.get("degraded") or self.summary.get("DEGRADED"):
            self.writer_markers.append("degraded=1")

    def _detect_layout(self):
        if (self.path / "streams").is_dir() or self.index or self.summary_json or self.boot_meta:
            self.layout = "v3"
        elif (self.path / "smart").is_dir() or self.find("02-initramfs-console.log"):
            self.layout = "v2"
        elif self.kernel or self.snapshots or self.summary:
            self.layout = "v2"
        else:
            self.layout = "unknown"

    def _compute_times(self):
        uptime = None
        if self.index.get("duration_s") is not None:
            uptime = as_float(self.index.get("duration_s"))
        if uptime is None and self.summary.get("uptime_s"):
            uptime = as_float(self.summary["uptime_s"])
        if uptime is None and self.history:
            uptime = as_float(self.history[-1].get("uptime"))
        if uptime is None and self.snapshots:
            uptime = self.snapshots[-1]["uptime"]
        if uptime is None and self.kernel:
            uptime = self.kernel[-1].ts
        if uptime is None and self.stream_info:
            values = [v.get("last_mono") for v in self.stream_info.values() if v.get("last_mono") is not None]
            if values:
                uptime = max(values)
        self.duration_s = uptime
        self.start_utc = self.index.get("started_utc") or self.boot_meta.get("started_utc")
        self.end_utc = self.index.get("ended_utc") or self.boot_meta.get("ended_utc")
        if not self.start_utc and self.summary.get("written") and uptime is not None:
            self.end_utc = str(self.summary["written"])
            try:
                end = _dt.datetime.strptime(str(self.summary["written"]), "%H:%M:%SZ")
                start = end - _dt.timedelta(seconds=uptime)
                self.start_utc = start.strftime("%H:%M:%SZ")
            except ValueError:
                pass
        self.events.sort(key=lambda e: (e["up"] is None, e["up"] or 0, e["text"]))

    def _compute_gaps(self):
        if self.layout == "v3":
            if not self.index:
                self.gaps.append("no index.json or index.partial.json (writer did not stop cleanly)")
            elif not self.index.get("complete", False):
                self.gaps.append("index is partial: the boot did not stop cleanly")
            streams = self.index.get("streams")
            if isinstance(streams, dict):
                for name, value in sorted(streams.items()):
                    if not isinstance(value, dict):
                        continue
                    gaps = value.get("gaps")
                    if isinstance(gaps, list) and gaps:
                        self.gaps.append("stream %s reports %d gap(s)" % (name, len(gaps)))
        else:
            if not self.snapshots:
                self.gaps.append("no smart snapshot files found")
            else:
                last = self.snapshots[-1]
                sizes = [s["bytes"] for s in self.snapshots[:-1] if s["bytes"] > 0]
                median = sorted(sizes)[len(sizes) // 2] if sizes else 0
                self.gaps.append("%d snapshot(s); last at %s (%d bytes)"
                                 % (len(self.snapshots), fmt_ts(last["uptime"]), last["bytes"]))
                if median and last["bytes"] < median / 2:
                    self.gaps.append("last snapshot is much smaller than the typical %d bytes "
                                     "-> the final snapshot was probably cut short" % median)
            gz = sorted(self.path.rglob("journal-final.log.gz"))
            if gz:
                text = read_gz(gz[-1])
                last_ts = None
                for line in text.splitlines():
                    m = MONO_RE.match(line)
                    if m:
                        last_ts = float(m.group(1))
                if last_ts is not None and self.duration_s and last_ts < self.duration_s - 20:
                    self.gaps.append("final journal export stops at %s, %.0f s before the last known "
                                     "uptime -> likely truncated" % (fmt_ts(last_ts), self.duration_s - last_ts))
            err = read_text(self.find("journal-errors.log") or Path("/nonexistent")).splitlines()
            if err:
                self.gaps.append("journal-errors.log last line: " + quote(err[-1], 120))
            ec = re.search(r"KESTREL_USERSPACE_CAPTURE_WINDOW_(FINISHED|EXPIRED).*?budget_s=(\d+)",
                           read_text(self.find("00-status.txt") or Path("/nonexistent")))
            if ec:
                self.gaps.append("early userspace capture %s after a %s s budget"
                                 % (ec.group(1).lower(), ec.group(2)))
            susp = next((e for e in self.kernel if "PM: suspend entry" in e.msg), None)
            row = next((r for r in self.history if r.get("seq") == "resume"), None)
            if susp and row:
                up = as_float(row.get("uptime"))
                if up and susp.ts is not None and abs(up - susp.ts) > 5:
                    self.gaps.append("clock domains differ: suspend at kmsg %s (monotonic) vs smartlog "
                                     "resume up=%s (uptime includes the %.0f s suspend)"
                                     % (fmt_ts(susp.ts), fmt_ts(up), up - susp.ts))
        for marker in self.writer_markers:
            if re.search(r"(DEST_CHANGED|RAM_CAP|STREAM_CAP|BUDGET_EXHAUSTED)", marker, re.I):
                self.gaps.append("writer: " + quote(marker, 160))
        dynamic = sorted(set(self.stream_info) - {"kernel", "journal"})
        if dynamic:
            self.gaps.append("additional streams present: " + ", ".join(dynamic))

    def unique_entries(self):
        seen = set()
        out = []
        for e in self.entries:
            key = (round(e.ts, 3) if e.ts is not None else None, e.wall, e.msg[:240], e.stream)
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out

    def final_snapshot(self):
        return self.snapshots[-1] if self.snapshots else None

    def text(self, name):
        p = self.find(name)
        return read_text(p) if p else ""

    def build_id(self):
        for source in (self.summary_json.get("build_id"), self.index.get("build_id"),
                       self.boot_meta.get("build_id"), self.summary.get("BUILD_ID")):
            if source:
                return str(source)
        for snap in reversed(self.snapshots):
            m = re.search(r"^(?:BUILD_ID|VERSION_ID)=(\S+)", snap["text"], re.M)
            if m:
                return m.group(1).strip('"')
        return ""

    def kernel_release(self):
        for source in (self.summary_json.get("kernel_release"), self.index.get("kernel"),
                       self.boot_meta.get("kernel")):
            if source:
                return str(source)
        m = re.search(r"Linux\s+\S+\s+(\S+)", self.text("00-status.txt"))
        if m:
            return m.group(1)
        snap = self.final_snapshot()
        if snap:
            m = re.search(r"Linux\s+\S+\s+(\S+)", snap["text"])
            if m:
                return m.group(1)
        for e in self.kernel:
            m = re.search(r"Linux version \S+ \(.*?\) .*", e.msg)
            if m:
                return e.msg[:120]
        return ""


def error_entries(boot):
    return [e for e in boot.unique_entries() if e.error()]


def signatures(entries, limit=8):
    counts = {}
    for e in entries:
        text = e.msg.splitlines()[0]
        text = re.sub(r"^archlinux\s+", "", text)
        text = re.sub(r"^kernel:\s+", "", text)
        text = re.sub(r"\[\s*\d+\.\d+\]", "", text)
        text = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex>", text)
        text = re.sub(r"\b\d{2,}\b", "<n>", text)
        text = re.sub(r"\s+", " ", text).strip()
        key = (e.subsystem, text[:130])
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(((n, sub, txt) for (sub, txt), n in counts.items()),
                     key=lambda item: (-item[0], item[1], item[2]))
    return ordered[:limit]


def first_fault(boot, regex, before, after):
    for i, e in enumerate(boot.kernel):
        if regex.search(e.msg):
            lo = max(0, i - before)
            hi = min(len(boot.kernel), i + after)
            return e, boot.kernel[lo:hi]
    for e in boot.unique_entries():
        if e.src in ("warnings", "errors") and regex.search(e.msg):
            return e, []
    return None


def error_counts(boot):
    counts = {}
    for e in boot.unique_entries():
        if e.error():
            counts[e.subsystem] = counts.get(e.subsystem, 0) + 1
    return dict(sorted(counts.items()))


def failed_units(boot):
    names = set()
    for key in ("failed_units", "FAILED UNITS"):
        raw = boot.summary_json.get(key) if key in boot.summary_json else boot.summary.get(key)
        if isinstance(raw, (list, tuple)):
            for item in raw:
                names.update(UNIT_RE.findall(str(item)))
        elif raw:
            names.update(UNIT_RE.findall(str(raw)))
    snap = boot.final_snapshot()
    texts = [snap["text"]] if snap else []
    texts.append(boot.text("journal-errors.log"))
    for text in texts:
        in_block = False
        for line in text.splitlines():
            if line.startswith("=="):
                in_block = "failed units" in line.lower()
                continue
            if in_block and line.strip():
                m = re.match(r"^[*\u25cf]\s+(\S+\.(?:service|socket|timer|target|mount|path))", line.strip())
                if m:
                    names.add(m.group(1))
                    continue
                m = re.match(r"^\s*(\S+\.(?:service|socket|timer|target|mount|path))\s+loaded\s+failed", line)
                if m:
                    names.add(m.group(1))
        for m in re.finditer(r"Failed to start ([A-Za-z0-9@_.:-]+\.(?:service|socket|timer|target|mount|path))", text):
            names.add(m.group(1))
    for e in boot.entries:
        m = re.search(r"Failed to start ([A-Za-z0-9@_.:-]+\.(?:service|socket|timer|target|mount|path))", e.msg)
        if m:
            names.add(m.group(1))
        m = re.search(r"Unit ([A-Za-z0-9@_.:-]+\.(?:service|socket|timer|target|mount|path)) entered failed state", e.msg)
        if m:
            names.add(m.group(1))
    return sorted(n for n in names if n.rsplit(".", 1)[-1] in UNIT_SUFFIXES)


def suspend_stats(boot):
    stats = {}
    raw = boot.summary_json.get("suspend")
    if isinstance(raw, dict):
        stats = {str(k): str(v) for k, v in raw.items()}
    elif raw:
        stats["summary"] = str(raw)
    if not stats:
        snap = boot.final_snapshot()
        if snap:
            in_block = False
            for line in snap["text"].splitlines():
                if line.startswith("=="):
                    in_block = "suspend and resume statistics" in line
                    continue
                if in_block:
                    m = re.match(r"^(\w+)=(\S+)", line.strip())
                    if m:
                        stats[m.group(1)] = m.group(2)
    if not stats:
        text = " ".join(boot.summary_lines)
        m = re.search(r"success=(\d+).*fail=(\d+)", text)
        if m:
            stats = {"success": m.group(1), "fail": m.group(2)}
    events = [e for e in boot.entries if re.search(r"(PM: suspend entry|PM: suspend exit|failed to resume|Hardware became unavailable upon resume)", e.msg, re.I)]
    stats["suspend_entry_records"] = str(sum(1 for e in events if "suspend entry" in e.msg))
    stats["resume_failure_records"] = str(sum(1 for e in events if re.search(r"(failed to resume|Hardware became unavailable)", e.msg, re.I)))
    return stats


def wifi_stats(boot):
    stats = {}
    raw = boot.summary_json.get("wifi")
    if isinstance(raw, dict):
        stats.update({str(k): str(v) for k, v in raw.items()})
    elif raw:
        stats["summary"] = str(raw)
    if not stats and boot.summary.get("WIFI"):
        stats["summary"] = str(boot.summary["WIFI"])
    down = []
    up = []
    snap = boot.final_snapshot()
    if snap:
        in_block = False
        for line in snap["text"].splitlines():
            if line.startswith("=="):
                in_block = line.startswith("== network")
                continue
            if in_block and line.strip():
                if re.search(r"\bwl\w*\s+DOWN\b", line):
                    down.append(line.strip())
                elif re.search(r"\bwl\w*\s+UP\b", line):
                    up.append(line.strip())
    stats["down"] = [quote(x, 140) for x in down]
    stats["up"] = [quote(x, 140) for x in up]
    wifi_errors = [e for e in boot.entries if e.subsystem == "wifi" and e.error()]
    stats["error_records"] = str(len(wifi_errors))
    stats["first_errors"] = [quote(e.msg.splitlines()[0], 160) for e in wifi_errors[:3]]
    return stats


def sound_stats(boot):
    stats = {}
    raw = boot.summary_json.get("sound")
    if isinstance(raw, dict):
        stats.update({str(k): str(v) for k, v in raw.items()})
    elif raw:
        stats["summary"] = str(raw)
    if not stats and boot.summary.get("SOUND"):
        stats["summary"] = str(boot.summary["SOUND"])
    sound_errors = [e for e in boot.entries if e.subsystem == "sound" and e.error()]
    stats["error_records"] = str(len(sound_errors))
    stats["first_errors"] = [quote(e.msg.splitlines()[0], 160) for e in sound_errors[:3]]
    return stats


def waydroid_stats(boot):
    stats = {}
    raw = boot.summary_json.get("waydroid")
    if isinstance(raw, dict):
        stats.update({str(k): str(v) for k, v in raw.items()})
    elif raw:
        stats["summary"] = str(raw)
    records = [e for e in boot.entries if e.subsystem == "waydroid"]
    stats["records"] = str(len(records))
    stats["error_records"] = str(sum(1 for e in records if e.error()))
    stats["separated_from_kernel"] = "true"
    stats["first_errors"] = [quote(e.msg.splitlines()[0], 160) for e in records if e.error()][:3]
    return stats


def terminal_review(boot):
    items = sorted(boot.terminal, key=lambda t: (t["mono"] is None, t["mono"] or 0, t["cmd"]))
    rows = []
    for item in items:
        rows.append({
            "mono": item["mono"],
            "cmd": quote(item["cmd"], 180),
            "exit": item["exit"],
            "dur_ms": item["dur_ms"],
            "session": quote(item["session"], 40),
            "nonzero": bool(item["exit"] not in (None, 0)),
        })
    return rows


def destination_report(boot):
    found = []

    def add(kind, path="", writable=None, source=""):
        kind, path = str(kind), str(path)
        for item in found:
            if item["kind"] == kind and item["path"] == path:
                return
            if not path and item["kind"] == kind:
                return
        found.append({"kind": kind, "path": path, "writable": writable, "source": source})

    dest_value = boot.boot_meta.get("dest")
    if isinstance(dest_value, dict):
        add(dest_value.get("kind", "?"), dest_value.get("path", ""), dest_value.get("writable"), "boot.json")
    else:
        for key in ("dest", "dest_kind", "where"):
            if boot.boot_meta.get(key):
                add(boot.boot_meta[key], boot.boot_meta.get("dest_path", ""), None, "boot.json")
    for key in ("dest", "dest_kind", "where"):
        if boot.summary_json.get(key):
            add(boot.summary_json[key], boot.summary_json.get("dest_path", ""), None, "summary.json")
    dests = boot.index.get("destinations")
    if isinstance(dests, list):
        for item in dests:
            if isinstance(item, dict):
                add(item.get("kind", "?"), item.get("path", ""), item.get("writable"), "index.json")
    for key in ("DEST", "WHERE"):
        if boot.summary.get(key):
            add(boot.summary[key], "", None, "summary.txt")
    if boot.status.get("where"):
        add(boot.status["where"], "", None, "00-status.txt")
    for marker in boot.writer_markers:
        m = re.search(r"(?:where|to)=(\w+)", marker)
        if m:
            add(m.group(1), "", None, "writer marker")
    degraded = bool(boot.summary_json.get("degraded") or boot.summary.get("DEGRADED")) or any(
        re.search(r"(DEST_CHANGED|DEGRADED|RAM_CAP)", marker, re.I) for marker in boot.writer_markers)
    return {"destinations": found, "degraded": degraded,
            "markers": [quote(m, 180) for m in boot.writer_markers]}


def boot_outcome(boot):
    if boot.index.get("outcome"):
        return str(boot.index["outcome"])
    if boot.summary_json.get("outcome"):
        return str(boot.summary_json["outcome"])
    if boot.layout == "v3":
        if boot.index.get("complete"):
            return "clean shutdown (index complete)"
        if boot.index:
            return "power loss or hang (index is partial)"
        return "unknown (no index)"
    tail = "\n".join(e.msg for e in boot.kernel[-120:])
    if re.search(r"systemd-shutdown|reboot: Power down|reboot: Restarting system", tail):
        return "clean shutdown (systemd-shutdown marker in kernel log)"
    if re.search(r"EXT4-fs .*unmounting", tail) and boot.events and any("final" in e["text"] for e in boot.events):
        return "clean shutdown (final snapshot + unmount marker)"
    if boot.events and any("final snapshot done" in e["text"] for e in boot.events):
        return "orderly stop (final snapshot marker; no kernel shutdown marker)"
    return "NO clean shutdown marker (hard power-off, forced reboot, or kernel hang likely)"


def timeline(boot, max_events):
    items = [(0.0, 'boot (first record)')]
    for e in boot.events:
        if e["up"] is not None:
            items.append((e["up"], "event: " + str(e["text"])))
    for snap in boot.snapshots:
        if snap["seq"] in ("1", "999"):
            items.append((snap["uptime"] if snap["uptime"] is not None else 0.0,
                          "snapshot %s (%d bytes, %s)" % (snap["seq"], snap["bytes"], snap["where"])))
    for row in boot.history:
        if row.get("seq", "") in ("resume", "kernelburst", "manual"):
            up = as_float(row.get("uptime")) or 0.0
            duplicate = any(ev["up"] is not None and abs(ev["up"] - up) <= 2
                            and str(row.get("seq", "")).lower() in str(ev["text"]).lower()
                            for ev in boot.events)
            if duplicate:
                continue
            items.append((up, "event %s (errors=%s, oops=%s)" % (row.get("seq"), row.get("kernel_errors", "?"),
                                                                 row.get("oops_like", "?"))))
    for marker in boot.writer_markers:
        if re.search(r"(DEST_CHANGED|RAM_CAP|STREAM_CAP|BUDGET_EXHAUSTED)", marker, re.I):
            items.append((0.0, "writer: " + marker))
    if boot.terminal:
        first = min((t["mono"] for t in boot.terminal if t["mono"] is not None), default=None)
        items.append((first or 0.0, "terminal: %d command(s) recorded" % len(boot.terminal)))
    items.sort(key=lambda item: (item[0], item[1]))
    return [{"up": up, "text": quote(text, 180)} for up, text in items[: max(4, max_events + 4)]]


def suspicious_lines(boot):
    found = []
    seen = set()
    candidates = []
    for e in boot.unique_entries():
        candidates.append((e.src, e.msg, e.ts))
    for item in boot.terminal:
        candidates.append(("terminal:" + (item["session"] or "?"), item["cmd"], item["mono"]))
        candidates.append(("terminal-output", item["stdout_tail"], item["mono"]))
        candidates.append(("terminal-output", item["stderr_tail"], item["mono"]))
    for source, text, mono in candidates:
        if not text:
            continue
        for line in str(text).splitlines() or [str(text)]:
            for name, rx in INJECTION_RES:
                if rx.search(line):
                    key = (name, line[:200])
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append({"kind": name, "source": source, "mono": mono,
                                  "text": quote(line, 200)})
                    break
    found.sort(key=lambda x: (x["mono"] is None, x["mono"] or 0, x["kind"], x["text"]))
    return found


def differences(boot, prev):
    if not prev:
        return []
    changes = []
    for label, new, old in (
        ("kernel", boot.kernel_release(), prev.kernel_release()),
        ("build", boot.build_id(), prev.build_id()),
        ("outcome", boot_outcome(boot), boot_outcome(prev)),
    ):
        if new != old:
            changes.append("%s: %s -> %s" % (label, quote(old or "?", 120), quote(new or "?", 120)))
    for label, new, old in (
        ("duration_s", boot.duration_s, prev.duration_s),
        ("failed_units", len(failed_units(boot)), len(failed_units(prev))),
        ("suspend_success", suspend_stats(boot).get("success"), suspend_stats(prev).get("success")),
        ("suspend_fail", suspend_stats(boot).get("fail"), suspend_stats(prev).get("fail")),
        ("wifi_errors", wifi_stats(boot).get("error_records"), wifi_stats(prev).get("error_records")),
        ("sound_errors", sound_stats(boot).get("error_records"), sound_stats(prev).get("error_records")),
        ("waydroid_errors", waydroid_stats(boot).get("error_records"), waydroid_stats(prev).get("error_records")),
        ("terminal_commands", len(boot.terminal), len(prev.terminal)),
        ("terminal_failures", sum(1 for t in boot.terminal if t["exit"] not in (None, 0)),
         sum(1 for t in prev.terminal if t["exit"] not in (None, 0))),
    ):
        if new != old:
            changes.append("%s: %r -> %r" % (label, old, new))
    new_units = set(failed_units(boot))
    old_units = set(failed_units(prev))
    for name in sorted(new_units - old_units):
        changes.append("new failed unit: " + name)
    for name in sorted(old_units - new_units):
        changes.append("failed unit gone: " + name)
    new_counts = error_counts(boot)
    old_counts = error_counts(prev)
    for sub in sorted(set(new_counts) | set(old_counts)):
        if new_counts.get(sub) != old_counts.get(sub):
            changes.append("errors[%s]: %s -> %s" % (sub, old_counts.get(sub, 0), new_counts.get(sub, 0)))
    new_sigs = {(sub, txt): n for n, sub, txt in signatures(error_entries(boot), 40)}
    old_sigs = {(sub, txt): n for n, sub, txt in signatures(error_entries(prev), 40)}
    for key in sorted(new_sigs):
        if key not in old_sigs and new_sigs[key] >= 3:
            changes.append("new repeated signature (%dx): %s" % (new_sigs[key], quote(key[1], 160)))
    if not changes:
        changes.append("no material difference in the compared fields")
    return changes


def build_digest(boot):
    oops = first_fault(boot, HARD_FAULT_RE, 6, 10)
    warning = first_fault(boot, WARNING_RE, 3, 4)
    data = {
        "schema": SCHEMA,
        "boot": {
            "id": boot.boot_id,
            "folder": str(boot.path),
            "layout": boot.layout,
            "duration_s": boot.duration_s,
            "duration": fmt_ts(boot.duration_s),
            "started": boot.start_utc,
            "ended": boot.end_utc,
            "outcome": boot_outcome(boot),
            "build": boot.build_id(),
            "kernel": boot.kernel_release(),
            "cmdline": [quote(x, 100) for x in (boot.index.get("cmdline") or boot.boot_meta.get("cmdline") or [])],
        },
        "destination": destination_report(boot),
        "timeline": timeline(boot, 12),
        "errors_by_subsystem": error_counts(boot),
        "first_oops": None,
        "first_warning": None,
        "failed_units": failed_units(boot),
        "findings": {
            "suspend": suspend_stats(boot),
            "wifi": wifi_stats(boot),
            "sound": sound_stats(boot),
            "waydroid": waydroid_stats(boot),
            "storage": [quote(e.msg.splitlines()[0], 160) for e in boot.entries
                        if e.subsystem == "storage" and e.error()][:5],
        },
        "terminal": terminal_review(boot),
        "top_signatures": [{"count": n, "subsystem": sub, "text": quote(txt, 160)}
                           for n, sub, txt in signatures(error_entries(boot), 8)],
        "suspicious": suspicious_lines(boot),
        "gaps": [quote(g, 180) for g in boot.gaps],
        "previous": None,
    }
    if oops:
        e, ctx = oops
        data["first_oops"] = {
            "mono": e.ts,
            "source": e.src,
            "text": quote(e.msg.splitlines()[0] if e.msg else "", 200),
            "context": [{"mono": c.ts, "text": quote(c.msg.splitlines()[0], 200),
                         "current": c is e} for c in ctx],
        }
    if warning:
        e, ctx = warning
        data["first_warning"] = {
            "mono": e.ts,
            "source": e.src,
            "text": quote(e.msg.splitlines()[0] if e.msg else "", 200),
            "context": [{"mono": c.ts, "text": quote(c.msg.splitlines()[0], 200),
                         "current": c is e} for c in ctx],
        }
    if boot.previous:
        data["previous"] = {"boot_id": boot.previous.boot_id,
                            "changes": [quote(x, 180) for x in differences(boot, boot.previous)]}
    return data


def print_digest(boot, data):
    b = data["boot"]
    print("FroodzOS digest  boot " + b["id"])
    print("  folder   " + b["folder"])
    print("  layout   %s   duration %s" % (b["layout"], b["duration"]))
    print("  outcome  " + quote(b["outcome"], 180))
    print("  build    %s   %s" % (quote(b["build"] or "?", 60), quote(b["kernel"] or "?", 120)))
    if b["cmdline"]:
        print("  options  " + " ".join(b["cmdline"][:12]))

    dest = data["destination"]
    print("\nDestination")
    if dest["destinations"]:
        for item in dest["destinations"]:
            print("  - %s %s (%s)" % (quote(item["kind"], 40),
                                      quote(item["path"], 120), item["source"]))
    else:
        print("  - no explicit destination record")
    print("  degraded: %s" % ("yes" if dest["degraded"] else "no"))
    for marker in dest["markers"][:6]:
        print("  marker " + marker)

    print("\nTimeline")
    for item in data["timeline"]:
        print("  %s  %s" % (fmt_ts(item["up"]), item["text"]))

    print("\nErrors by subsystem (Waydroid separated)")
    if data["errors_by_subsystem"]:
        for sub, count in sorted(data["errors_by_subsystem"].items(), key=lambda kv: (-kv[1], kv[0])):
            print("  %-9s %d" % (sub, count))
    else:
        print("  none classified as errors")

    print("\nFindings")
    s = data["findings"]["suspend"]
    if s:
        print("  suspend  " + " ".join("%s=%s" % (k, quote(v, 80)) for k, v in sorted(s.items()) if k != "first_errors"))
    w = data["findings"]["wifi"]
    if w:
        print("  wifi     errors=%s %s" % (w.get("error_records", "?"),
                                           quote(w.get("summary", ""), 140)))
        for line in w.get("first_errors", [])[:2]:
            print("           " + line)
    so = data["findings"]["sound"]
    if so:
        print("  sound    errors=%s %s" % (so.get("error_records", "?"),
                                           quote(so.get("summary", ""), 140)))
    wa = data["findings"]["waydroid"]
    print("  waydroid records=%s errors=%s (excluded from kernel faults)"
          % (wa.get("records", "0"), wa.get("error_records", "0")))
    if data["failed_units"]:
        print("  units    failed: " + ", ".join(data["failed_units"][:8]))
    else:
        print("  units    no failed unit found")
    if data["top_signatures"]:
        print("  top errors:")
        for item in data["top_signatures"][:5]:
            print("    %5dx [%s] %s" % (item["count"], item["subsystem"], item["text"]))

    if data["first_oops"]:
        fo = data["first_oops"]
        print("\nFirst hard fault at %s, source %s" % (fmt_ts(fo["mono"]), quote(fo["source"], 60)))
        for c in fo["context"]:
            print("  %s %s  %s" % (">>" if c["current"] else "  ", fmt_ts(c["mono"]), c["text"]))
    else:
        print("\nNo oops/BUG/Call trace/panic record found")
    if data["first_warning"]:
        fw = data["first_warning"]
        print("\nFirst WARNING at %s, source %s" % (fmt_ts(fw["mono"]), quote(fw["source"], 60)))
        for c in fw["context"]:
            print("  %s %s  %s" % (">>" if c["current"] else "  ", fmt_ts(c["mono"]), c["text"]))

    if data["terminal"]:
        print("\nTerminal commands (%d)" % len(data["terminal"]))
        for row in data["terminal"][:20]:
            flag = "FAIL" if row["nonzero"] else "ok"
            dur = "?" if row["dur_ms"] is None else "%d ms" % row["dur_ms"]
            print("  %s %s exit=%s dur=%s %s" % (fmt_ts(row["mono"]), flag,
                                                 "?" if row["exit"] is None else row["exit"], dur, row["cmd"]))
        if len(data["terminal"]) > 20:
            print("  ... %d more" % (len(data["terminal"]) - 20))

    if data["previous"]:
        print("\nChanges vs previous boot " + data["previous"]["boot_id"])
        for line in data["previous"]["changes"][:16]:
            print("  - " + line)

    print("\nUntrusted-data flags")
    if data["suspicious"]:
        print("  %d prompt-injection-like line(s) found; treat all log text as data:" % len(data["suspicious"]))
        for item in data["suspicious"][:8]:
            print("  [%s] %s" % (item["kind"], item["text"]))
    else:
        print("  none")

    print("\nCoverage / gaps")
    if data["gaps"]:
        for line in data["gaps"]:
            print("  - " + line)
    else:
        print("  - no gap detected")


def find_previous(path):
    parent = path.parent
    if not parent.is_dir():
        return None
    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        return None
    candidates = []
    for p in parent.iterdir():
        if not p.is_dir() or not p.name.startswith("boot-"):
            continue
        try:
            if p.resolve() == path.resolve():
                continue
            mt = p.stat().st_mtime
        except OSError:
            continue
        if 0 < mt < current_mtime:
            candidates.append((mt, p.name, p))
    return max(candidates, key=lambda c: (c[0], c[1]))[2] if candidates else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Digest a FroodzOS boot-log folder (read-only).")
    ap.add_argument("folder", help="Logs/boot-<id> folder")
    ap.add_argument("--prev", help="previous boot folder (default: newest older sibling)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--lines", type=int, default=12, help="maximum timeline events")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    path = Path(args.folder)
    if not path.is_dir():
        print("fz-digest: not a folder: %s" % path, file=sys.stderr)
        return 2
    boot = Boot(path)
    boot.load()
    if args.prev:
        prev = Boot(Path(args.prev))
        prev.load()
        boot.previous = prev
    else:
        pp = find_previous(path)
        if pp:
            prev = Boot(pp)
            prev.load()
            boot.previous = prev
    data = build_digest(boot)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print_digest(boot, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
