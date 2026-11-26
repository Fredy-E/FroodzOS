# SPDX-License-Identifier: GPL-2.0-or-later
"""Destination state machine: stick -> FROODZ_PERSIST spool -> RAM.

Budgets follow W6: a 4.5 GiB FAT32 ring, a 2 GiB boot-safety floor, 300 MiB
soft / 550 MiB hard per boot, eight retained boots, and tiered shedding.
The newest boot folder is never deleted.
"""
from __future__ import annotations

import errno
import json
import os
import shutil
import time
from dataclasses import dataclass, field

FATAL_ERRNOS = {
    errno.EROFS, errno.ENOSPC, errno.EIO, errno.ENODEV, errno.EDQUOT, errno.ENXIO,
}
PROTECTED_BOOTS = 2  # current + immediately previous


@dataclass
class Dest:
    kind: str
    root: str
    boot_dir: str
    boot_id: str
    streams_dir: str = ""
    smart_dir: str = ""
    events_dir: str = ""
    writable: bool = True
    floor_mb: int = 0

    def __post_init__(self):
        self.streams_dir = os.path.join(self.boot_dir, "streams")
        self.smart_dir = os.path.join(self.boot_dir, "smart")
        self.events_dir = os.path.join(self.boot_dir, "events")


@dataclass
class Tier:
    name: str
    allowed: set
    journal_max_priority: int = 7
    reason: str = ""

    def can_write(self, stream, priority=7):
        if stream not in self.allowed:
            return False
        if stream == "journal" and priority is not None:
            return int(priority) <= self.journal_max_priority
        return True


ALL_STREAMS = {
    "kernel", "journal", "systemd", "udev", "network", "power",
    "terminal", "ui", "waydroid",
}
BASE_STREAMS = {"kernel", "journal", "systemd", "udev", "network", "power"}


def _default_free_mb(path):
    try:
        st = os.statvfs(path)
        return (st.f_bavail * st.f_frsize) // (1 << 20)
    except AttributeError:
        pass
    except OSError:
        return 0
    try:
        return shutil.disk_usage(path).free // (1 << 20)
    except OSError:
        return 0


def _default_probe(path, size=4096):
    probe = os.path.join(path, ".fz-probe")
    os.makedirs(path, exist_ok=True)
    fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                 getattr(os, "O_BINARY", 0), 0o600)
    try:
        chunk = b"\0" * size
        written = 0
        while written < size:
            written += os.write(fd, chunk[written:])
        fsync = getattr(os, "fdatasync", None) or getattr(os, "fsync", None)
        if fsync:
            fsync(fd)
    finally:
        os.close(fd)
    os.unlink(probe)
    try:
        dfd = os.open(path, os.O_RDONLY)
        try:
            fsync = getattr(os, "fsync", None)
            if fsync:
                fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass
    return True, "ok"


def _walk_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.stat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


