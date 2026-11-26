# SPDX-License-Identifier: GPL-2.0-or-later
"""Snapshots, the legacy human views and summary.json.

The collectors are ports of the useful v2 shell collectors, executed in a
separate process with a global deadline.  File names and the history.tsv first
16 columns are unchanged for old readers.
"""
from __future__ import annotations

import argparse
import glob as globmod
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time

from .index import atomic_write, atomic_write_json
from .redact import Redactor

MAX_SECTION = 96 * 1024
HISTORY_COLUMNS = (
    "seq", "uptime", "utc", "maxtemp_mc", "memavail_kb", "load1",
    "battery_capacity", "battery_voltage", "backlight", "failed_units",
    "coredumps", "deferred", "remoteproc", "sound_cards", "kernel_errors",
    "oops_like",
)
HISTORY_EXTRA = (
    "mono", "psi_io", "wifi_state", "suspend_fail", "waydroid_lines", "dest",
    "degraded",
)
ANDROID_NOISE = re.compile(
    r"(?i)(libprocessgroup|ueventd|servicemanager|healthd|\blogd\b|libbpf|"
    r"waydroid|gbinder|\binit:\s|uid_\d+|failed to make and chown|"
    r"failed to set task profiles|read-only file system.*(?:cgroup|uid_\d+))")
OOPS_RE = re.compile(
    r"(?i)(Oops|BUG:|Call trace|soft lockup|hung task|Unable to handle|"
    r"Kernel panic|rcu.*stall)")
SENSITIVE_LINE = re.compile(r"(?i)(psk|passphrase|password|private key)")


def _sanitize_tsv(value):
    return str(value if value is not None else "").replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _now_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _time_utc():
    return time.strftime("%H:%M:%S", time.gmtime())


