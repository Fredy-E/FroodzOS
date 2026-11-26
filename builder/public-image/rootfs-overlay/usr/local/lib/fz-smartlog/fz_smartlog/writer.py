# SPDX-License-Identifier: GPL-2.0-or-later
"""StreamWriter - the one writer every smartlog stream uses (W4 sec.15).

Contract highlights
* One JSON object per line, one ``os.write()`` per record.
* ``<stream>/<seq:06d>.jsonl``; a meta record opens every segment.
* ``fdatasync`` every ``FZ_LOG_SYNC_MS`` (default 1000) or
  ``FZ_LOG_SYNC_BYTES`` (default 65536); rotate at ``FZ_LOG_SEGMENT_BYTES``
  (default 8 MiB); stop at ``FZ_LOG_MAX_STREAM_BYTES``.
* Closed segments are never modified.  A torn final line is expected after a
  power cut and is ignored by :func:`read_jsonl`.
* ``EROFS``/``ENOSPC``/``EIO``/``ENODEV`` raise :class:`DestinationFailed`;
  the supervisor switches destination and restarts the worker.
"""
from __future__ import annotations

import errno
import json
import os
import re
import threading
import time

from .redact import Redactor

SCHEMA = 3
DEFAULT_SEGMENT_BYTES = 8 << 20
DEFAULT_SYNC_MS = 1000
DEFAULT_SYNC_BYTES = 64 << 10
DEFAULT_MAX_BYTES = 32 << 20
FATAL_ERRNOS = {
    errno.EROFS, errno.ENOSPC, errno.EIO, errno.ENODEV, errno.EDQUOT, errno.ENXIO,
}
SEGMENT_RE = re.compile(r"^(\d{6,})\.jsonl$")
STREAM_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class DestinationFailed(Exception):
    """The destination cannot accept writes; the supervisor must switch."""

    def __init__(self, reason, errno_value=None, path=None):
        self.reason = str(reason)
        self.errno = errno_value
        self.path = path
        super().__init__("%s%s%s" % (self.reason,
                                     " errno=%s" % errno_value if errno_value else "",
                                     " path=%s" % path if path else ""))


def _fatal(exc):
    return isinstance(exc, OSError) and exc.errno in FATAL_ERRNOS


def utc_iso(wall=None):
    wall = time.time() if wall is None else wall
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(wall)) + ".%03dZ" % (
        int(wall * 1000) % 1000)


def parse_jsonl(data):
    """Return (records, bad_lines, trailing_partial) for NDJSON bytes/text."""
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    lines = data.split(b"\n")
    trailing = False
    if lines and lines[-1] == b"":
        lines.pop()
    elif lines:
        trailing = True
        lines = lines[:-1]
    records, bad = [], []
    for line in lines:
        line = line.rstrip(b"\r")
        if not line:
            continue
        try:
            rec = json.loads(line.decode("utf-8", "replace"))
            if not isinstance(rec, dict):
                raise ValueError("not an object")
        except Exception:
            bad.append(line)
            continue
        records.append(rec)
    return records, bad, trailing


def read_jsonl(path):
    with open(path, "rb") as fh:
        return parse_jsonl(fh.read())


