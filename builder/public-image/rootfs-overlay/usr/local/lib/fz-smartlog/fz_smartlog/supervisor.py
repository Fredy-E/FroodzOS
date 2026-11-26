# SPDX-License-Identifier: GPL-2.0-or-later
"""smartlog v3 supervisor: destination state machine, stream workers and events."""
from __future__ import annotations

import collections
import json
import os
import queue
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

from . import VERSION, boot_id as read_boot_id
from .config import Config, PRIORITY
from .dest import ALL_STREAMS, DestManager, Tier
from .index import atomic_write, atomic_write_json, build_index, write_index
from .redact import Redactor
from .writer import DestinationFailed, StreamWriter, utc_iso

KERNEL_CRITICAL = re.compile(
    r"(?i)(Oops|BUG:|Call trace|Kernel panic|Unable to handle|"
    r"soft lockup|hung task|rcu.*stall)")
KERNEL_WARNING = re.compile(r"(?i)(WARNING:|tainted)")
WIFI_ERROR = re.compile(
    r"(?i)(ath12k|wiphy|wpa_supplicant|firmware crash|failed to resume|"
    r"hardware became unavailable)")
STORAGE_ERROR = re.compile(r"(?i)(i/o error|input/output error|read-only file system|no space left)")
EVENT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
KMSG_RE = re.compile(r"^(\d+),(\d+),(\d+),([^;]*);(.*)$", re.S)
DMESG_RE = re.compile(r"^\[\s*([0-9]+(?:\.[0-9]+)?)\]\s?(.*)$")


def _up():
    try:
        with open("/proc/uptime", "r", encoding="ascii", errors="replace") as fh:
            return int(float(fh.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return int(time.monotonic())


def _iso(wall=None):
    return utc_iso(time.time() if wall is None else wall)


def _read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _cmd(cmd, timeout=3, text=True):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=text, timeout=timeout)
        return proc.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def sd_notify(message):
    address = os.environ.get("NOTIFY_SOCKET")
    if not address or not hasattr(socket, "AF_UNIX"):
        return False
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(address)
            sock.sendall(message.encode("utf-8", "replace"))
        finally:
            sock.close()
        return True
    except OSError:
        return False


def _shell_quote(value):
    return "'" + str(value).replace("'", "'\\''") + "'"


class DerivedViews:
    """kernel-warnings.log / journal-errors.log, rotating at 3 MB."""
    LIMIT = 3 << 20

    def __init__(self, smart_dir, redactor):
        self.dir = smart_dir
        self.redactor = redactor
        self.seen = collections.deque(maxlen=20000)
        self.seen_set = set()
        self._lock = threading.Lock()

    def set_dir(self, smart_dir):
        with self._lock:
            self.dir = smart_dir

    def _append(self, name, line):
        path = os.path.join(self.dir, name)
        try:
            if os.path.exists(path) and os.path.getsize(path) >= self.LIMIT:
                old = path[:-4] + ".1.log" if path.endswith(".log") else path + ".1.log"
                try:
                    if os.path.exists(old):
                        os.unlink(old)
                    os.replace(path, old)
                except OSError:
                    pass
            os.makedirs(self.dir, exist_ok=True)
            with open(path, "a", encoding="utf-8", errors="replace", newline="\n") as fh:
                fh.write(line)
        except OSError:
            pass

    def add(self, record):
        message = record.get("MESSAGE")
        if not isinstance(message, str) or not message:
            return
        transport = str(record.get("_TRANSPORT") or "")
        ident = str(record.get("SYSLOG_IDENTIFIER") or "")
        priority = _int(record.get("PRIORITY"), 7)
        mono = record.get("mono")
        key = (round(float(mono), 3) if isinstance(mono, (int, float)) else 0, message[:200])
        with self._lock:
            if key in self.seen_set:
                return
            self.seen.append(key)
            self.seen_set.add(key)
            if len(self.seen) == self.seen.maxlen:
                self.seen_set = set(self.seen)
            text = self.redactor.line(message.replace("\n", " ")).rstrip("\n")
            prefix = "[%s] %s: " % (mono if mono is not None else "?",
                                     ident or "kernel")
            if transport == "kernel" or ident == "kernel":
                if priority <= 4:
                    self._append("kernel-warnings.log", prefix + text + "\n")
            elif priority <= 3:
                self._append("journal-errors.log", prefix + text + "\n")


class Source(threading.Thread):
    def __init__(self, runtime, name):
        super().__init__(name=name, daemon=True)
        self.runtime = runtime
        self.stop_event = threading.Event()
        self.proc = None

    def stop(self):
        self.stop_event.set()
        self._terminate()

    def _terminate(self):
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def sleep(self, seconds):
        self.stop_event.wait(seconds)

    def run(self):
        # Thread entry point: run the source's loop(); a crash is logged and the loop restarted
        # (a recorder must not lose a stream because of one bad record), at most every 2 seconds.
        while not self.stop_event.is_set():
            try:
                self.loop()
                return
            except Exception as exc:  # noqa: BLE001 - keep the recorder alive
                try:
                    self.runtime.marker("SOURCE_CRASH name=%s error=%s: %s" % (
                        self.name, type(exc).__name__, str(exc)[:200]))
                except Exception:  # noqa: BLE001
                    pass
                self.sleep(2.0)

    def emit(self, stream, record):
        return self.runtime.write_stream(stream, record)


class KernelSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "kernel")
        self.fd = None
        self.last_seq = None
        self.last_seq_write = 0.0

    def _handoff(self):
        path = os.path.join(self.runtime.config.state, "kernel.seq")
        value = _read(path).strip()
        return _int(value, 0) if value else 0

    def _open(self):
        path = os.environ.get("FZ_KMSG_FILE", "/dev/kmsg")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        seq = self._handoff()
        if seq:
            try:
                os.lseek(fd, seq, os.SEEK_SET)
            except OSError:
                pass
        self.fd = fd
        return fd

    def _write_seq(self):
        now = time.monotonic()
        if self.last_seq is None or now - self.last_seq_write < 2.0:
            return
        self.last_seq_write = now
        try:
            atomic_write(os.path.join(self.runtime.config.state, "kernel.seq"),
                         ("%d\n" % self.last_seq).encode())
        except OSError:
            pass

    def loop(self):
        try:
            fd = self._open()
        except OSError:
            self._dmesg_fallback()
            return
        while not self.stop_event.is_set():
            try:
                ready, _w, _x = select.select([fd], [], [], 0.5)
            except OSError:
                ready = []
            if not ready:
                continue
            try:
                raw = os.read(fd, 65536)
            except OSError as exc:
                if getattr(exc, "errno", None) in (11, 4):  # EAGAIN / EINTR
                    continue
                break
            if not raw:
                self.sleep(0.2)
                continue
            text = raw.decode("utf-8", "replace").rstrip("\n")
            match = KMSG_RE.match(text)
            if not match:
                continue
            prio, seq, usec, flags, message = match.groups()
            self.last_seq = _int(seq)
            mono = _int(usec) / 1e6
            wall = time.time() - max(0.0, time.monotonic() - mono)
            self.emit("kernel", {
                "ts": _iso(wall), "mono": round(mono, 6), "prio": _int(prio),
                "seq": self.last_seq, "flags": flags.strip(), "msg": message,
            })
            self._write_seq()
        try:
            os.close(fd)
        except OSError:
            pass

    def _dmesg_fallback(self):
        while not self.stop_event.is_set():
            try:
                self.proc = subprocess.Popen(["dmesg", "-w"], stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, text=True,
                                             errors="replace", bufsize=1)
            except OSError:
                self.sleep(5)
                continue
            self.runtime.marker("DMESG_FALLBACK /dev/kmsg unavailable")
            for line in self.proc.stdout:
                if self.stop_event.is_set():
                    break
                line = line.rstrip("\n")
                match = DMESG_RE.match(line)
                mono = float(match.group(1)) if match else time.monotonic()
                message = match.group(2) if match else line
                self.emit("kernel", {
                    "ts": _iso(time.time() - max(0.0, time.monotonic() - mono)),
                    "mono": round(mono, 6), "source": "dmesg", "msg": message,
                })
            self._terminate()
            self.proc = None
            if not self.stop_event.is_set():
                self.runtime.marker("DMESG_FALLBACK restart")
                self.sleep(2)


class JournalSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "journal")
        self.record_cap = max(4096, int(runtime.config.journal_max_record_kb) * 1024)

    def _cap(self, record):
        truncated = False

        def walk(value):
            nonlocal truncated
            if isinstance(value, str):
                if len(value.encode("utf-8", "replace")) > self.record_cap:
                    truncated = True
                    return value.encode("utf-8", "replace")[:self.record_cap].decode(
                        "utf-8", "replace") + "<truncated>"
                return value
            if isinstance(value, list):
                return [walk(v) for v in value]
            if isinstance(value, dict):
                return {k: walk(v) for k, v in value.items()}
            return value

        out = {key: walk(value) for key, value in record.items()}
        if truncated:
            out["fz_truncated"] = True
        return out

    def loop(self):
        while not self.stop_event.is_set():
            if self.runtime.is_paused("journal"):
                self.sleep(0.5)
                continue
            try:
                self.proc = subprocess.Popen(
                    ["journalctl", "-b", "-f", "-o", "json", "--no-pager"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    errors="replace", bufsize=1)
            except OSError:
                self.runtime.marker("JOURNAL_UNAVAILABLE")
                self.sleep(5)
                continue
            for line in self.proc.stdout:
                if self.stop_event.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                record = self._cap(record)
                usec = _int(record.get("__MONOTONIC_TIMESTAMP"), 0)
                mono = usec / 1e6 if usec else time.monotonic()
                rtime = _int(record.get("__REALTIME_TIMESTAMP"), 0)
                record["mono"] = round(mono, 6)
                record["ts"] = _iso(rtime / 1e6 if rtime else
                                    time.time() - max(0.0, time.monotonic() - mono))
                self.emit("journal", record)
            self._terminate()
            self.proc = None
            if not self.stop_event.is_set():
                self.runtime.gap("journal", "journal-restart")
                self.sleep(2)


class LineCommandSource(Source):
    command = ()

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.proc = subprocess.Popen(list(self.command), stdout=subprocess.PIPE,
                                             stderr=subprocess.DEVNULL, text=True,
                                             errors="replace", bufsize=1)
            except OSError:
                self.runtime.marker("%s_UNAVAILABLE" % self.name.upper())
                self.sleep(10)
                continue
            for line in self.proc.stdout:
                if self.stop_event.is_set():
                    break
                record = self.parse(line.rstrip("\n"))
                if record is not None:
                    record.setdefault("ts", _iso())
                    record.setdefault("mono", round(time.monotonic(), 6))
                    self.emit(self.name, record)
            self._terminate()
            self.proc = None
            if not self.stop_event.is_set():
                self.runtime.gap(self.name, "%s-restart" % self.name)
                self.sleep(3)

    def parse(self, line):
        try:
            value = json.loads(line)
        except ValueError:
            return {"raw": line}
        if isinstance(value, dict):
            value.setdefault("_source", self.name)
            return value
        return {"value": value}


class SystemdSource(LineCommandSource):
    def __init__(self, runtime):
        super().__init__(runtime, "systemd")
        self.command = ["busctl", "monitor", "--json=short",
                        "org.freedesktop.systemd1"]


class UdevSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "udev")
        self.block = {}

    def _emit_block(self):
        if not self.block:
            return
        record = dict(self.block)
        self.block = {}
        record["ts"] = _iso()
        record["mono"] = round(time.monotonic(), 6)
        self.emit("udev", record)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.proc = subprocess.Popen(
                    ["udevadm", "monitor", "--udev", "--property"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    errors="replace", bufsize=1)
            except OSError:
                self.runtime.marker("UDEV_UNAVAILABLE")
                self.sleep(10)
                continue
            for line in self.proc.stdout:
                if self.stop_event.is_set():
                    break
                line = line.rstrip("\n")
                if not line:
                    self._emit_block()
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key == "ACTION" and "ACTION" in self.block:
                    self._emit_block()
                if key in ("ACTION", "DEVPATH", "SUBSYSTEM", "DEVNAME", "DEVTYPE",
                           "DRIVER", "SEQNUM") or key.startswith("ID_"):
                    self.block[key] = value
            self._emit_block()
            self._terminate()
            self.proc = None
            if not self.stop_event.is_set():
                self.runtime.gap("udev", "udev-restart")
                self.sleep(3)


class NetworkSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "network")
        self.last = None

    def _state(self):
        interfaces = []
        try:
            names = sorted(os.listdir("/sys/class/net"))
        except OSError:
            names = []
        for name in names:
            base = "/sys/class/net/%s" % name
            interface = {
                "name": name,
                "operstate": _read(os.path.join(base, "operstate")).strip(),
                "carrier": _read(os.path.join(base, "carrier")).strip(),
                "wireless": os.path.isdir(os.path.join(base, "wireless")),
                "address": _read(os.path.join(base, "address")).strip(),
            }
            interfaces.append(interface)
        state = {"kind": "state", "interfaces": interfaces}
        if interfaces:
            nmcli = _cmd(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev"], 3)
            if nmcli.strip():
                state["nmcli"] = [line for line in nmcli.splitlines() if line.strip()]
            rfkill = _cmd(["rfkill", "list"], 3)
            if rfkill.strip():
                state["rfkill"] = rfkill.strip().splitlines()[:20]
        return state

    def loop(self):
        while not self.stop_event.is_set():
            state = self._state()
            key = json.dumps(state, sort_keys=True)
            if key != self.last:
                self.last = key
                state["ts"] = _iso()
                state["mono"] = round(time.monotonic(), 6)
                self.emit("network", state)
            self.sleep(2)


class PowerSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "power")
        self.last = None

    def _state(self):
        base = "/sys/power/suspend_stats"
        stats = {}
        for name in ("success", "fail", "failed_prepare", "failed_suspend",
                     "failed_resume", "last_failed_dev", "last_failed_step"):
            stats[name] = _read(os.path.join(base, name)).strip()
        supplies = []
        try:
            names = sorted(os.listdir("/sys/class/power_supply"))
        except OSError:
            names = []
        for name in names:
            base = os.path.join("/sys/class/power_supply", name)
            supplies.append({
                "name": name,
                "type": _read(os.path.join(base, "type")).strip(),
                "status": _read(os.path.join(base, "status")).strip(),
                "online": _read(os.path.join(base, "online")).strip(),
                "capacity": _read(os.path.join(base, "capacity")).strip(),
            })
        return {"kind": "state", "suspend_stats": stats, "supplies": supplies,
                "mem_sleep": _read("/sys/power/mem_sleep").strip()}

    def loop(self):
        while not self.stop_event.is_set():
            state = self._state()
            key = json.dumps(state, sort_keys=True)
            if key != self.last:
                self.last = key
                state["ts"] = _iso()
                state["mono"] = round(time.monotonic(), 6)
                self.emit("power", state)
            self.sleep(2)


class HeartbeatSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "heartbeat")
        self.beats = 0

    def loop(self):
        while not self.stop_event.is_set():
            self.beats += 1
            self.runtime.write_alive()
            self.sleep(2)


class IndexSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "index")

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.runtime.write_partial_index()
            except Exception as exc:
                self.runtime.marker("INDEX_ERROR %s" % type(exc).__name__)
            self.sleep(5)


class SnapshotSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "snapshot")
        self.seq = 0
        self.targets = list(runtime.config.snapshot_schedule)
        self.next_due = self.targets[0] if self.targets else runtime.config.snapshot_period_s

    def loop(self):
        while not self.stop_event.is_set():
            self.sleep(1)
            if self.stop_event.is_set():
                break
            uptime = _up()
            if uptime < self.next_due:
                continue
            self.seq += 1
            self.runtime.spawn_snapshot(self.seq, "periodic",
                                        uptime=uptime,
                                        deadline=self.runtime.config.snapshot_deadline_s)
            if self.targets:
                self.targets.pop(0)
                if self.targets:
                    self.next_due = self.targets[0]
                else:
                    self.next_due = uptime + self.runtime.config.snapshot_period_s
            else:
                self.next_due = uptime + self.runtime.config.snapshot_period_s


class MonitorSource(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "monitor")
        self.last_failed = None
        self.last_suspend = None
        self.last_wifi = None
        self.last_hot = 0.0

    def _snapshot(self):
        meminfo = {}
        for line in _read("/proc/meminfo").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meminfo[key] = _int(value.split()[0] if value.split() else 0)
        thermal = 0
        try:
            for name in os.listdir("/sys/class/thermal"):
                if not name.startswith("thermal_zone"):
                    continue
                thermal = max(thermal, _int(_read(
                    "/sys/class/thermal/%s/temp" % name)))
        except OSError:
            pass
        failed = []
        text = _cmd(["systemctl", "--failed", "--no-legend"], 8)
        for line in text.splitlines():
            parts = line.strip().split()
            if parts and not parts[0].startswith("●"):
                failed.append(parts[0])
        suspend = {
            "success": _int(_read("/sys/power/suspend_stats/success")),
            "fail": _int(_read("/sys/power/suspend_stats/fail")),
            "failed_resume": _int(_read("/sys/power/suspend_stats/failed_resume")),
            "last_failed_dev": _read("/sys/power/suspend_stats/last_failed_dev").strip(),
            "last_failed_step": _read("/sys/power/suspend_stats/last_failed_step").strip(),
        }
        wifi = {"present": 0, "up": 0}
        try:
            for name in os.listdir("/sys/class/net"):
                if os.path.isdir("/sys/class/net/%s/wireless" % name):
                    wifi["present"] += 1
                    if _read("/sys/class/net/%s/operstate" % name).strip() == "up":
                        wifi["up"] += 1
        except OSError:
            pass
        psi = 0.0
        for line in _read("/proc/pressure/memory").splitlines():
            if line.startswith("some "):
                match = re.search(r"avg10=([0-9.]+)", line)
                if match:
                    psi = float(match.group(1))
        state = {"thermal_mc": thermal, "memavail_kb": meminfo.get("MemAvailable", 0),
                 "memtotal_kb": meminfo.get("MemTotal", 0), "failed": failed,
                 "suspend": suspend, "wifi": wifi, "psi_mem": psi}
        self.runtime.metric_cache.update(state)
        return state

    def loop(self):
        while not self.stop_event.is_set():
            try:
                state = self._snapshot()
            except Exception:
                self.sleep(5)
                continue
            now = time.monotonic()
            if self.last_failed is not None and state["failed"] != self.last_failed:
                self.runtime.enqueue_event("failedunit", "event",
                                           {"failed_units": state["failed"]})
            if self.last_suspend is not None and \
                    state["suspend"]["success"] > self.last_suspend["success"]:
                self.runtime.enqueue_event("resume", "event", {"suspend": state["suspend"]})
            if self.last_wifi is not None and state["wifi"] != self.last_wifi:
                self.runtime.enqueue_event("wifi", "event", {"wifi": state["wifi"]})
            if state["thermal_mc"] >= 75000 and now - self.last_hot >= 600:
                self.last_hot = now
                self.runtime.enqueue_event("hot", "event",
                                           {"max_temp_mc": state["thermal_mc"]})
            if (state["memtotal_kb"] and
                    state["memavail_kb"] * 100 // state["memtotal_kb"] < 8) or \
                    state["psi_mem"] > 10:
                self.runtime.enqueue_event("lowmem", "event",
                                           {"memavail_kb": state["memavail_kb"],
                                            "psi_mem": state["psi_mem"]})
            self.last_failed = state["failed"]
            self.last_suspend = state["suspend"]
            self.last_wifi = state["wifi"]
            self.sleep(10)


class EventEngine(Source):
    def __init__(self, runtime):
        super().__init__(runtime, "events")
        self.queue = queue.Queue(maxsize=1000)
        self.count = 0
        self.last_any = 0.0
        self.last_reason = {}
        self.events = []
        self.lock = threading.Lock()

    def enqueue(self, reason, severity="event", detail=None, critical=False):
        if not EVENT_RE.match(str(reason)):
            return False
        try:
            self.queue.put_nowait((str(reason), severity, detail or {}, bool(critical)))
            return True
        except queue.Full:
            return False

    def loop(self):
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._emit(*item)
            except Exception as exc:
                self.runtime.marker("EVENT_ERROR %s" % type(exc).__name__)

    def _emit(self, reason, severity, detail, critical):
        cfg = self.runtime.config
        now = time.monotonic()
        with self.lock:
            if self.count >= cfg.event_max:
                return
            if now - self.last_reason.get(reason, -1000) < 10:
                return
            if not critical and now - self.last_any < cfg.event_min_interval_s:
                return
            self.count += 1
            self.last_any = now
            self.last_reason[reason] = now
            self.runtime.flush_writers()
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + reason
            path = os.path.join(self.runtime.dest.current.events_dir, stamp)
            suffix = 1
            while os.path.exists(path):
                suffix += 1
                path = os.path.join(self.runtime.dest.current.events_dir,
                                    stamp + "-%d" % suffix)
            try:
                os.makedirs(path, exist_ok=True)
            except OSError:
                return
            event = {"utc": _iso(), "mono": round(now, 3), "reason": reason,
                     "severity": severity, "detail": detail,
                     "boot_id": self.runtime.config.boot_id,
                     "uptime_s": _up(), "dest": self.runtime.dest.current.kind}
            event = self.runtime.redactor.record(event)
            atomic_write_json(os.path.join(path, "event.json"), event)
            atomic_write_json(os.path.join(path, "state.json"),
                              self.runtime.redactor.record(
                                  dict(self.runtime.metric_cache,
                                       where=self.runtime.dest.current.kind)))
            with open(os.path.join(path, "kernel-tail.txt"), "w",
                      encoding="utf-8", errors="replace", newline="\n") as fh:
                for rec in list(self.runtime.kernel_tail):
                    fh.write(json.dumps(self.runtime.redactor.record(rec),
                                        ensure_ascii=False) + "\n")
            with open(os.path.join(path, "journal-tail.jsonl"), "w",
                      encoding="utf-8", errors="replace", newline="\n") as fh:
                for rec in list(self.runtime.journal_tail):
                    fh.write(json.dumps(self.runtime.redactor.record(rec),
                                        ensure_ascii=False) + "\n")
            with open(os.path.join(path, "snapshot.txt"), "w",
                      encoding="utf-8", errors="replace", newline="\n") as fh:
                fh.write("fz-smartlog event snapshot reason=%s uptime_s=%d "
                         "mono=%.3f boot_id=%s where=%s\nSNAPSHOT_PARTIAL reason=event\n" % (
                             reason, _up(), now, self.runtime.config.boot_id,
                             self.runtime.dest.current.kind))
                for key in sorted(self.runtime.metric_cache):
                    fh.write("%s=%s\n" % (key, self.runtime.metric_cache[key]))
            entry = {"utc": event["utc"], "mono": event["mono"], "reason": reason,
                     "dir": os.path.relpath(path, self.runtime.dest.current.boot_dir).replace(
                         os.sep, "/")}
            self.events.append(entry)
            self.runtime.event_log("event: %s (%s)" % (reason, severity))
            self.runtime.marker("EVENT reason=%s severity=%s" % (reason, severity))


class Runtime:
    def __init__(self, config=None):
        self.config = config or Config.from_env()
        self.config.boot_id = self.config.boot_id or read_boot_id()
        self.dest = DestManager(self.config, self.config.boot_id)
        self.started_epoch = time.time()
        self.started_utc = _iso(self.started_epoch)
        self.stop_event = threading.Event()
        self.writers = {}
        self.sources = []
        self.redactor = Redactor(mode=self.config.privacy)
        self.derived = None
        self.events = None
        self.metric_cache = {}
        self.kernel_tail = collections.deque(maxlen=60)
        self.journal_tail = collections.deque(maxlen=80)
        self.gaps = collections.defaultdict(list)
        self.switch_lock = threading.Lock()
        self.switch_requested = None
        self.tier_name = None
        self.current_tier = Tier("green", set(ALL_STREAMS), 7, "startup")
        self.paused = set()
        self.stopped = False
        self.shutdown_done = False
        self.ready = False
        self.index_cache = {}
        self.pruned = []
        self.final_snapshot = None
        self.snapshot_procs = []
        self.snapshot_lock = threading.Lock()

    # -- markers / env ---------------------------------------------------
    def marker(self, text):
        if self.dest.current is None:
            return
        line = "%s %s\n" % (_iso(), text)
        try:
            with open(os.path.join(self.dest.current.boot_dir, "05-writer.log"),
                      "a", encoding="utf-8", errors="replace", newline="\n") as fh:
                fh.write(line)
        except OSError:
            pass

    def event_log(self, text):
        if self.dest.current is None:
            return
        line = "%s up=%s %s\n" % (time.strftime("%H:%M:%S", time.gmtime()),
                                   _up(), text)
        for path in (os.path.join(self.dest.current.smart_dir, "events.log"),
                     os.path.join(self.dest.current.boot_dir, "events.log")):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8", errors="replace",
                          newline="\n") as fh:
                    fh.write(line)
            except OSError:
                pass

    def gap(self, stream, reason):
        now = round(time.monotonic(), 3)
        self.gaps[stream].append({"from": now, "to": now, "reason": reason})

    def build_env(self):
        cap = 32 << 20
        env = {
            "FZ_LOG_DIR": self.dest.current.streams_dir,
            "FZ_LOG_BOOT_DIR": self.dest.current.boot_dir,
            "FZ_LOG_BOOT_ID": self.config.boot_id,
            "FZ_LOG_DEST_KIND": self.dest.current.kind,
            "FZ_LOG_SEGMENT_BYTES": str(self.config.segment_mb << 20),
            "FZ_LOG_SYNC_MS": str(self.config.sync_ms),
            "FZ_LOG_SYNC_BYTES": str(self.config.sync_bytes),
            "FZ_LOG_MAX_STREAM_BYTES": str(cap),
            "FZ_LOG_PRIVACY": self.config.privacy,
            "FZ_LOG_SCHEMA": "3",
            "FZ_LOG_EVENTS_DIR": self.dest.current.events_dir,
        }
        for stream in ("terminal", "ui", "waydroid"):
            env["FZ_LOG_MAX_STREAM_BYTES_%s" % stream.upper()] = str(
                self.config.cap_bytes(stream))
        return env

    def write_env(self):
        env = self.build_env()
        text = "".join("%s=%s\n" % (key, _shell_quote(value)) for key, value in env.items())
        try:
            os.makedirs(self.config.state, exist_ok=True)
            atomic_write(os.path.join(self.config.state, "env"), text.encode("utf-8"))
            try:
                os.chmod(os.path.join(self.config.state, "env"), 0o644)
            except OSError:
                pass
        except OSError:
            pass

    def _write_boot_json(self):
        data = {
            "schema": 3,
            "boot_id": self.config.boot_id,
            "started_utc": self.started_utc,
            "started_epoch": self.started_epoch,
            "cmdline": list(self.config.cmdline_list),
            "build_id": self.config.build_id,
            "kernel": self.config.kernel,
            "marker": bool(self.config.marker_ok),
            "record_full": bool(self.config.record_full),
            "privacy": self.config.privacy,
            "dest_kind": self.dest.current.kind,
            "dest_path": self.dest.current.boot_dir,
        }
        atomic_write_json(os.path.join(self.dest.current.boot_dir, "boot.json"), data)

    def _setup_layout(self):
        dest = self.dest.current
        for path in (dest.boot_dir, dest.smart_dir, dest.streams_dir, dest.events_dir):
            os.makedirs(path, exist_ok=True)
        if self.config.record_full:
            for stream in ("terminal", "ui", "waydroid"):
                os.makedirs(os.path.join(dest.streams_dir, stream), exist_ok=True)
        if self.derived is None:
            self.derived = DerivedViews(
                dest.smart_dir,
                Redactor(key=self.redactor.key, mode=self.config.privacy))
        else:
            self.derived.set_dir(dest.smart_dir)

    # -- writers ---------------------------------------------------------
    def _open_writers(self):
        self.writers = {}
        try:
            for stream in ("kernel", "journal", "systemd", "udev", "network", "power"):
                self.writers[stream] = StreamWriter(
                    stream, base_dir=self.dest.current.streams_dir,
                    max_bytes=self.config.cap_bytes(stream),
                    segment_bytes=self.config.segment_mb << 20,
                    sync_ms=self.config.sync_ms, sync_bytes=self.config.sync_bytes,
                    privacy=self.config.privacy,
                    redactor=Redactor(key=self.redactor.key,
                                      mode=self.config.privacy))
        except DestinationFailed:
            for writer in list(self.writers.values()):
                try:
                    writer.close("open-failed")
                except Exception:
                    pass
            self.writers = {}
            raise
        self.marker("WRITERS_OPEN dir=%s streams=%s" % (
            self.dest.current.streams_dir, ",".join(sorted(self.writers))))

    def _close_writers(self):
        for stream, writer in list(self.writers.items()):
            try:
                writer.close("stop")
            except DestinationFailed:
                pass
            except OSError:
                pass
        self.writers = {}

    def active_paths(self):
        paths = []
        for writer in self.writers.values():
            path = writer.current_path()
            if path:
                paths.append(path)
        return paths

    def is_paused(self, stream):
        return stream in self.paused

    def stream_allowed(self, stream, record=None):
        tier = self.current_tier
        priority = PRIORITY.get(stream, 7)
        if stream == "journal" and record is not None:
            priority = _int(record.get("PRIORITY"), priority)
        return tier.can_write(stream, priority)

    def write_stream(self, stream, record):
        if self.stopped:
            return False
        if not self.stream_allowed(stream, record):
            if stream not in self.paused:
                self.paused.add(stream)
                self.marker("STREAM_PAUSED stream=%s tier=%s" % (stream, self.tier_name))
            return False
        writer = self.writers.get(stream)
        if writer is None:
            return False
        self.paused.discard(stream)
        record.setdefault("ts", _iso())
        record.setdefault("mono", round(time.monotonic(), 6))
        record.setdefault("stream", stream)
        try:
            ok = writer.write(record)
        except DestinationFailed as exc:
            self.request_destination_switch(stream, exc)
            return False
        except OSError:
            return False
        if ok:
            self.on_record(stream, record)
        return ok

    def on_record(self, stream, record):
        if stream == "kernel":
            self.kernel_tail.append(record)
            message = str(record.get("msg") or "")
            if KERNEL_CRITICAL.search(message):
                self.enqueue_event("oops", "critical",
                                   {"message": message[:500],
                                    "mono": record.get("mono")}, critical=True)
            elif KERNEL_WARNING.search(message):
                self.enqueue_event("kernelwarning", "event",
                                   {"message": message[:500],
                                    "mono": record.get("mono")})
            if STORAGE_ERROR.search(message):
                self.enqueue_event("storage", "critical",
                                   {"message": message[:500]}, critical=True)
        elif stream == "journal":
            self.journal_tail.append(record)
            if self.derived:
                self.derived.add(record)
            message = str(record.get("MESSAGE") or "")
            priority = _int(record.get("PRIORITY"), 7)
            if priority <= 4 and WIFI_ERROR.search(message):
                self.enqueue_event("wifi", "event", {"message": message[:500],
                                                     "priority": priority})
            if "coredump" in message.lower() or record.get("SYSLOG_IDENTIFIER") == \
                    "systemd-coredump":
                self.enqueue_event("coredump", "event", {"message": message[:500]})
            if "waydroid" in message.lower() and re.search(r"(?i)(fatal|anr|crash)", message):
                self.enqueue_event("waydroid", "event", {"message": message[:500]})
        elif stream == "power":
            stats = record.get("suspend_stats") or {}
            if isinstance(stats, dict):
                self.metric_cache["suspend_stats"] = stats

    def enqueue_event(self, reason, severity="event", detail=None, critical=False):
        if self.events is not None:
            self.events.enqueue(reason, severity, detail, critical)

    def request_destination_switch(self, stream, exc):
        with self.switch_lock:
            if self.switch_requested is None:
                self.switch_requested = (stream, getattr(exc, "reason", str(exc)))
        self.marker("DEST_FAILED stream=%s reason=%s" % (
            stream, getattr(exc, "reason", str(exc))))

    def _do_switch(self, reason):
        with self.switch_lock:
            request = self.switch_requested
            self.switch_requested = None
        if request is None:
            return
        stream, why = request
        self.marker("DEST_CHANGED from=%s reason=%s stream=%s" % (
            self.dest.current.kind if self.dest.current else "none", why, stream))
        self._stop_sources()
        self._close_writers()
        for name in ("kernel", "journal", "systemd", "udev", "network", "power"):
            self.gap(name, "destination-switch")
        try:
            self.dest.switch(why)
        except Exception:
            self.stopped = True
            return
        self._setup_layout()
        self._write_boot_json()
        self.write_env()
        self.marker("DEST_NEW kind=%s path=%s" % (
            self.dest.current.kind, self.dest.current.boot_dir))
        self._open_writers()
        self._start_sources()
        self.enqueue_event("storage", "critical",
                           {"reason": why, "stream": stream,
                            "dest": self.dest.current.kind}, critical=True)

    # -- heartbeat / index ----------------------------------------------
    def write_alive(self):
        if self.dest.current is None:
            return
        text = "%s up=%s dest=%s\n" % (_iso(), _up(), self.dest.current.kind)
        for path in (os.path.join(self.dest.current.boot_dir, "alive.txt"),
                     os.path.join(self.dest.current.smart_dir, "alive.txt")):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                atomic_write(path, text.encode())
            except OSError:
                pass

    def _index(self, complete=False):
        dest = self.dest.current
        return build_index(
            dest.boot_dir, boot_id=self.config.boot_id,
            started_utc=self.started_utc, complete=complete,
            dest_kind=dest.kind, dest_path=dest.boot_dir,
            destinations=[{"kind": dest.kind, "path": dest.boot_dir, "writable": True}],
            gaps=self.gaps, active_paths=[] if complete else self.active_paths(),
            outcome="clean" if complete else "unknown",
            cmdline=self.config.cmdline_list, build_id=self.config.build_id,
            kernel=self.config.kernel, pruned=self.pruned,
            cache=self.index_cache, ended_utc=_iso() if complete else None)

    def write_partial_index(self):
        index = self._index(complete=False)
        write_index(self.dest.current.boot_dir, index, partial=True)

    # -- snapshots -------------------------------------------------------
    def _child_env(self):
        env = dict(os.environ)
        package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        current = env.get("PYTHONPATH")
        env["PYTHONPATH"] = package + (os.pathsep + current if current else "")
        env.update(self.build_env())
        if self.config.privacy == "redacted":
            # Keep pseudonyms stable between the supervisor and the snapshot
            # process; the key is passed in memory only, never written down.
            env["FZ_REDACT_KEY"] = self.redactor.key.hex()
        return env

    def spawn_snapshot(self, seq, reason, uptime=None, deadline=None, wait=False):
        if self.dest.current is None:
            return None
        cmd = [sys.executable, "-B", "-m", "fz_smartlog.snapshot",
               "--dest", self.dest.current.boot_dir,
               "--boot-id", self.config.boot_id,
               "--where", self.dest.current.kind,
               "--reason", reason, "--seq", str(seq),
               "--deadline", str(deadline or self.config.snapshot_deadline_s),
               "--max-kb", str(self.config.snapshot_max_kb),
               "--privacy", self.config.privacy]
        if uptime is not None:
            cmd.extend(["--uptime", str(int(uptime))])
        nice = shutil.which("nice") if hasattr(shutil, "which") else None
        if nice:
            cmd = [nice, "-n", "10"] + cmd
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    env=self._child_env())
        except OSError:
            self.marker("SNAPSHOT_SPAWN_FAILED seq=%s" % seq)
            return None
        with self.snapshot_lock:
            self.snapshot_procs.append(proc)
        if wait:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
        return proc

    def _stop_snapshots(self):
        with self.snapshot_lock:
            procs = list(self.snapshot_procs)
            self.snapshot_procs = []
        for proc in procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except OSError:
                    pass
        for proc in procs:
            try:
                proc.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    proc.kill()
                except OSError:
                    pass

    # -- sources ---------------------------------------------------------
    def _start_sources(self):
        events = EventEngine(self)
        self.events = events
        self.sources = [
            KernelSource(self), JournalSource(self), SystemdSource(self),
            UdevSource(self), NetworkSource(self), PowerSource(self),
            HeartbeatSource(self), MonitorSource(self), events,
            IndexSource(self), SnapshotSource(self),
        ]
        for source in self.sources:
            source.start()

    def _stop_sources(self):
        for source in self.sources:
            try:
                source.stop()
            except Exception:
                pass
        for source in self.sources:
            if source.is_alive():
                source.join(timeout=2.0)
        self.sources = []
        self.events = None
        self._stop_snapshots()

    def flush_writers(self):
        for writer in list(self.writers.values()):
            try:
                writer.flush()
            except DestinationFailed:
                pass
            except OSError:
                pass

    def _check_budget(self):
        tier = self.dest.tier()
        self.current_tier = tier
        if tier.name != self.tier_name:
            self.tier_name = tier.name
            self.marker("BUDGET_TIER tier=%s allowed=%s reason=%s free_mb=%d" % (
                tier.name, ",".join(sorted(tier.allowed)), tier.reason,
                self.dest.free_mb()))
            if tier.name == "halt":
                self.marker("BUDGET_EXHAUSTED reason=%s" % tier.reason)
                self.request_destination_switch("budget", DestinationFailed(
                    "free-space:%s" % tier.reason))
        for stream in ("terminal", "ui", "waydroid", "network", "systemd", "udev"):
            if not tier.can_write(stream) and stream not in self.paused:
                self.paused.add(stream)
                self.marker("STREAM_PAUSED stream=%s tier=%s" % (stream, tier.name))
            elif tier.can_write(stream) and stream in self.paused:
                self.paused.discard(stream)
                self.marker("STREAM_RESUMED stream=%s tier=%s" % (stream, tier.name))
        if tier.name == "halt" and "journal" not in self.paused:
            self.paused.add("journal")

    # -- lifecycle -------------------------------------------------------
    def start(self):
        self.dest.choose_initial()
        self._setup_layout()
        self._write_boot_json()
        self.write_env()
        self.marker("start version=%s where=%s dest=%s pid=%d" % (
            VERSION, self.dest.current.kind, self.dest.current.boot_dir, os.getpid()))
        self.event_log("start where=%s dest=%s pid=%d version=3" % (
            self.dest.current.kind, self.dest.current.boot_dir, os.getpid()))
        try:
            self.pruned = self.dest.prune(os.path.basename(self.dest.current.boot_dir))
            for name in self.pruned:
                self.marker("PRUNED %s" % name)
        except Exception:
            self.pruned = []
        for _attempt in range(2):
            try:
                self._open_writers()
                break
            except DestinationFailed as exc:
                self.marker("WRITER_OPEN_FAILED reason=%s" % exc.reason)
                try:
                    self.dest.switch(exc.reason)
                except Exception:
                    self.stopped = True
                    raise
                self._setup_layout()
                self._write_boot_json()
                self.write_env()
        else:
            raise DestinationFailed("all-writers-failed")
        self.write_partial_index()
        self._start_sources()
        self.write_alive()
        try:
            os.makedirs(self.config.state, exist_ok=True)
            atomic_write(os.path.join(self.config.state, "ready"),
                         ("%s\n" % self.config.boot_id).encode())
        except OSError:
            pass
        self.ready = True
        sd_notify("READY=1\nSTATUS=smartlog v3 recording")
        self.marker("READY")

    def run(self):
        self.start()
        last_watchdog = 0.0
        last_budget = 0.0
        last_reprobe = 0.0
        while not self.stop_event.is_set():
            self.stop_event.wait(1.0)
            now = time.monotonic()
            if now - last_watchdog >= 10:
                last_watchdog = now
                sd_notify("WATCHDOG=1")
            if now - last_budget >= 5:
                last_budget = now
                try:
                    self._check_budget()
                except Exception:
                    pass
            if now - last_reprobe >= 30:
                last_reprobe = now
                try:
                    for kind in self.dest.reprobe_failed():
                        self.marker("DEST_AVAILABLE kind=%s (spool copy not switched mid-boot)" % kind)
                except Exception:
                    pass
            with self.switch_lock:
                requested = self.switch_requested is not None
            if requested:
                self._do_switch("destination-failed")
                if self.stopped:
                    break
        self.shutdown()
        return 0

    def stop(self):
        self.stop_event.set()

    def shutdown(self):
        if self.shutdown_done:
            return
        self.shutdown_done = True
        self.stopped = True
        sd_notify("STOPPING=1\nSTATUS=final flush")
        self.marker("STOP begin")
        self._stop_sources()
        self.flush_writers()
        try:
            dest = self.dest.current
            if dest is not None:
                self.spawn_snapshot(999, "final", uptime=_up(), deadline=5, wait=True)
        except Exception:
            pass
        self._close_writers()
        try:
            dest = self.dest.current
            index = self._index(complete=True)
            write_index(dest.boot_dir, index, partial=False)
            self.marker("STOP complete index.json")
        except Exception as exc:
            self.marker("STOP_INDEX_ERROR %s" % type(exc).__name__)
        try:
            self.write_alive()
            os.unlink(os.path.join(self.config.state, "ready"))
        except OSError:
            pass
        self.marker("STOP end")
        sd_notify("STOPPING=1\nSTATUS=stopped")

    def status(self):
        current = self.dest.status()
        return {
            "schema": 3,
            "version": VERSION,
            "boot_id": self.config.boot_id,
            "marker": bool(self.config.marker_ok),
            "record_full": bool(self.config.record_full),
            "privacy": self.config.privacy,
            "dest": current,
            "env_path": os.path.join(self.config.state, "env"),
            "ready": os.path.exists(os.path.join(self.config.state, "ready")),
            "started_utc": self.started_utc,
            "streams": sorted(self.writers),
        }


def run_supervisor(config=None):
    runtime = Runtime(config)
    runtime.config.boot_id = runtime.config.boot_id or read_boot_id()

    def _stop(_signum=None, _frame=None):
        runtime.stop()

    def _manual(_signum=None, _frame=None):
        runtime.enqueue_event("manual", "event", {"source": "SIGUSR1"}, critical=True)
        runtime.spawn_snapshot(0, "manual", uptime=_up(),
                               deadline=runtime.config.snapshot_deadline_s)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, _manual)
    return runtime.run()
