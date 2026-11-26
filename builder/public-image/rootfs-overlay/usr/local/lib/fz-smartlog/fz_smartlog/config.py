# SPDX-License-Identifier: GPL-2.0-or-later
"""Defaults and environment/cmdline overrides for smartlog v3."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import boot_id as read_boot_id, cmdline_words, marker_present, record_full

# Per-stream caps use W6's measured/model numbers where it has them and W4
# sec.14 for the systemd/udev/network/power streams that W6 does not list.
STREAM_CAPS_MB = {
    "kernel": 128,
    "journal": 64,
    "systemd": 16,
    "udev": 16,
    "network": 16,
    "power": 8,
    "terminal": 64,
    "ui": 8,
    "waydroid": 128,
}
PRIORITY = {
    "kernel": 0, "journal": 1, "power": 1, "network": 2, "systemd": 2,
    "udev": 2, "terminal": 3, "ui": 4, "waydroid": 4,
}


def _env_int(env, name, default, low=None, high=None):
    try:
        value = int(str(env.get(name, default)).strip())
    except (TypeError, ValueError):
        value = int(default)
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def _env_bool(env, name, default):
    raw = str(env.get(name, "1" if default else "0")).strip().lower()
    return raw not in ("0", "no", "false", "off", "")


def memtotal_mb(path="/proc/meminfo"):
    try:
        with open(path, "r", encoding="ascii", errors="replace") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


@dataclass
class Config:
    bootmnt: str = "/run/archiso/bootmnt"
    persist: str = "/run/fz-persist"
    ram: str = "/run/fz-smartlog"
    state: str = "/run/fz-smartlog"
    boot_id: str = ""
    cmdline: str = "/proc/cmdline"
    privacy: str = "owner"
    dest_order: tuple = ("stick", "persist", "ram")
    max_boot_mb: int = 550
    soft_boot_mb: int = 300
    max_stick_mb: int = 4608
    retention_boots: int = 8
    min_free_mb: int = 2048
    halt_free_mb: int = 1024
    yellow_free_mb: int = 2560
    ram_cap_mb: int = 64
    segment_mb: int = 8
    sync_ms: int = 1000
    sync_bytes: int = 65536
    journal_max_record_kb: int = 64
    snapshot_schedule: tuple = (45, 150, 400)
    snapshot_period_s: int = 900
    snapshot_max_kb: int = 1024
    snapshot_deadline_s: int = 20
    event_max: int = 20
    event_min_interval_s: int = 30
    record_max_boots: int = 8
    stream_caps_mb: dict = field(default_factory=lambda: dict(STREAM_CAPS_MB))
    marker_ok: bool = False
    record_full: bool = False
    cmdline_list: tuple = ()
    build_id: str = "unknown"
    kernel: str = "unknown"

    @classmethod
    def from_env(cls, environ=None, cmdline_path=None):
        env = dict(os.environ if environ is None else environ)
        cmdline_path = cmdline_path or env.get("FZ_CMDLINE") or "/proc/cmdline"
        try:
            words = tuple(cmdline_words(cmdline_path))
        except OSError:
            words = ()
        bootmnt = env.get("FZ_SMARTLOG_BOOTMNT", "/run/archiso/bootmnt")
        marker = marker_present(bootmnt)
        ram_total = memtotal_mb()
        ram_cap = _env_int(env, "FZ_SMARTLOG_RAM_CAP_MB",
                           max(16, min(64, ram_total // 10 or 64)), 8, 4096)
        privacy = (env.get("FZ_LOG_PRIVACY") or env.get("FZ_SMARTLOG_PRIVACY") or
                   "owner").strip().lower()
        if privacy not in ("owner", "redacted"):
            privacy = "owner"
        caps = dict(STREAM_CAPS_MB)
        for stream in caps:
            caps[stream] = _env_int(
                env, "FZ_SMARTLOG_CAP_%s_MB" % stream.upper(),
                env.get("FZ_SMARTLOG_STREAM_MB", caps[stream]), 1, 8192)
        schedule = env.get("FZ_SMARTLOG_TARGETS", "45 150 400").replace(",", " ").split()
        try:
            schedule = tuple(int(x) for x in schedule)
        except ValueError:
            schedule = (45, 150, 400)
        return cls(
            bootmnt=bootmnt,
            persist=env.get("FZ_SMARTLOG_PERSIST", "/run/fz-persist"),
            ram=env.get("FZ_SMARTLOG_RAM", "/run/fz-smartlog"),
            state=env.get("FZ_SMARTLOG_STATE", "/run/fz-smartlog"),
            boot_id=env.get("FZ_BOOT_ID", "").strip() or read_boot_id(),
            cmdline=cmdline_path,
            privacy=privacy,
            max_boot_mb=_env_int(env, "FZ_SMARTLOG_MAX_BOOT_MB", 550, 1, 65536),
            soft_boot_mb=_env_int(env, "FZ_SMARTLOG_SOFT_BOOT_MB", 300, 1, 65536),
            max_stick_mb=_env_int(env, "FZ_SMARTLOG_MAX_STICK_MB", 4608, 1, 1 << 20),
            retention_boots=_env_int(env, "FZ_SMARTLOG_RETENTION_BOOTS", 8, 2, 1000),
            min_free_mb=_env_int(env, "FZ_SMARTLOG_MIN_FREE_MB", 2048, 0, 1 << 20),
            halt_free_mb=_env_int(env, "FZ_SMARTLOG_HALT_FREE_MB", 1024, 0, 1 << 20),
            yellow_free_mb=_env_int(env, "FZ_SMARTLOG_YELLOW_FREE_MB", 2560, 0, 1 << 20),
            ram_cap_mb=ram_cap,
            segment_mb=_env_int(env, "FZ_LOG_SEGMENT_MB",
                                max(1, _env_int(env, "FZ_LOG_SEGMENT_BYTES", 8 << 20) // (1 << 20)),
                                1, 4096),
            sync_ms=_env_int(env, "FZ_LOG_SYNC_MS", 1000, 50, 60000),
            sync_bytes=_env_int(env, "FZ_LOG_SYNC_BYTES", 65536, 4096, 1 << 30),
            journal_max_record_kb=_env_int(env, "FZ_SMARTLOG_JOURNAL_RECORD_KB", 64, 4, 4096),
            snapshot_schedule=schedule,
            snapshot_period_s=_env_int(env, "FZ_SMARTLOG_PERIOD", 900, 10, 86400),
            snapshot_max_kb=_env_int(env, "FZ_SMARTLOG_SNAP_KB", 1024, 16, 1024 * 1024),
            snapshot_deadline_s=_env_int(env, "FZ_SMARTLOG_DEADLINE", 20, 1, 300),
            event_max=_env_int(env, "FZ_SMARTLOG_EVENT_MAX", 20, 1, 1000),
            event_min_interval_s=_env_int(env, "FZ_SMARTLOG_EVENT_INTERVAL", 30, 0, 86400),
            record_max_boots=_env_int(env, "FZ_SMARTLOG_KEEP_BOOTS", 8, 2, 1000),
            stream_caps_mb=caps,
            marker_ok=marker,
            record_full=record_full(cmdline_path),
            cmdline_list=words,
            build_id=_build_id(env),
            kernel=_kernel(env),
        )

    def cap_bytes(self, stream):
        return int(self.stream_caps_mb.get(stream, STREAM_CAPS_MB.get(stream, 32))) << 20

    def dest_roots(self):
        return {
            "stick": os.path.join(self.bootmnt, "Logs"),
            "persist": os.path.join(self.persist, "fz-logs"),
            "ram": self.ram,
        }

    def active_dest_order(self):
        if not self.marker_ok:
            return ("ram",)
        return self.dest_order


def _build_id(env):
    value = env.get("FZ_BUILD_ID")
    if value:
        return value
    try:
        with open("/etc/os-release", "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("BUILD_ID="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def _kernel(env):
    value = env.get("FZ_KERNEL")
    if value:
        return value
    try:
        return os.uname().release
    except (AttributeError, OSError):
        return "unknown"