class StreamWriter:
    def __init__(self, stream, base_dir=None, max_bytes=None, segment_bytes=None,
                 sync_ms=None, sync_bytes=None, privacy=None, redactor=None,
                 clock=time.monotonic, wall_clock=time.time,
                 open_func=os.open, write_func=None, close_func=os.close,
                 stat_func=os.stat, listdir_func=os.listdir,
                 makedirs_func=os.makedirs, unlink_func=os.unlink,
                 fsync_func=None, fdatasync_func=None):
        if not STREAM_RE.match(stream):
            raise ValueError("invalid stream name: %r" % (stream,))
        self.stream = stream
        self.base_dir = base_dir or os.environ.get("FZ_LOG_DIR")
        if not self.base_dir:
            raise ValueError("no base_dir and FZ_LOG_DIR is not set")
        self.stream_dir = os.path.join(self.base_dir, stream)
        self.max_bytes = int(max_bytes if max_bytes is not None else
                             os.environ.get("FZ_LOG_MAX_STREAM_BYTES", DEFAULT_MAX_BYTES))
        self.segment_bytes = int(segment_bytes if segment_bytes is not None else
                                 os.environ.get("FZ_LOG_SEGMENT_BYTES", DEFAULT_SEGMENT_BYTES))
        self.sync_ms = int(sync_ms if sync_ms is not None else
                           os.environ.get("FZ_LOG_SYNC_MS", DEFAULT_SYNC_MS))
        self.sync_bytes = int(sync_bytes if sync_bytes is not None else
                              os.environ.get("FZ_LOG_SYNC_BYTES", DEFAULT_SYNC_BYTES))
        self.privacy = (privacy or os.environ.get("FZ_LOG_PRIVACY") or "owner").lower()
        self.redactor = redactor or Redactor(mode=self.privacy)
        self.clock = clock
        self.wall_clock = wall_clock
        self._open_func = open_func
        self._write_func = write_func or os.write
        self._close_func = close_func
        self._stat_func = stat_func
        self._listdir_func = listdir_func
        self._makedirs_func = makedirs_func
        self._unlink_func = unlink_func
        self._fsync_func = fsync_func or getattr(os, "fsync", None)
        self._fdatasync_func = fdatasync_func or getattr(os, "fdatasync", None) or getattr(os, "fsync", None)
        self._lock = threading.RLock()
        self.fd = None
        self.seq = 0
        self.path = None
        self.segment_size = 0
        self.total_bytes = 0
        self.unsynced_bytes = 0
        self.records = 0
        self.last_sync = self.clock()
        self.last_write = None
        self.first_mono = None
        self.last_mono = None
        self.closed = False
        self.capped = False
        self.failed = False
        self.close_reason = None
        self.open_errors = 0
        self._open_segment()

    # -- low level -------------------------------------------------------
    def _fatal(self, exc, what):
        self.failed = True
        try:
            if self.fd is not None:
                self._close_func(self.fd)
        except OSError:
            pass
        self.fd = None
        raise DestinationFailed("%s:%s" % (what, getattr(exc, "errno", "error")),
                                getattr(exc, "errno", None), self.path) from exc

    def _fsync_dir(self):
        try:
            fd = self._open_func(self.stream_dir, os.O_RDONLY)
        except OSError:
            return
        try:
            if self._fsync_func:
                self._fsync_func(fd)
        except OSError:
            pass
        finally:
            try:
                self._close_func(fd)
            except OSError:
                pass

    def _next_seq(self):
        highest = 0
        try:
            names = self._listdir_func(self.stream_dir)
        except OSError as exc:
            if _fatal(exc):
                self._fatal(exc, "listdir")
            names = []
        for name in names:
            match = SEGMENT_RE.match(name)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    def _encode(self, record):
        clean = self.redactor.record(record)
        try:
            line = json.dumps(clean, ensure_ascii=False, separators=(",", ":"),
                              default=str)
        except (TypeError, ValueError):
            line = json.dumps({"_fz": "unserialisable"}, separators=(",", ":"))
        return (line.replace("\r", "\\r").replace("\n", "\\n") + "\n").encode(
            "utf-8", "replace")

    def _open_segment(self):
        try:
            self._makedirs_func(self.stream_dir, exist_ok=True)
        except OSError as exc:
            self._fatal(exc, "mkdir")
        self.seq = self._next_seq()
        self.path = os.path.join(self.stream_dir, "%06d.jsonl" % self.seq)
        flags = (os.O_WRONLY | os.O_CREAT | os.O_APPEND |
                 getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_BINARY", 0))
        try:
            self.fd = self._open_func(self.path, flags, 0o600)
            self.segment_size = self._stat_func(self.path).st_size
        except OSError as exc:
            self.fd = None
            if _fatal(exc):
                self._fatal(exc, "open")
            self.open_errors += 1
            raise DestinationFailed("open:%s" % exc.errno, exc.errno, self.path) from exc
        self._fsync_dir()
        meta = {"_fz": "stream_open", "schema": SCHEMA, "stream": self.stream,
                "seq": self.seq, "opened_utc": utc_iso(self.wall_clock())}
        self._write_bytes(self._encode(meta), count_record=False)
        self.last_sync = self.clock()

    def _write_bytes(self, data, count_record=True):
        if self.fd is None:
            raise DestinationFailed("no-open-fd", None, self.path)
        try:
            written = 0
            while written < len(data):
                written += self._write_func(self.fd, data[written:])
        except OSError as exc:
            if _fatal(exc):
                self._fatal(exc, "write")
            raise
        self.segment_size += len(data)
        self.total_bytes += len(data)
        self.unsynced_bytes += len(data)
        if count_record:
            self.records += 1

    # -- public API ------------------------------------------------------
    def current_path(self):
        return self.path

    def write(self, record):
        """Append one dict as one JSON line. Returns False when capped/closed."""
        if not isinstance(record, dict):
            raise TypeError("StreamWriter.write expects a dict")
        with self._lock:
            if self.closed or self.failed or self.capped:
                return False
            if self.fd is None:
                return False
            now = self.clock()
            if self.last_write is not None and now < self.last_sync:
                self.last_sync = now
            if (now - self.last_sync) * 1000 >= self.sync_ms or \
                    self.unsynced_bytes >= self.sync_bytes:
                self.flush()
            data = self._encode(record)
            if self.total_bytes + len(data) > self.max_bytes:
                self.capped = True
                cap = {"_fz": "stream_cap", "stream": self.stream,
                       "bytes": self.total_bytes, "cap": self.max_bytes}
                try:
                    self._write_bytes(self._encode(cap), count_record=False)
                    self.flush()
                except DestinationFailed:
                    raise
                return False
            if self.segment_size > 0 and self.segment_size + len(data) > self.segment_bytes:
                self.rotate("size")
            self._write_bytes(data)
            self.last_write = now
            mono = record.get("mono")
            if isinstance(mono, (int, float)):
                if self.first_mono is None:
                    self.first_mono = float(mono)
                self.last_mono = float(mono)
            if self.unsynced_bytes >= self.sync_bytes:
                self.flush()
            return True

    def flush(self):
        """fdatasync the current segment.  Raises DestinationFailed on fatal IO."""
        with self._lock:
            if self.fd is None or self.closed:
                return True
            if not self.unsynced_bytes:
                self.last_sync = self.clock()
                return True
            try:
                if self._fdatasync_func:
                    self._fdatasync_func(self.fd)
            except OSError as exc:
                if _fatal(exc):
                    self._fatal(exc, "sync")
                raise
            self.unsynced_bytes = 0
            self.last_sync = self.clock()
            return True

    def rotate(self, reason="size"):
        with self._lock:
            if self.closed or self.failed or self.fd is None:
                return False
            try:
                self.flush()
            except DestinationFailed:
                raise
            try:
                self._close_func(self.fd)
            except OSError:
                pass
            self.fd = None
            self._fsync_dir()
            self._open_segment()
            return True

    def close(self, reason="stop"):
        with self._lock:
            if self.closed:
                return self.info()
            self.close_reason = reason
            if self.fd is not None and not self.failed:
                try:
                    rec = {"_fz": "stream_closed", "stream": self.stream,
                           "reason": reason, "bytes": self.total_bytes}
                    self._write_bytes(self._encode(rec), count_record=False)
                except DestinationFailed:
                    pass
                try:
                    self.flush()
                except DestinationFailed:
                    pass
                try:
                    self._close_func(self.fd)
                except OSError:
                    pass
                self.fd = None
                self._fsync_dir()
            self.closed = True
            return self.info()

    def info(self):
        return {
            "stream": self.stream,
            "file": self.path,
            "seq": self.seq,
            "bytes": self.total_bytes,
            "segment_bytes": self.segment_size,
            "records": self.records,
            "first_mono": self.first_mono,
            "last_mono": self.last_mono,
            "complete": self.closed,
            "capped": self.capped,
            "failed": self.failed,
        }

    def segments(self):
        """Describe every segment of this stream on disk (oldest first)."""
        out = []
        try:
            names = sorted(n for n in self._listdir_func(self.stream_dir)
                           if SEGMENT_RE.match(n))
        except OSError:
            return out
        for name in names:
            path = os.path.join(self.stream_dir, name)
            try:
                size = self._stat_func(path).st_size
            except OSError:
                size = 0
            out.append({
                "file": name,
                "path": path,
                "bytes": size,
                "active": os.path.abspath(path) == os.path.abspath(self.path or ""),
            })
        return out


def writer_for_stream(stream, base_dir, caps, segment_bytes, sync_ms, sync_bytes,
                      privacy):
    """Supervisor helper: create a writer with the per-stream cap."""
    return StreamWriter(stream, base_dir=base_dir,
                        max_bytes=caps.get(stream, DEFAULT_MAX_BYTES),
                        segment_bytes=segment_bytes, sync_ms=sync_ms,
                        sync_bytes=sync_bytes, privacy=privacy)