def _uptime():
    try:
        with open("/proc/uptime", "r", encoding="ascii", errors="replace") as fh:
            return int(float(fh.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return int(time.monotonic())


class Snapshotter:
    def __init__(self, dest_dir, boot_id="unknown", where="ram", root="/",
                 runner=None, clock=time.monotonic, max_kb=1024, deadline_s=20,
                 privacy="owner", host=None):
        self.dest_dir = os.path.abspath(dest_dir)
        self.smart_dir = os.path.join(self.dest_dir, "smart")
        self.boot_id = boot_id
        self.where = where
        self.root = os.path.abspath(root)
        self.clock = clock
        self.max_bytes = max(1, int(max_kb)) * 1024
        self.deadline_s = max(1, int(deadline_s))
        self.privacy = (privacy or "owner").lower()
        self.redactor = Redactor(mode=self.privacy)
        self.host = (self.root == os.path.abspath(os.sep)) if host is None else host
        self.runner = runner
        self.deadline = 0.0
        self.deadline_hit = False
        os.makedirs(self.smart_dir, exist_ok=True)

    # -- io helpers ------------------------------------------------------
    def _path(self, rel):
        return os.path.join(self.root, rel.lstrip("/"))

    def _read(self, rel, default=""):
        try:
            with open(self._path(rel), "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return default

    def _glob(self, pattern):
        return sorted(globmod.glob(self._path(pattern)))

    def _stat_mb(self, rel):
        try:
            st = os.statvfs(self._path(rel))
            return (st.f_bavail * st.f_frsize) // (1 << 20), (st.f_blocks * st.f_frsize) // (1 << 20)
        except (AttributeError, OSError):
            return 0, 0

    def remaining(self):
        return max(0.0, self.deadline - self.clock())

    def _run(self, cmd, timeout=5):
        if self.runner is not None:
            try:
                return str(self.runner(cmd, timeout) or "")
            except Exception:
                return ""
        if not self.host:
            return ""
        if self.deadline and self.remaining() <= 0.05:
            return ""
        if self.deadline:
            timeout = max(0.2, min(float(timeout), self.remaining()))
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                  errors="replace", env=env)
            out = (proc.stdout or "") + (proc.stderr or "")
            return out.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def _have(self, name):
        return self.host and shutil.which(name) is not None

    # -- individual data sources ----------------------------------------
    def _meminfo(self):
        data = {}
        for line in self._read("/proc/meminfo").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[key] = _int(value.split()[0] if value.split() else 0)
        return data

    def _thermal(self):
        best = 0
        entries = []
        for path in self._glob("/sys/class/thermal/thermal_zone*/temp"):
            value = _int(self._read(path))
            zone = os.path.basename(os.path.dirname(path))
            ztype = self._read(os.path.join(os.path.dirname(path), "type")).strip()
            entries.append((value, zone, ztype))
            best = max(best, value)
        entries.sort(reverse=True)
        return best, entries

    def _battery(self):
        for path in self._glob("/sys/class/power_supply/*"):
            if self._read(os.path.join(path, "type")).strip() == "Battery":
                return path
        return None

    def _failed_units(self):
        out = self._run(["systemctl", "--failed", "--no-legend"], 8)
        units = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("●"):
                continue
            parts = line.split()
            if parts:
                units.append(parts[0])
        return units

    def _kernel_counts(self):
        errors = warnings = oops = noise = 0
        err_text = self._run(["dmesg", "--level=err,crit,alert,emerg"], 5)
        if not err_text:
            err_text = self._run(["journalctl", "-k", "-p", "err", "-o", "cat",
                                  "--no-pager", "-q", "-n", "2000"], 5)
        for line in err_text.splitlines():
            if not line.strip():
                continue
            if ANDROID_NOISE.search(line):
                noise += 1
            else:
                errors += 1
        warn_text = self._run(["dmesg", "--level=warn"], 5)
        warnings = sum(1 for line in warn_text.splitlines() if line.strip())
        full = self._run(["dmesg"], 6)
        oops = sum(1 for line in full.splitlines() if OOPS_RE.search(line))
        return {"errors": errors, "warnings": warnings, "oops_like": oops,
                "android_noise": noise,
                "tainted": _int(self._read("/proc/sys/kernel/tainted"))}

    def _suspend(self):
        base = "/sys/power/suspend_stats"
        names = ("success", "fail", "failed_prepare", "failed_suspend",
                 "failed_resume", "last_failed_dev", "last_failed_step")
        out = {}
        for name in names:
            value = self._read(os.path.join(base, name)).strip()
            out[name] = value
        return out

    def _wifi(self):
        interfaces = []
        for path in self._glob("/sys/class/net/*/wireless"):
            interfaces.append(os.path.basename(os.path.dirname(path)))
        up = 0
        for iface in interfaces:
            state = self._read("/sys/class/net/%s/operstate" % iface).strip()
            if state == "up":
                up += 1
        associated = "no"
        for iface in interfaces:
            text = self._run(["iw", "dev", iface, "link"], 3)
            if "Connected to" in text:
                associated = "yes"
                break
        if interfaces and associated == "no" and self._have("nmcli"):
            text = self._run(["nmcli", "-t", "-f", "DEVICE,STATE", "dev"], 3)
            for line in text.splitlines():
                if line.endswith(":connected"):
                    associated = "yes"
                    break
        last_error = "none"
        if self.host:
            text = self._run(
                ["journalctl", "-b", "-p", "err", "-o", "cat", "--no-pager", "-q",
                 "-n", "5", "-g", "ath12k|wifi|wpa_supplicant|NetworkManager"], 4)
            for line in reversed(text.splitlines()):
                if line.strip():
                    last_error = self.redactor.line(line.strip()).rstrip("\n")[:200]
                    break
        return {"present": len(interfaces), "up": up,
                "associated": associated, "last_error": last_error}

    def _waydroid(self):
        state = self._run(["systemctl", "is-active", "waydroid-container"], 3).strip() or "unknown"
        lines = errors = 0
        stream_dir = os.path.join(self.dest_dir, "streams", "waydroid")
        try:
            for name in sorted(os.listdir(stream_dir)):
                if not name.endswith(".jsonl"):
                    continue
                try:
                    with open(os.path.join(stream_dir, name), "r",
                              encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            if not line.strip():
                                continue
                            lines += 1
                            if re.search(r"(?i)(fatal|error|anr|crash)", line):
                                errors += 1
                except OSError:
                    continue
        except OSError:
            pass
        return {"state": state, "lines": lines, "errors": errors}

    # -- metrics ---------------------------------------------------------
    def metrics(self):
        mem = self._meminfo()
        maxtemp, _entries = self._thermal()
        battery = self._battery()
        bcap = bvolt = bstatus = ben = bef = bed = ""
        if battery:
            bcap = self._read(os.path.join(battery, "capacity")).strip()
            bvolt = self._read(os.path.join(battery, "voltage_now")).strip()
            bstatus = self._read(os.path.join(battery, "status")).strip()
            ben = self._read(os.path.join(battery, "energy_now")).strip()
            bef = self._read(os.path.join(battery, "energy_full")).strip()
            bed = self._read(os.path.join(battery, "energy_full_design")).strip()
            if not bcap and _int(ben) and _int(bef) > 0:
                bcap = str(_int(ben) * 100 // _int(bef))
        ac = ""
        for path in self._glob("/sys/class/power_supply/*ac*/online") + \
                self._glob("/sys/class/power_supply/AC*/online"):
            ac = self._read(path).strip()
            if ac:
                break
        backlight = ""
        values = [self._read(p).strip() for p in self._glob("/sys/class/backlight/*/actual_brightness")]
        maxima = [self._read(p).strip() for p in self._glob("/sys/class/backlight/*/max_brightness")]
        if values:
            backlight = "%s/%s" % (values[0], maxima[0] if maxima else "?")
        failed = self._failed_units()
        kernel = self._kernel_counts()
        suspend = self._suspend()
        wifi = self._wifi()
        waydroid = self._waydroid()
        coredumps = 0
        if self.host and self._have("coredumpctl"):
            coredumps = sum(1 for line in self._run(
                ["coredumpctl", "list", "--no-pager", "-q"],
                min(5, max(0.2, self.remaining()))).splitlines() if line.strip())
        remotes = []
        for path in self._glob("/sys/class/remoteproc/*"):
            remotes.append("%s:%s" % (self._read(os.path.join(path, "name")).strip(),
                                      self._read(os.path.join(path, "state")).strip()))
        running = sum(1 for item in remotes if item.endswith(("running", "attached")))
        root_avail, _root_total = self._stat_mb("/")
        root_used_pct = ""
        try:
            st = os.statvfs(self._path("/"))
            total = st.f_blocks or 1
            root_used_pct = str(int((st.f_blocks - st.f_bfree) * 100 / total))
        except (AttributeError, OSError):
            pass
        psi_io = ""
        psi_mem = ""
        for line in self._read("/proc/pressure/io").splitlines():
            if line.startswith("some "):
                match = re.search(r"avg10=([0-9.]+)", line)
                if match:
                    psi_io = match.group(1)
        for line in self._read("/proc/pressure/memory").splitlines():
            if line.startswith("some "):
                match = re.search(r"avg10=([0-9.]+)", line)
                if match:
                    psi_mem = match.group(1)
        health = ""
        if _int(bed) > 0 and _int(bef) > 0:
            health = str(_int(bef) * 100 // _int(bed))
        m = {
            "uptime": str(_uptime()),
            "mono": "%.3f" % time.monotonic(),
            "utc": _now_utc(),
            "maxtemp_mc": str(maxtemp),
            "memavail_kb": str(mem.get("MemAvailable", 0)),
            "memtotal_kb": str(mem.get("MemTotal", 0)),
            "load1": (self._read("/proc/loadavg").split() or [""])[0],
            "rootuse_pct": root_used_pct,
            "battery_capacity": bcap,
            "battery_voltage": bvolt,
            "battery_status": bstatus,
            "battery_energy_now": ben,
            "battery_energy_full": bef,
            "battery_energy_design": bed,
            "battery_health_pct": health,
            "ac_online": ac,
            "backlight": backlight,
            "failed_units": str(len(failed)),
            "failed_unit_names": ",".join(failed),
            "coredumps": str(coredumps),
            "deferred": str(len(self._read("/sys/kernel/debug/devices_deferred").splitlines())),
            "remoteproc_running": "%d/%d" % (running, len(remotes)),
            "remoteproc_states": " ".join(remotes),
            "sound_cards": str(self._read("/proc/asound/cards").count("[")),
            "kernel_errors": str(kernel["errors"]),
            "kernel_warnings": str(kernel["warnings"]),
            "android_noise": str(kernel["android_noise"]),
            "oops_like": str(kernel["oops_like"]),
            "tainted": str(kernel["tainted"]),
            "psi_mem_some10": psi_mem,
            "psi_io": psi_io,
            "suspend_ok": suspend.get("success") or "0",
            "suspend_fail": suspend.get("fail") or "0",
            "failed_prepare": suspend.get("failed_prepare") or "0",
            "failed_suspend": suspend.get("failed_suspend") or "0",
            "failed_resume": suspend.get("failed_resume", "0") or "0",
            "last_failed_dev": suspend.get("last_failed_dev", "") or "none",
            "last_failed_step": suspend.get("last_failed_step", "") or "none",
            "pd_mapper": "1" if "qcom_pd_mapper" in self._read("/proc/modules") else "0",
            "wifi_ifaces": str(wifi["present"]),
            "wifi_up": str(wifi["up"]),
            "wifi_associated": wifi["associated"],
            "wifi_last_error": wifi["last_error"],
            "waydroid_lines": str(waydroid["lines"]),
            "waydroid_errors": str(waydroid["errors"]),
            "waydroid_state": waydroid["state"],
            "dest": self.where,
            "degraded": "yes" if self.where != "stick" else "no",
            "root_avail_mb": str(root_avail),
        }
        return m

    # -- collectors ------------------------------------------------------
    def _skip(self, title):
        return "\n== %s\nSKIPPED reason=deadline\n" % title

    def c_system(self):
        if self.remaining() < 0.5:
            return self._skip("system")
        out = ["\n== system\n"]
        try:
            uname = os.uname()
            out.append("%s %s %s %s\n" % (uname.sysname, uname.nodename, uname.release, uname.machine))
        except AttributeError:
            out.append("uname unavailable\n")
        out.append(self._read("/proc/cmdline").strip() + "\n")
        out.append(self._read("/proc/loadavg").strip() + "\n")
        for line in self._read("/proc/meminfo").splitlines():
            if line.split(":")[0] in ("MemTotal", "MemFree", "MemAvailable", "Buffers",
                                       "Cached", "SwapTotal", "SwapFree", "Dirty",
                                       "Writeback", "Shmem", "Slab", "CommitLimit",
                                       "Committed_AS"):
                out.append(line + "\n")
        for line in self._read("/etc/os-release").splitlines():
            if line.split("=")[0] in ("PRETTY_NAME", "BUILD_ID", "VERSION_ID"):
                out.append(line + "\n")
        out.append("\n== pressure stall (PSI)\n")
        for name in ("cpu", "memory", "io"):
            first = self._read("/proc/pressure/%s" % name).splitlines()
            out.append("%s: %s\n" % (name, first[0] if first else ""))
        if self.remaining() > 6 and self._have("systemd-analyze"):
            out.append("\n== time and boot\n")
            out.append(self._run(["systemd-analyze", "time"], min(5, self.remaining())) + "\n")
            out.append(self._run(["systemd-analyze", "blame"], min(5, self.remaining()))[:4000] + "\n")
            out.append(self._run(["systemd-analyze", "critical-chain"], min(5, self.remaining()))[:4000] + "\n")
        out.append("\n== machine (once is enough, cheap)\n")
        for name in ("sys_vendor", "product_name", "product_version", "product_family",
                     "bios_vendor", "bios_version", "bios_date", "board_name"):
            value = self._read("/sys/class/dmi/id/%s" % name).strip()
            if value:
                out.append("%s=%s\n" % (name, value))
        model = self._read("/proc/device-tree/model").replace("\0", " ").strip()
        if model:
            out.append("dt model=%s\n" % model)
        if self.remaining() > 2 and self._have("lscpu"):
            out.append(self._run(["lscpu"], min(5, self.remaining()))[:4000] + "\n")
        return "".join(out)

    def c_storage(self):
        if self.remaining() < 0.5:
            return self._skip("storage")
        out = ["\n== storage\n"]
        for path in ("/", "/run", "/tmp", "/run/archiso/bootmnt"):
            avail, total = self._stat_mb(path)
            out.append("%s avail=%dMB total=%dMB\n" % (path, avail, total))
        if self._have("lsblk"):
            out.append(self._run(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT,RO"],
                                 min(5, self.remaining())) + "\n")
        for path in self._glob("/sys/block/*/stat"):
            out.append("%s stat=%s\n" % (os.path.basename(os.path.dirname(path)),
                                          self._read(path).strip()))
        out.append("\n== mounts\n")
        for line in self._read("/proc/mounts").splitlines():
            parts = line.split()
            if len(parts) > 2 and parts[1] in ("/", "/run", "/tmp", "/boot", "/efi",
                                               "/run/archiso/bootmnt"):
                out.append(line + "\n")
        out.append("\n== swap and zram\n")
        out.append("\n".join(self._read("/proc/swaps").splitlines()[:5]) + "\n")
        return "".join(out)

    def c_thermal_cpu(self):
        if self.remaining() < 0.5:
            return self._skip("thermal")
        _best, entries = self._thermal()
        out = ["\n== thermal zones (millidegrees, hottest first)\n"]
        for value, zone, ztype in entries[:14]:
            out.append("%s %s %s\n" % (zone, ztype, value))
        out.append("\n== cooling devices\n")
        for path in self._glob("/sys/class/thermal/cooling_device*")[:10]:
            out.append("%s %s cur=%s max=%s\n" % (
                os.path.basename(path), self._read(os.path.join(path, "type")).strip(),
                self._read(os.path.join(path, "cur_state")).strip(),
                self._read(os.path.join(path, "max_state")).strip()))
        out.append("\n== cpu frequency, governor, idle\n")
        for path in self._glob("/sys/devices/system/cpu/cpufreq/policy*"):
            out.append("%s cur=%s min=%s max=%s gov=%s\n" % (
                os.path.basename(path),
                self._read(os.path.join(path, "scaling_cur_freq")).strip(),
                self._read(os.path.join(path, "cpuinfo_min_freq")).strip(),
                self._read(os.path.join(path, "cpuinfo_max_freq")).strip(),
                self._read(os.path.join(path, "scaling_governor")).strip()))
        out.append("online=%s offline=%s\n" % (
            self._read("/sys/devices/system/cpu/online").strip(),
            self._read("/sys/devices/system/cpu/offline").strip()))
        out.append("\n== interrupts (top 15 by count)\n")
        rows = []
        for line in self._read("/proc/interrupts").splitlines()[1:]:
            parts = line.split()
            total = sum(_int(p) for p in parts[1:] if p.isdigit())
            rows.append((total, line[:140]))
        for total, line in sorted(rows, reverse=True)[:15]:
            out.append(line + "\n")
        return "".join(out)

    def c_power(self):
        if self.remaining() < 0.5:
            return self._skip("power")
        out = ["\n== power supplies (raw sysfs)\n"]
        attrs = ("type", "status", "present", "online", "capacity", "capacity_level",
                 "voltage_now", "voltage_min_design", "current_now", "charge_now",
                 "charge_full", "charge_full_design", "energy_now", "energy_full",
                 "energy_full_design", "power_now", "health", "technology",
                 "manufacturer", "model_name", "usb_type")
        for path in self._glob("/sys/class/power_supply/*"):
            out.append("-- %s\n" % path)
            for name in attrs:
                value = self._read(os.path.join(path, name)).strip()
                if value:
                    out.append("%s=%s\n" % (name, value))
        if self._have("upower") and self.remaining() > 3:
            out.append("\n== upower\n" + self._run(["upower", "-d"], min(6, self.remaining())) + "\n")
        if self._have("powerprofilesctl"):
            out.append("power profile=%s\n" % self._run(["powerprofilesctl", "get"], 3))
        if self._have("systemd-inhibit"):
            out.append("\n== inhibitors\n" + self._run(["systemd-inhibit", "--list", "--no-pager"],
                                                       min(4, self.remaining())) + "\n")
        out.append("\n== powerdevil settings in effect\n")
        out.append("\n".join(line for line in self._read("/etc/xdg/powerdevilrc").splitlines()
                             if not line.startswith("#"))[:3000] + "\n")
        out.append("\n== backlight and keyboard light\n")
        for path in self._glob("/sys/class/backlight/*") + self._glob("/sys/class/leds/*kbd*"):
            out.append("-- %s\n" % path)
            for name in ("brightness", "max_brightness", "actual_brightness", "type",
                         "bl_power", "scale"):
                value = self._read(os.path.join(path, name)).strip()
                if value:
                    out.append("%s=%s\n" % (name, value))
        out.append("\n== PWM (duty and period)\n")
        out.append(self._read("/sys/kernel/debug/pwm")[:4000] + "\n")
        out.append("\n== power domains and regulators (debugfs, trimmed)\n")
        out.append(self._read("/sys/kernel/debug/pm_genpd/pm_genpd_summary")[:4000] + "\n")
        out.append(self._read("/sys/kernel/debug/regulator/regulator_summary")[:4000] + "\n")
        return "".join(out)

    def c_dsp(self):
        if self.remaining() < 0.5:
            return self._skip("dsp")
        out = ["\n== DSP / remoteproc (battery and audio depend on the ADSP)\n"]
        for path in self._glob("/sys/class/remoteproc/*"):
            out.append("%s name=%s state=%s firmware=%s\n" % (
                os.path.basename(path),
                self._read(os.path.join(path, "name")).strip(),
                self._read(os.path.join(path, "state")).strip(),
                self._read(os.path.join(path, "firmware")).strip()))
        out.append("\n== devices waiting for a driver or supplier\n")
        out.append(self._read("/sys/kernel/debug/devices_deferred")[:6000] + "\n")
        out.append("\n== device links that are not active yet\n")
        for path in self._glob("/sys/class/devlink/*"):
            status = self._read(os.path.join(path, "status")).strip()
            if status and status not in ("active", "consumer probing"):
                out.append("%s  %s\n" % (status, os.path.basename(path)))
        out.append("\n== interconnect (summary head)\n")
        out.append(self._read("/sys/kernel/debug/interconnect/interconnect_summary")[:4000] + "\n")
        out.append("\n== drivers bound to qcom platforms\n")
        for name in ("qnoc-x1e80100", "qcom_q6v5_pas", "qcom_pmic_glink", "qcom,battmgr",
                     "pmic_glink_altmode", "ucsi_glink", "qcom-pdr", "qcom_pd_mapper"):
            path = "/sys/bus/platform/drivers/%s" % name
            if os.path.isdir(self._path(path)):
                entries = [e for e in os.listdir(self._path(path))
                           if e not in ("bind", "unbind", "uevent", "module")]
                out.append("-- driver %s: %s\n" % (name, " ".join(entries[:40])))
        out.append("\n== firmware files present for this machine\n")
        for rel in ("/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3",
                    "/usr/lib/firmware/qcom"):
            try:
                out.append("%s: %s\n" % (rel, " ".join(sorted(os.listdir(self._path(rel)))[:30])))
            except OSError:
                pass
        out.append("\n== qrtr and rpmsg\n")
        if self._have("qrtr-lookup"):
            out.append(self._run(["qrtr-lookup"], 4) + "\n")
        try:
            out.append("rpmsg: %s\n" % " ".join(sorted(os.listdir(self._path("/sys/bus/rpmsg/devices")))[:20]))
        except OSError:
            pass
        return "".join(out)

    def c_kernel(self):
        if self.remaining() < 0.5:
            return self._skip("kernel")
        out = ["\n== kernel messages: warnings and errors since boot\n"]
        out.append(self._run(["dmesg", "--level=emerg,alert,crit,err,warn",
                              "--time-format=reltime"], min(8, self.remaining()))[-12000:] + "\n")
        out.append("\n== kernel messages about hardware subsystems\n")
        text = self._run(["dmesg", "--time-format=reltime"], min(8, self.remaining()))
        rx = re.compile(r"(?i)(adsp|cdsp|q6v5|pdr|pd.mapper|pmic.glink|battmgr|"
                        r"interconnect|bwmon|apr|gpr|soundwire|wcd9|lpass|snd|backlight|"
                        r"dispcc|msm_dpu|simpledrm|kgsl|drm|dwc3|ucsi|typec|ath12k|"
                        r"btqca|bluetooth|camss|venus|thermal|cpufreq|smmu|iommu|firmware)")
        out.extend(line + "\n" for line in text.splitlines() if rx.search(line))
        out.append("\n== suspend and resume statistics\n")
        for name, value in self._suspend().items():
            out.append("%s=%s\n" % (name, value))
        out.append("mem_sleep=%s\n" % self._read("/sys/power/mem_sleep").strip())
        counts = self._kernel_counts()
        out.append("\n== kernel taint, oops and lockup indicators\n")
        out.append("tainted=%s\n" % counts["tainted"])
        out.append("oops-like lines: %d\n" % counts["oops_like"])
        out.append("kernel errors excluding Android noise: %d (excluded %d)\n" % (
            counts["errors"], counts["android_noise"]))
        out.append("\n== loaded modules\n")
        modules = self._read("/proc/modules").splitlines()
        out.append("%d modules: %s\n" % (len(modules), " ".join(
            line.split()[0] for line in modules)[:3500]))
        return "".join(out)

    def c_services(self):
        if self.remaining() < 0.5:
            return self._skip("services")
        failed = self._failed_units()
        out = ["\n== failed units, timers, noisy units\n"]
        out.append("FAILED UNITS: %s\n" % (", ".join(failed) if failed else "none"))
        if self._have("systemctl"):
            out.append(self._run(["systemctl", "list-timers", "--no-pager", "--no-legend"],
                                 min(5, self.remaining()))[:4000] + "\n")
        out.append("\n== units with most error-level journal lines this boot\n")
        text = self._run(["journalctl", "-b", "-p", "err", "-o", "json-pretty",
                          "--no-pager", "-q", "-n", "1000"],
                         min(8, self.remaining()))
        counts = {}
        for line in text.splitlines():
            match = re.search(r'"(_SYSTEMD_UNIT|SYSLOG_IDENTIFIER)"\s*:\s*"([^"]+)"', line)
            if match:
                counts[match.group(2)] = counts.get(match.group(2), 0) + 1
        for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:15]:
            out.append("%6d %s\n" % (count, name))
        out.append("\n== crashes (coredumpctl)\n")
        if self._have("coredumpctl"):
            out.append(self._run(["coredumpctl", "list", "--no-pager", "-q"],
                                 min(6, self.remaining()))[-4000:] + "\n")
        out.append("\n== application warnings of the desktop user (uid 1000), last 60\n")
        text = self._run(["journalctl", "-b", "_UID=1000", "-p", "warning",
                          "-o", "short-monotonic", "--no-pager", "-q", "-n", "200"],
                         min(8, self.remaining()))
        for line in text.splitlines()[-60:]:
            out.append(line[:240] + "\n")
        return "".join(out)

    def c_graphics(self):
        if self.remaining() < 0.5:
            return self._skip("graphics")
        out = ["\n== graphics session\n"]
        out.append(self._run(["journalctl", "-b", "-q", "--no-pager", "-n", "200",
                              "-t", "kestrel-graphics-supervisor"],
                             min(5, self.remaining()))[-3000:] + "\n")
        out.append(self._run(["loginctl", "list-sessions", "--no-legend"], 4) + "\n")
        for path in self._glob("/sys/class/drm/card*-*"):
            out.append("%s %s modes=%s\n" % (
                os.path.basename(path), self._read(os.path.join(path, "status")).strip(),
                self._read(os.path.join(path, "modes")).splitlines()[0]
                if self._read(os.path.join(path, "modes")).splitlines() else ""))
        try:
            out.append("dri: %s\n" % " ".join(os.listdir(self._path("/dev/dri"))))
        except OSError:
            pass
        out.append(self._run(["journalctl", "-b", "-q", "--no-pager", "-n", "200",
                              "-t", "kwin_wayland", "-t", "kwin_wayland_wrapper",
                              "-p", "warning"],
                             min(5, self.remaining()))[-3000:] + "\n")
        return "".join(out)

    def c_audio(self):
        if self.remaining() < 0.5:
            return self._skip("audio")
        out = ["\n== audio\n", self._read("/proc/asound/cards")[:1000] + "\n"]
        if self._have("wpctl"):
            out.append(self._run(["wpctl", "status"], min(5, self.remaining()))[:3000] + "\n")
        if self._have("pactl"):
            out.append(self._run(["pactl", "info"], 4) + "\n")
        return "".join(out)

    def c_net(self):
        if self.remaining() < 0.5:
            return self._skip("network")
        out = ["\n== network\n"]
        out.append(self._run(["ip", "-br", "link"], 4) + "\n")
        out.append(self._run(["ip", "-br", "addr"], 4) + "\n")
        if self._have("rfkill"):
            out.append(self._run(["rfkill", "list"], 4) + "\n")
        if self._have("nmcli"):
            out.append(self._run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev"], 4) + "\n")
        if self._have("iw"):
            for line in self._run(["iw", "dev"], 4).splitlines():
                if "Interface" in line or "type" in line or "channel" in line:
                    out.append(line + "\n")
            for line in self._run(["iw", "dev"], 4).splitlines():
                match = re.match(r"\s*Interface\s+(\S+)", line)
                if match:
                    link = self._run(["iw", "dev", match.group(1), "link"], 3)
                    out.extend(l + "\n" for l in link.splitlines()
                               if re.search(r"(signal|bitrate|freq)", l))
        if self._have("bluetoothctl"):
            text = self._run(["bluetoothctl", "list"], 3)
            out.append(re.sub(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", "XX:XX:XX:XX:XX:XX", text) + "\n")
        return "".join(out)

    def c_hw(self):
        if self.remaining() < 0.5:
            return self._skip("hardware")
        out = ["\n== usb and pci\n"]
        if self._have("lsusb"):
            out.append(self._run(["lsusb"], min(5, self.remaining())) + "\n")
        if self._have("lspci"):
            out.append(self._run(["lspci"], min(5, self.remaining())) + "\n")
        out.append("\n== input devices\n")
        for line in self._read("/proc/bus/input/devices").splitlines():
            if line.startswith(("N: Name", "H: Handlers")):
                out.append(line + "\n")
        out.append("\n== cameras and media\n")
        try:
            out.append(" ".join(os.listdir(self._path("/dev")))[:1000] + "\n")
        except OSError:
            pass
        return "".join(out)

    def c_proc(self):
        if self.remaining() < 0.5:
            return self._skip("processes")
        out = ["\n== busiest processes\n"]
        if self._have("ps"):
            out.append(self._run(["ps", "-eo", "pid,ppid,pcpu,pmem,rss,etimes,comm",
                                  "--sort=-pcpu"], min(4, self.remaining()))[:3000] + "\n")
            out.append(self._run(["ps", "-eo", "pid,pcpu,pmem,rss,comm",
                                  "--sort=-rss"], min(4, self.remaining()))[:2000] + "\n")
        return "".join(out)

    def collect_sections(self):
        # Reserve about five seconds for the cheap metrics/summary path.
        self.deadline_hit = False
        budget = self.deadline_s - 5 if self.deadline_s > 6 else max(1, self.deadline_s - 2)
        self.deadline = self.clock() + max(1, budget)
        collectors = (self.c_system, self.c_storage, self.c_thermal_cpu, self.c_power,
                      self.c_dsp, self.c_kernel, self.c_services, self.c_graphics,
                      self.c_audio, self.c_net, self.c_hw, self.c_proc)
        out = []
        for collector in collectors:
            if self.remaining() < 0.5:
                self.deadline_hit = True
                out.append(self._skip(collector.__name__[2:]))
                continue
            try:
                body = collector()
            except Exception as exc:  # a collector must never kill the snapshot
                body = "\n== %s\nCOLLECTOR_ERROR %s\n" % (collector.__name__[2:], type(exc).__name__)
            out.append(body)
        return out

    # -- writing ---------------------------------------------------------
    def compose(self, header, sections):
        budget = self.max_bytes - 128
        out = header
        truncated = None
        for index, block in enumerate(sections):
            if len(out.encode("utf-8")) + len(block.encode("utf-8")) <= budget:
                out += block
                continue
            room = budget - len(out.encode("utf-8")) - 64
            if room > 0:
                cut = block.encode("utf-8")[:room].decode("utf-8", "ignore")
                newline = cut.rfind("\n")
                if newline > 0:
                    out += cut[:newline + 1]
            truncated = index
            break
        if truncated is not None:
            out += "\nTRUNCATED reason=size section=%d\n" % truncated
        if self.deadline_hit or self.remaining() < 0.5:
            out += "\nSNAPSHOT_PARTIAL reason=deadline\n"
        return self.redactor.text(out)

    def _filename(self, seq, reason, uptime):
        safe_reason = re.sub(r"[^a-z0-9_-]+", "-", str(reason).lower()) or "event"
        if isinstance(seq, int) and seq >= 0 and safe_reason in (
                "periodic", "final", "scheduled", "startup"):
            return "snap-%03d-up%d.txt" % (seq, uptime), seq
        return "event-%s-up%d.txt" % (safe_reason, uptime), None

    def write(self, seq, reason="periodic", uptime=None, sections=None):
        uptime = _uptime() if uptime is None else int(uptime)
        sections = self.collect_sections() if sections is None else sections
        # Metrics are cheap; allow them a short window after the collector budget.
        self.deadline = self.clock() + max(3, min(8, self.deadline_s))
        mono = time.monotonic()
        header = ("fz-smartlog snapshot seq=%s uptime_s=%d mono=%.3f boot_id=%s where=%s\n"
                  "utc=%s\n" % (seq, uptime, mono, self.boot_id, self.where, _now_utc()))
        body = self.compose(header, sections)
        name, effective_seq = self._filename(seq, reason, uptime)
        path = os.path.join(self.smart_dir, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", errors="replace", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            fsync = getattr(os, "fdatasync", None) or getattr(os, "fsync", None)
            if fsync:
                try:
                    fsync(fh.fileno())
                except OSError:
                    pass
        os.replace(tmp, path)
        try:
            dfd = os.open(self.smart_dir, os.O_RDONLY)
            try:
                fsync = getattr(os, "fsync", None)
                if fsync:
                    fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
        exports = []
        if reason in ("final", "manual", "early") or seq == 999:
            export_tag = "final" if (reason == "final" or seq == 999) else reason
            exports = self.export_logs(export_tag)
        metrics = self.metrics()
        metrics["exports"] = " ".join(os.path.basename(path) for path in exports) or "none"
        metrics["uptime"] = str(uptime)
        metrics["mono"] = "%.3f" % mono
        metrics["snapshot_file"] = name
        metrics["snapshot_seq"] = str(effective_seq if effective_seq is not None else "")
        try:
            streams = [d for d in os.listdir(os.path.join(self.dest_dir, "streams"))
                       if os.path.isdir(os.path.join(self.dest_dir, "streams", d))]
            metrics["streams"] = str(len(streams))
            newest = 0.0
            for root, _dirs, files in os.walk(os.path.join(self.dest_dir, "streams")):
                for fname in files:
                    try:
                        newest = max(newest, os.stat(os.path.join(root, fname)).st_mtime)
                    except OSError:
                        pass
            metrics["last_write"] = _time_utc() if not newest else time.strftime(
                "%H:%M:%SZ", time.gmtime(newest))
        except OSError:
            metrics["streams"] = "0"
            metrics["last_write"] = "none"
        metrics["gaps"] = str(int(metrics.get("gaps") or 0))
        self.analyse(metrics, seq if effective_seq is not None else reason, uptime)
        self.event("snapshot seq=%s reason=%s file=%s" % (seq, reason, name))
        return path

    def export_logs(self, tag):
        """Bounded dmesg/journal exports, same names as v2 plus a .done marker."""
        if self.remaining() < 1:
            return []
        made = []
        sources = (
            ("dmesg", ["dmesg", "--time-format=iso"], 1500 * 1024),
            ("journal", ["journalctl", "-b", "--no-pager", "-o", "short-monotonic",
                         "-q", "-n", "50000"], 3000 * 1024),
        )
        for kind, cmd, cap in sources:
            text = self._run(cmd, min(6, max(1, self.remaining())))
            partial = False
            if not text:
                continue
            data = text.encode("utf-8", "replace")
            lines = data.splitlines(keepends=True)
            while len(gzip.compress(b"".join(lines), 6)) > cap and len(lines) > 200:
                lines = lines[len(lines) // 4:]
                partial = True
            payload = gzip.compress(b"".join(lines), 6)
            suffix = ".partial.gz" if partial else ".log.gz"
            path = os.path.join(self.smart_dir, "%s-%s%s" % (kind, tag, suffix))
            atomic_write(path, payload)
            done = os.path.join(self.smart_dir, "%s-%s.done" % (kind, tag))
            atomic_write(done, ("complete=%s lines=%d bytes=%d sha256=%s\n" % (
                "false" if partial else "true", len(lines), len(payload),
                hashlib.sha256(payload).hexdigest())).encode("ascii"))
            made.append(path)
        return made

    def event(self, text):
        line = "%s up=%s %s\n" % (_time_utc(), _uptime(), text)
        for path in (os.path.join(self.smart_dir, "events.log"),
                     os.path.join(self.dest_dir, "events.log")):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8", errors="replace", newline="\n") as fh:
                    fh.write(line)
                    fh.flush()
            except OSError:
                pass

    # -- analysis --------------------------------------------------------
    def _previous_summary(self):
        parent = os.path.dirname(self.dest_dir)
        current = os.path.basename(self.dest_dir)
        candidates = []
        try:
            for name in os.listdir(parent):
                path = os.path.join(parent, name)
                if not (name.startswith("boot-") and name != current and
                        os.path.isdir(path)):
                    continue
                started = 0.0
                try:
                    with open(os.path.join(path, "boot.json"), "r",
                              encoding="utf-8", errors="replace") as fh:
                        started = float(json.load(fh).get("started_epoch") or 0)
                except (OSError, ValueError, TypeError):
                    pass
                if not started:
                    try:
                        started = os.path.getmtime(path)
                    except OSError:
                        started = 0
                candidates.append((started, name, path))
        except OSError:
            return None, None
        for _started, _name, path in sorted(candidates, reverse=True):
            summary = os.path.join(path, "summary.json")
            try:
                with open(summary, "r", encoding="utf-8", errors="replace") as fh:
                    data = json.load(fh)
                return os.path.basename(path), data
            except (OSError, ValueError):
                continue
        return None, None

    def _changes(self, summary):
        previous_name, previous = self._previous_summary()
        if not previous:
            return previous_name, {}
        changes = {}
        for key in ("build_id", "kernel", "failed_units", "suspend", "wifi",
                    "sound", "waydroid", "kernel_errors"):
            old = previous.get(key)
            new = summary.get(key)
            if old != new:
                changes[key] = {"from": old, "to": new}
        return previous_name, changes

    def summary_json(self, m, previous_name=None, changes=None):
        data = {
            "schema": 3,
            "boot_id": self.boot_id,
            "where": self.where,
            "battery": {"capacity": m.get("battery_capacity"),
                        "voltage": m.get("battery_voltage"),
                        "status": m.get("battery_status"),
                        "health_pct": m.get("battery_health_pct"),
                        "ac_online": m.get("ac_online")},
            "dsp": {"running": m.get("remoteproc_running"),
                    "states": m.get("remoteproc_states")},
            "deferred": m.get("deferred"),
            "sound": {"cards": m.get("sound_cards")},
            "thermal": {"maxtemp_mc": m.get("maxtemp_mc")},
            "memory": {"memavail_kb": m.get("memavail_kb"),
                       "memtotal_kb": m.get("memtotal_kb"),
                       "psi_mem_avg10": m.get("psi_mem_some10")},
            "suspend": {"success": m.get("suspend_ok"), "fail": m.get("suspend_fail"),
                        "failed_resume": m.get("failed_resume"),
                        "last_failed_dev": m.get("last_failed_dev"),
                        "last_failed_step": m.get("last_failed_step")},
            "wifi": {"present": m.get("wifi_ifaces"), "up": m.get("wifi_up"),
                     "associated": m.get("wifi_associated"),
                     "last_error": m.get("wifi_last_error")},
            "failed_units": [u for u in (m.get("failed_unit_names") or "").split(",") if u],
            "kernel": {"errors": m.get("kernel_errors"),
                       "warnings": m.get("kernel_warnings"),
                       "oops_like": m.get("oops_like"),
                       "android_noise": m.get("android_noise"),
                       "tainted": m.get("tainted")},
            "waydroid": {"lines": m.get("waydroid_lines"),
                         "errors": m.get("waydroid_errors"),
                         "state": m.get("waydroid_state")},
            "top_signatures": [],
            "previous_boot": previous_name,
            "changes": changes or {},
            "generated_utc": _now_utc(),
        }
        return data

    def summary_lines(self, m):
        say = []
        say.append("FroodzOS smart summary  boot=%s  uptime=%ss  written=%sZ  where=%s" % (
            self.boot_id, m.get("uptime"), _time_utc(), self.where))
        say.append("(automatic rules; facts are in snap-*.txt and history.tsv. "
                   "A finding is a pointer, not a diagnosis.)")
        say.append("")
        bcap, bvolt, bstatus = (m.get("battery_capacity"), m.get("battery_voltage"),
                                m.get("battery_status"))
        if not bcap and not bvolt:
            say.append("BATTERY: no battery device present.")
        elif str(bcap) == "0" and (not bvolt or str(bvolt) == "0"):
            say.append("BATTERY: device exists but reports capacity 0 and no voltage "
                       "(status '%s'): its data source is not live. Check ADSP below." % bstatus)
        else:
            say.append("BATTERY: %s%% voltage %s status %s; AC online=%s; "
                       "full-charge capacity %s%% of design." % (
                           bcap, bvolt, bstatus, m.get("ac_online"),
                           m.get("battery_health_pct")))
        say.append("DSP: remoteproc running or attached %s [%s] (battery, sound and "
                   "USB-C power data need the ADSP)." % (
                       m.get("remoteproc_running"), m.get("remoteproc_states")))
        say.append("DEFERRED DEVICES: %s (drivers still waiting for a supplier)." % m.get("deferred"))
        say.append("SOUND: %s sound card(s)%s" % (
            m.get("sound_cards"),
            " (no sound device: depends on the ADSP)" if str(m.get("sound_cards")) == "0" else ""))
        say.append("THERMAL: hottest sensor %d C (experiment stop 80 C)." % (
            _int(m.get("maxtemp_mc")) // 1000))
        say.append("MEMORY: %d MB available of %d MB; root overlay use %s%%; "
                   "memory pressure avg10=%s." % (
                       _int(m.get("memavail_kb")) // 1024,
                       _int(m.get("memtotal_kb")) // 1024,
                       m.get("rootuse_pct"), m.get("psi_mem_some10")))
        say.append("LOAD: 1-minute load %s." % m.get("load1"))
        say.append("BACKLIGHT: %s (actual/max)." % m.get("backlight"))
        say.append("SUSPEND: %s successful suspend(s), %s failed; failed_resume=%s "
                   "last_failed_dev=%s step=%s; pd-mapper module loaded=%s." % (
                       m.get("suspend_ok"), m.get("suspend_fail"),
                       m.get("failed_resume"), m.get("last_failed_dev"),
                       m.get("last_failed_step"), m.get("pd_mapper")))
        say.append("WIFI: present=%s up=%s associated=%s last_error=%s" % (
            m.get("wifi_ifaces"), m.get("wifi_up"), m.get("wifi_associated"),
            m.get("wifi_last_error")))
        names = [u for u in (m.get("failed_unit_names") or "").split(",") if u]
        say.append("FAILED UNITS: %s" % (", ".join(names) if names else "none"))
        say.append("WAYDROID: lines=%s errors=%s state=%s (excluded from kernel error count)" % (
            m.get("waydroid_lines"), m.get("waydroid_errors"), m.get("waydroid_state")))
        say.append("SERVICES: failed units %s; crashes recorded %s." % (
            m.get("failed_units"), m.get("coredumps")))
        say.append("KERNEL: errors %s (excluded %s Android/Waydroid lines), warnings %s, "
                   "oops-like lines %s, taint %s." % (
                       m.get("kernel_errors"), m.get("android_noise"),
                       m.get("kernel_warnings"), m.get("oops_like"), m.get("tainted")))
        say.append("DATA: streams=%s last_write=%s gaps=%s dest=%s degraded=%s" % (
            m.get("streams", "?"), m.get("last_write", "?"), m.get("gaps", "0"),
            m.get("dest"), m.get("degraded")))
        if m.get("exports"):
            say.append("EXPORTS: %s" % m.get("exports"))
        return say

    def analyse(self, m, seq, uptime):
        os.makedirs(self.smart_dir, exist_ok=True)
        summary = self.summary_json(m)
        previous_name, changes = self._changes(summary)
        summary["previous_boot"] = previous_name
        summary["changes"] = changes
        summary["snapshot_seq"] = str(seq)
        atomic_write_json(os.path.join(self.smart_dir, "summary.json"), summary)
        atomic_write_json(os.path.join(self.dest_dir, "summary.json"), summary)
        lines = self.summary_lines(m)
        # Trend from the previous history row.
        history_path = os.path.join(self.smart_dir, "history.tsv")
        previous_rows = []
        try:
            with open(history_path, "r", encoding="utf-8", errors="replace") as fh:
                previous_rows = [line.rstrip("\n").split("\t") for line in fh][1:]
        except OSError:
            pass
        if previous_rows:
            first = previous_rows[0]
            last = previous_rows[-1]
            try:
                lines.append("TREND: hottest sensor was %s mC at the first snapshot, "
                             "%s mC at the previous one, %s mC now." % (
                                 first[3], last[3], m.get("maxtemp_mc")))
            except IndexError:
                pass
        lines.append("")
        lines.append("NEW SINCE LAST SNAPSHOT:")
        for key in ("failed_units", "coredumps", "kernel_errors", "oops_like"):
            marker = os.path.join(self.smart_dir, ".last-%s" % key)
            try:
                with open(marker, "r", encoding="ascii") as fh:
                    old = fh.read().strip()
            except OSError:
                old = ""
            new = str(m.get(key) or "0")
            if old and _int(new) > _int(old):
                lines.append("  %s rose from %s to %s" % (key, old, new))
            try:
                with open(marker, "w", encoding="ascii") as fh:
                    fh.write(new)
            except OSError:
                pass
        text = "\n".join(lines) + "\n"
        text = self.redactor.text(text)
        atomic_write(os.path.join(self.smart_dir, "summary.txt"), text.encode("utf-8", "replace"))
        atomic_write(os.path.join(self.dest_dir, "summary.txt"), text.encode("utf-8", "replace"))
        # history.tsv: the first 16 columns are unchanged.
        write_header = not os.path.exists(history_path)
        values = [
            str(seq), m.get("uptime"), _time_utc(), m.get("maxtemp_mc"),
            m.get("memavail_kb"), m.get("load1"), m.get("battery_capacity"),
            m.get("battery_voltage"), m.get("backlight"), m.get("failed_units"),
            m.get("coredumps"), m.get("deferred"), m.get("remoteproc_running"),
            m.get("sound_cards"), m.get("kernel_errors"), m.get("oops_like"),
            m.get("mono"), m.get("psi_io"),
            "up=%s,associated=%s" % (m.get("wifi_up"), m.get("wifi_associated")),
            m.get("suspend_fail"), m.get("waydroid_lines"), m.get("dest"),
            m.get("degraded"),
        ]
        row = "\t".join(_sanitize_tsv(v) for v in values) + "\n"
        with open(history_path, "a", encoding="utf-8", errors="replace", newline="\n") as fh:
            if write_header:
                fh.write("\t".join(HISTORY_COLUMNS + HISTORY_EXTRA) + "\n")
            fh.write(row)
        root_history = os.path.join(self.dest_dir, "history.tsv")
        if os.path.abspath(root_history) != os.path.abspath(history_path):
            root_header = not os.path.exists(root_history)
            try:
                with open(root_history, "a", encoding="utf-8", errors="replace",
                          newline="\n") as fh:
                    if root_header:
                        fh.write("\t".join(HISTORY_COLUMNS + HISTORY_EXTRA) + "\n")
                    fh.write(row)
            except OSError:
                pass
        return summary

    # -- CLI helpers -----------------------------------------------------
    def build_once(self):
        sections = self.collect_sections()
        self.deadline = self.clock() + max(3, min(8, self.deadline_s))
        metrics = self.metrics()
        header = ("fz-smartlog snapshot seq=0 uptime_s=%s mono=%.3f boot_id=%s where=terminal\n"
                  "utc=%s\n" % (metrics.get("uptime"), time.monotonic(),
                                self.boot_id, _now_utc()))
        body = self.compose(header, sections)
        return body, "\n".join(self.summary_lines(metrics)) + "\n"


def run_cli(argv=None):
    parser = argparse.ArgumentParser(prog="fz-smartlog snapshot")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--boot-id", default=os.environ.get("FZ_LOG_BOOT_ID", "unknown"))
    parser.add_argument("--where", default=os.environ.get("FZ_LOG_DEST_KIND", "ram"))
    parser.add_argument("--reason", default="periodic")
    parser.add_argument("--seq", type=int, default=0)
    parser.add_argument("--uptime", type=int, default=None)
    parser.add_argument("--deadline", type=int, default=20)
    parser.add_argument("--max-kb", type=int, default=1024)
    parser.add_argument("--privacy", default=os.environ.get("FZ_LOG_PRIVACY", "owner"))
    parser.add_argument("--root", default="/")
    parser.add_argument("--no-commands", action="store_true")
    args = parser.parse_args(argv)
    snap = Snapshotter(args.dest, boot_id=args.boot_id, where=args.where,
                       root=args.root, max_kb=args.max_kb,
                       deadline_s=args.deadline, privacy=args.privacy,
                       host=False if args.no_commands else None)
    path = snap.write(args.seq, args.reason, args.uptime)
    print(path)
    return 0


def main(argv=None):
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