class DestManager:
    def __init__(self, config, boot_id=None, clock=time.monotonic,
                 free_mb_func=None, probe_func=None, walk_bytes_func=None,
                 rmtree_func=None):
        self.config = config
        self.boot_id = boot_id or config.boot_id
        self.clock = clock
        self.free_mb_func = free_mb_func or _default_free_mb
        self.probe_func = probe_func or _default_probe
        self.walk_bytes_func = walk_bytes_func or _walk_bytes
        self.rmtree_func = rmtree_func or shutil.rmtree
        self.current = None
        self.chosen_kind = None
        self.failures = []
        self.failed_kinds = set()
        self.reprobe_at = 0.0
        self._free_cache = (0.0, 0)
        self.deleted = []
        self.marker_ok = bool(getattr(config, "marker_ok", False))

    # -- probing ---------------------------------------------------------
    def roots(self):
        return self.config.dest_roots()

    def floor_mb(self, kind):
        if kind == "stick":
            return int(self.config.min_free_mb)
        if kind == "persist":
            return max(1024, int(self.config.min_free_mb))
        return 0

    def make_dest(self, kind):
        root = self.roots()[kind]
        return Dest(kind=kind, root=root,
                    boot_dir=os.path.join(root, "boot-%s" % self.boot_id),
                    boot_id=self.boot_id, floor_mb=self.floor_mb(kind))

    def probe(self, kind):
        if kind not in self.roots():
            return False, "unknown-kind"
        if kind == "persist":
            try:
                if not os.path.ismount(self.config.persist):
                    return False, "persist-not-mounted"
            except (AttributeError, OSError):
                return False, "persist-not-mounted"
        dest = self.make_dest(kind)
        try:
            ok, reason = self.probe_func(dest.root)
        except OSError as exc:
            return False, "probe:%s" % getattr(exc, "errno", "error")
        except Exception:
            return False, "probe:error"
        if not ok:
            return False, reason
        if kind == "ram":
            return True, "ok"
        free = self.free_mb_func(dest.root)
        if free < self.floor_mb(kind):
            return False, "free:%d<floor:%d" % (free, self.floor_mb(kind))
        return True, "ok"

    def choose_initial(self):
        for kind in self.config.active_dest_order():
            ok, reason = self.probe(kind)
            if not ok:
                self.failures.append({"kind": kind, "reason": reason,
                                      "mono": self.clock()})
                self.failed_kinds.add(kind)
                continue
            try:
                return self._activate(kind)
            except OSError as exc:
                why = "activate:%s" % getattr(exc, "errno", "error")
                self.failures.append({"kind": kind, "reason": why,
                                      "mono": self.clock()})
                self.failed_kinds.add(kind)
                continue
        # Last resort: RAM even if the probe failed (it is the only place left).
        kind = "ram"
        self.failures.append({"kind": kind, "reason": "all-candidates-failed",
                              "mono": self.clock()})
        return self._activate(kind, force=True)

    def _activate(self, kind, force=False):
        dest = self.make_dest(kind)
        try:
            self._ensure_dirs(dest)
        except OSError as exc:
            if not force:
                raise
            os.makedirs(dest.boot_dir, exist_ok=True)
        self.current = dest
        if self.chosen_kind is None:
            self.chosen_kind = kind
        self._free_cache = (self.clock(), self.free_mb_func(dest.root))
        return dest

    def _ensure_dirs(self, dest):
        for path in (dest.boot_dir, dest.smart_dir, dest.streams_dir, dest.events_dir):
            os.makedirs(path, exist_ok=True)

    def switch(self, reason="destination-failed"):
        """Move to the next candidate after the current kind."""
        if self.current is None:
            return self.choose_initial()
        order = list(self.config.active_dest_order())
        old = self.current.kind
        self.failures.append({"kind": old, "reason": str(reason),
                              "mono": self.clock()})
        self.failed_kinds.add(old)
        try:
            index = order.index(old)
        except ValueError:
            index = -1
        for kind in order[index + 1:]:
            ok, why = self.probe(kind)
            if ok:
                return self._activate(kind)
            self.failures.append({"kind": kind, "reason": why, "mono": self.clock()})
            self.failed_kinds.add(kind)
        # RAM is the terminal destination and is always attempted.
        if old != "ram":
            return self._activate("ram", force=True)
        raise RuntimeError("no writable destination remains")

    def reprobe_failed(self):
        """Probe previously failed destinations at most every 30 s."""
        now = self.clock()
        if now < self.reprobe_at:
            return []
        self.reprobe_at = now + 30.0
        available = []
        for kind in list(self.failed_kinds):
            if self.current is not None and kind == self.current.kind:
                continue
            ok, _why = self.probe(kind)
            if ok:
                self.failed_kinds.discard(kind)
                available.append(kind)
        return available

    # -- budgets ---------------------------------------------------------
    def free_mb(self, refresh=False):
        if self.current is None:
            return 0
        now = self.clock()
        cached_at, value = self._free_cache
        if refresh or now - cached_at >= 30.0 or value == 0:
            value = self.free_mb_func(self.current.root)
            self._free_cache = (now, value)
        return value

    def boot_bytes(self):
        if self.current is None:
            return 0
        return self.walk_bytes_func(self.current.boot_dir)

    def tier(self):
        """Return the current shedding tier (W6 free-space guard)."""
        if self.current is None:
            return Tier("halt", set(), 0, "no-destination")
        used_mb = self.boot_bytes() // (1 << 20)
        if self.current.kind == "ram":
            cap = max(8, int(self.config.ram_cap_mb))
            if used_mb >= int(cap * 1.2):
                return Tier("halt", set(), 0, "ram-cap")
            if used_mb >= cap:
                return Tier("red", {"kernel", "journal"}, 3, "ram-cap")
            if used_mb >= int(cap * 0.75):
                return Tier("orange", BASE_STREAMS, 7, "ram-soft")
            return Tier("green", ALL_STREAMS, 7, "ram-ok")
        free = self.free_mb()
        if used_mb >= int(self.config.max_boot_mb):
            return Tier("hard", {"kernel", "journal"}, 3, "boot-hard-cap")
        if used_mb >= int(self.config.soft_boot_mb):
            return Tier("soft", BASE_STREAMS, 7, "boot-soft-cap")
        if free < int(self.config.halt_free_mb):
            return Tier("halt", set(), 0, "free-halt")
        if free < 1536:
            return Tier("red", {"kernel", "journal"}, 3, "free-red")
        if free < int(self.config.min_free_mb):
            return Tier("orange", BASE_STREAMS, 7, "free-orange")
        if free < int(self.config.yellow_free_mb):
            return Tier("yellow", ALL_STREAMS - {"ui", "waydroid"}, 7, "free-yellow")
        return Tier("green", ALL_STREAMS, 7, "ok")

    # -- retention -------------------------------------------------------
    def _boot_dirs(self):
        if self.current is None:
            return []
        root = self.current.root
        try:
            names = os.listdir(root)
        except OSError:
            return []
        out = []
        for name in names:
            if not name.startswith("boot-"):
                continue
            path = os.path.join(root, name)
            if not os.path.isdir(path):
                continue
            started = 0
            try:
                with open(os.path.join(path, "boot.json"), "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                started = float(data.get("started_epoch") or 0)
            except (OSError, ValueError, TypeError):
                pass
            if not started:
                try:
                    started = os.stat(path).st_mtime
                except OSError:
                    started = 0
            out.append((started, name, path))
        out.sort()
        return out

    def prune(self, current_name=None):
        """Delete old boot folders; never the current or previous boot."""
        if self.current is None or self.current.kind not in ("stick", "persist"):
            return []
        current_name = current_name or os.path.basename(self.current.boot_dir)
        dirs = self._boot_dirs()
        protected = {current_name}
        for _started, name, _path in reversed(dirs):
            if name != current_name:
                protected.add(name)
                break
        deleted = []
        deletable = [d for d in dirs if d[1] not in protected]
        sizes = {path: self.walk_bytes_func(path) for _started, _name, path in dirs}
        total = sum(sizes.values())
        count = len(dirs)
        retention = max(PROTECTED_BOOTS, int(self.config.retention_boots))
        deadline = time.monotonic() + 20.0
        while deletable:
            free = self.free_mb_func(self.current.root)
            if (total // (1 << 20) <= int(self.config.max_stick_mb) and
                    free >= int(self.config.min_free_mb) and
                    count <= retention):
                break
            if time.monotonic() > deadline:
                break
            _started, name, path = deletable.pop(0)  # oldest first
            if os.path.basename(path) == current_name:
                break
            try:
                root_abs = os.path.abspath(self.current.root)
                path_abs = os.path.abspath(path)
                if os.path.dirname(path_abs) != root_abs:
                    break
                self.rmtree_func(path_abs)
                deleted.append(name)
                total -= sizes.get(path, 0)
                count -= 1
            except OSError:
                break
        self.deleted.extend(deleted)
        return deleted

    # -- status ----------------------------------------------------------
    def status(self):
        if self.current is None:
            return {"kind": None, "path": None}
        return {
            "kind": self.current.kind,
            "path": self.current.boot_dir,
            "root": self.current.root,
            "chosen": self.chosen_kind,
            "degraded": self.current.kind != (self.chosen_kind or self.current.kind),
            "failures": list(self.failures),
            "deleted": list(self.deleted),
        }
