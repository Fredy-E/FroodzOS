#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Opt-in filesystem tests for the smartlog-v3 writer contract.

These tests need Linux root, loop devices, mkfs.vfat/fsck.vfat and (for one
case) device-mapper. They are skipped unless ``FZ_FS_TESTS=1`` and euid 0:

    wsl -d CachyOSBuilder -u root -- bash -c \
      'cd /mnt/d/.../t3-b0630faa && FZ_FS_TESTS=1 python3 -B -m unittest tests.test_recorder_fs -v'

The real writer is being implemented in parallel. The test-only reference
writer below uses the same seams and the same NDJSON framing, so the tests can
be pointed at ``fz_smartlog.writer`` without changing the assertions.

HOOK: replace ``RefWriter``/``writer_main`` with an adapter over
``fz_smartlog.writer.StreamWriter`` once that module exists (keep the CLI flags
``--target/--ram/--ext4/--max-file-bytes/--max-total-bytes/--reserve-bytes``).
"""
import errno
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path

FZ_FS_TESTS = os.environ.get("FZ_FS_TESTS") == "1"
IS_LINUX = sys.platform.startswith("linux")
EUID = os.geteuid() if hasattr(os, "geteuid") else 1
ROOT = IS_LINUX and EUID == 0 and FZ_FS_TESTS
WRITER = Path(__file__).resolve()
FALLBACK_ERRNOS = {errno.ENOSPC, errno.EROFS, errno.EIO, errno.ENODEV, errno.EDQUOT, errno.ENXIO}
O_BINARY = getattr(os, "O_BINARY", 0)


def run(cmd, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError("%s failed rc=%d: %s %s" % (" ".join(cmd), result.returncode,
                                                       result.stdout.strip(), result.stderr.strip()))
    return result


def encode_record(stream, payload, now):
    return (json.dumps({"t": round(now, 3), "s": stream, "c": zlib.crc32(payload.encode()), "d": payload},
                       ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def parse_log_text(data):
    if isinstance(data, str):
        data = data.encode()
    lines = data.split(b"\n")
    trailing = False
    if lines and lines[-1] == b"":
        lines.pop()
    elif lines:
        trailing = True
        lines = lines[:-1]
    records, bad = [], []
    for line in lines:
        line = line.strip(b"\r")
        try:
            record = json.loads(line.decode("utf-8", "replace"))
            if not isinstance(record, dict) or "d" not in record or "c" not in record:
                raise ValueError("shape")
            if zlib.crc32(str(record["d"]).encode()) != record["c"]:
                raise ValueError("crc")
        except Exception:
            bad.append(line)
            continue
        records.append(record)
    return records, bad, trailing


# ---------------------------------------------------------------------------
# REFERENCE WRITER (test-only). See the HOOK note in the module docstring.
# ---------------------------------------------------------------------------

class RefConfig:
    def __init__(self, target, ram, ext4=None, max_file_bytes=8 << 20, max_total_bytes=64 << 20,
                 max_files=3, reserve_bytes=4 << 20, sync_interval=1.0, space_check_interval=0.2,
                 boot_id="test-boot"):
        self.target = target
        self.ram = ram
        self.ext4 = ext4
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.max_files = max_files
        self.reserve_bytes = reserve_bytes
        self.sync_interval = sync_interval
        self.space_check_interval = space_check_interval
        self.boot_id = boot_id


class RefWriter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.where = None
        self.directory = None
        self.files = {}
        self.total = 0
        self.seq = 0
        self.last_record = None
        self.last_sync = time.monotonic()
        self.last_space = 0.0
        self.fallback = None
        self.notes = []
        self.stopped = False
        self._open()

    def _free(self, path):
        try:
            return shutil.disk_usage(path).free
        except OSError:
            return 0

    def _activate(self, directory, label):
        if not directory:
            return False
        try:
            os.makedirs(directory, exist_ok=True)
            probe = os.path.join(directory, ".fz-rec-probe")
            with open(probe, "wb"):
                pass
            os.unlink(probe)
        except OSError:
            return False
        if self._free(directory) < self.cfg.reserve_bytes:
            return False
        self.where, self.directory = label, directory
        return True

    def _open(self):
        if not self._activate(self.cfg.target, "stick"):
            self._fallback("target-unwritable-or-low-space")

    def _path(self, index):
        return os.path.join(self.directory, "kmsg-%03d.log" % index)

    def _ensure(self):
        if "kmsg" in self.files:
            return self.files["kmsg"]
        fd = os.open(self._path(0), os.O_WRONLY | os.O_CREAT | os.O_APPEND | O_BINARY, 0o600)
        self.files["kmsg"] = {"fd": fd, "index": 0, "size": os.stat(self._path(0)).st_size}
        return self.files["kmsg"]

    def _rotate(self):
        current = self.files.pop("kmsg")
        os.close(current["fd"])
        index = current["index"] + 1
        if index >= self.cfg.max_files:
            self.stopped = True
            self.notes.append("rotation-exhausted")
            return False
        fd = os.open(self._path(index), os.O_WRONLY | os.O_CREAT | os.O_APPEND | O_BINARY, 0o600)
        self.files["kmsg"] = {"fd": fd, "index": index, "size": 0}
        return True

    def _fallback(self, reason):
        previous = self.where
        for item in self.files.values():
            try:
                os.close(item["fd"])
            except OSError:
                pass
        self.files = {}
        if previous in (None, "stick") and self._activate(self.cfg.ext4, "ext4"):
            pass
        elif previous in (None, "stick", "ext4") and self._activate(self.cfg.ram, "ram"):
            pass
        else:
            self.stopped = True
            self.notes.append("fallback-exhausted:" + reason)
            return
        self.fallback = reason
        self.notes.append("fallback:%s->%s" % (reason, self.where))

    def write(self, line):
        if self.stopped:
            return False
        now = time.monotonic()
        if now - self.last_sync >= self.cfg.sync_interval:
            self.sync()
        data = encode_record("kmsg", line, now)
        if self.total + len(data) > self.cfg.max_total_bytes:
            self.stopped = True
            self.notes.append("global-cap")
            return False
        if not self.cfg.space_check_interval or now - self.last_space >= self.cfg.space_check_interval:
            self.last_space = now
            if self._free(self.directory) < self.cfg.reserve_bytes + len(data):
                self._fallback("free-space")
                if self.where == "ram":
                    return self.write(line)
                return False
        try:
            item = self._ensure()
            if item["size"] + len(data) > self.cfg.max_file_bytes and item["size"] > 0:
                if not self._rotate():
                    return False
                item = self.files["kmsg"]
            os.write(item["fd"], data)
        except OSError as exc:
            if exc.errno in FALLBACK_ERRNOS:
                self._fallback("write:%s" % exc.errno)
                return False
            raise
        item["size"] += len(data)
        self.total += len(data)
        self.seq += 1
        self.last_record = now
        return True

    def sync(self):
        now = time.monotonic()
        for item in self.files.values():
            try:
                os.fsync(item["fd"])
            except OSError:
                pass
        alive = {"t": round(now, 3), "where": self.where, "total": self.total, "seq": self.seq,
                 "last_record_t": round(self.last_record, 3) if self.last_record else None,
                 "fallback": self.fallback}
        path = os.path.join(self.directory, "alive.json")
        try:
            with open(path + ".tmp", "wb") as fh:
                fh.write(json.dumps(alive).encode())
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(path + ".tmp", path)
        except OSError:
            pass
        self.last_sync = now

    def close(self):
        self.sync()
        for item in self.files.values():
            try:
                os.close(item["fd"])
            except OSError:
                pass
        self.files = {}
        self.stopped = True
        return {"where": self.where, "total": self.total, "seq": self.seq,
                "fallback": self.fallback, "notes": self.notes}


def writer_main(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--ram", required=True)
    parser.add_argument("--ext4", default=None)
    parser.add_argument("--lines", type=int, default=0)
    parser.add_argument("--rate", type=int, default=0)
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--max-file-bytes", type=int, default=8 << 20)
    parser.add_argument("--max-total-bytes", type=int, default=64 << 20)
    parser.add_argument("--reserve-bytes", type=int, default=4 << 20)
    parser.add_argument("--sync-interval", type=float, default=1.0)
    parser.add_argument("--space-check-interval", type=float, default=0.2)
    args = parser.parse_args(argv)
    writer = RefWriter(RefConfig(args.target, args.ram, ext4=args.ext4,
                                 max_file_bytes=args.max_file_bytes,
                                 max_total_bytes=args.max_total_bytes,
                                 reserve_bytes=args.reserve_bytes,
                                 sync_interval=args.sync_interval,
                                 space_check_interval=args.space_check_interval))
    stop = {"flag": False}

    def on_signal(signum, frame):
        stop["flag"] = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, on_signal)
        except (ValueError, OSError):
            pass
    started = time.monotonic()
    count = 0
    while not stop["flag"] and not writer.stopped:
        if args.lines and count >= args.lines:
            break
        if args.duration and time.monotonic() - started >= args.duration:
            break
        writer.write("synthetic kmsg record %06d payload=%s" % (count, "x" * 48))
        count += 1
        if args.rate:
            time.sleep(1.0 / args.rate)
    stats = writer.close()
    stats["elapsed"] = round(time.monotonic() - started, 3)
    print(json.dumps(stats, sort_keys=True))
    return 0


class FatImage:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.mountpoint = None
        self.loop = None
        self.mounted = False
        self.fstype = None

    def create(self, size_mb=64, label="FZTEST", fstype="vfat"):
        with open(self.path, "wb") as fh:
            fh.truncate(size_mb << 20)
        self.fstype = fstype
        if fstype == "vfat":
            run(["mkfs.vfat", "-F", "32", "-n", label, self.path])
        else:
            run(["mkfs.ext4", "-q", "-F", "-L", label, self.path])
        return self

    def _detect(self):
        if self.fstype:
            return self.fstype
        probe = run(["blkid", "-o", "value", "-s", "TYPE", self.path], check=False)
        self.fstype = (probe.stdout or "").strip() or "vfat"
        return self.fstype

    def mount(self, ro=False):
        if self.mountpoint is None:
            self.mountpoint = tempfile.mkdtemp(prefix="fzfs.")
        if self.loop is None:
            self.loop = run(["losetup", "-f", "--show", self.path]).stdout.strip()
        fstype = self._detect()
        opts = "ro" if ro else ("rw,uid=0,gid=0,umask=022" if fstype == "vfat" else "rw")
        run(["mount", "-t", fstype, "-o", opts, self.loop, self.mountpoint])
        self.mounted = True
        return self.mountpoint

    def remount(self, ro):
        run(["mount", "-o", "remount,%s" % ("ro" if ro else "rw"), self.mountpoint])

    def free_bytes(self):
        stats = os.statvfs(self.mountpoint)
        return stats.f_bavail * stats.f_frsize

    def snapshot(self, destination):
        shutil.copyfile(self.path, destination)
        return destination

    def umount(self):
        if self.mounted:
            run(["umount"] + ([self.mountpoint] if self.fstype == "vfat" else ["-l", self.mountpoint]), check=False)
            self.mounted = False
        if self.loop:
            run(["losetup", "-d", self.loop], check=False)
            self.loop = None

    def fsck(self, repair=False):
        extra = ["-a"] if repair else ["-n"]
        if self._detect() == "vfat":
            result = run(["fsck.vfat"] + extra + [self.path], check=False)
        else:
            result = run(["fsck.ext4", "-fn", self.path], check=False)
        output = (result.stdout + result.stderr).strip()
        errors = [line for line in output.splitlines()
                  if any(word in line for word in ("corrupt", "Cross-link", "cross-link", "Lost cluster",
                                                   "Bad cluster", "FATs differ", "Free cluster summary",
                                                   "has differences"))]
        return {"rc": result.returncode, "errors": errors, "output": output}


def logs_in(directory):
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
            if name.endswith(".log") and name.startswith("kmsg-")]


def parse_dir(directory):
    info = {"records": 0, "bad": 0, "trailing": 0, "files": []}
    for path in logs_in(directory):
        with open(path, "rb") as fh:
            records, bad, trailing = parse_log_text(fh.read())
        info["records"] += len(records)
        info["bad"] += len(bad)
        info["trailing"] += int(trailing)
        info["files"].append({"name": os.path.basename(path), "bytes": os.path.getsize(path)})
    return info


def start_writer(target, ram, extra=()):
    cmd = [sys.executable, str(WRITER), "--writer", "--target", target, "--ram", ram,
           "--rate", "1200", "--max-file-bytes", "131072", "--max-total-bytes", str(8 << 20),
           "--sync-interval", "0.25", "--space-check-interval", "0.0"] + list(extra)
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def stop_writer(proc):
    proc.terminate()
    try:
        out, err = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    stats = None
    for line in out.splitlines():
        try:
            stats = json.loads(line)
        except Exception:
            pass
    return stats, err


@unittest.skipUnless(ROOT and shutil.which("losetup") and shutil.which("mkfs.vfat") and shutil.which("fsck.vfat"),
                     "needs Linux root, FZ_FS_TESTS=1, losetup/mkfs.vfat/fsck.vfat")
class FatRecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fzrecfs.", dir="/tmp")
        self.image = FatImage(os.path.join(self.tmp, "fat.img")).create(128, "RECORDER")
        self.ram = os.path.join(self.tmp, "ram")

    def tearDown(self):
        try:
            self.image.umount()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rotation_and_clean_fat_after_graceful_stop(self):
        mount = self.image.mount()
        proc = start_writer(mount, self.ram)
        time.sleep(2.0)
        stats, err = stop_writer(proc)
        self.assertIsNotNone(stats, err)
        self.assertEqual(stats["where"], "stick")
        info = parse_dir(mount)
        self.assertGreater(info["records"], 100)
        self.assertEqual(info["bad"], 0)
        self.assertGreaterEqual(len(info["files"]), 2)
        self.assertTrue(all(item["bytes"] <= 131072 for item in info["files"]))
        self.image.umount()
        fsck = self.image.fsck()
        self.assertNotIn("corrupt", fsck["output"].lower())

    def test_read_only_mount_from_the_start_writes_only_ram(self):
        mount = self.image.mount()
        self.image.remount(ro=True)
        proc = start_writer(mount, self.ram)
        time.sleep(1.0)
        stats, err = stop_writer(proc)
        self.assertIsNotNone(stats, err)
        self.assertEqual(stats["where"], "ram")
        self.assertFalse(logs_in(mount))
        self.assertGreater(parse_dir(self.ram)["records"], 0)
        self.image.remount(ro=False)

    def test_free_space_guard_on_a_nearly_full_image(self):
        mount = self.image.mount()
        filler = os.path.join(mount, "filler.bin")
        with open(filler, "wb") as fh:
            chunk = b"x" * (1 << 20)
            while self.image.free_bytes() > (2 << 20):
                fh.write(chunk)
            os.fsync(fh.fileno())
        proc = start_writer(mount, self.ram, ["--reserve-bytes", str(4 << 20)])
        time.sleep(1.0)
        stats, err = stop_writer(proc)
        self.assertIsNotNone(stats, err)
        self.assertEqual(stats["where"], "ram")
        self.assertFalse(logs_in(mount))
        self.assertGreater(parse_dir(self.ram)["records"], 0)
        os.unlink(filler)

    def test_read_only_fat_prefers_the_persistent_ext4_target(self):
        mount = self.image.mount()
        self.image.remount(ro=True)
        ext4 = FatImage(os.path.join(self.tmp, "persist.img")).create(96, "PERSIST", fstype="ext4")
        ext4_mount = ext4.mount()
        proc = start_writer(mount, self.ram, ["--ext4", ext4_mount, "--reserve-bytes", "0"])
        time.sleep(1.0)
        stats, err = stop_writer(proc)
        self.assertIsNotNone(stats, err)
        self.assertEqual(stats["where"], "ext4")
        self.assertGreater(parse_dir(ext4_mount)["records"], 0)
        self.assertFalse(logs_in(mount))
        ext4.umount()
        self.image.remount(ro=False)

    def test_kill_9_leaves_parseable_logs_and_a_readable_snapshot(self):
        mount = self.image.mount()
        proc = start_writer(mount, self.ram)
        time.sleep(1.4)
        proc.kill()
        proc.wait(timeout=10)
        info = parse_dir(mount)
        self.assertGreater(info["records"], 50)
        self.assertEqual(info["bad"], 0)
        self.assertLessEqual(info["trailing"], len(info["files"]))
        snapshot = os.path.join(self.tmp, "powercut.img")
        self.image.snapshot(snapshot)
        self.image.umount()
        fsck = self.image.fsck(repair=True)
        self.assertLessEqual(fsck["rc"], 1, fsck["output"])
        snap_image = FatImage(snapshot)
        self.assertLessEqual(snap_image.fsck(repair=True)["rc"], 1)
        snap_mount = snap_image.mount(ro=True)
        snap_info = parse_dir(snap_mount)
        snap_image.umount()
        self.assertGreater(snap_info["records"], 0)
        self.assertEqual(snap_info["bad"], 0)

    def test_snapshot_while_writer_runs_is_readable(self):
        mount = self.image.mount()
        proc = start_writer(mount, self.ram)
        time.sleep(1.0)
        snapshot = os.path.join(self.tmp, "inflight.img")
        self.image.snapshot(snapshot)
        stop_writer(proc)
        self.image.umount()
        snap_image = FatImage(snapshot)
        fsck = snap_image.fsck(repair=True)
        self.assertLessEqual(fsck["rc"], 1, fsck["output"])
        snap_mount = snap_image.mount(ro=True)
        info = parse_dir(snap_mount)
        snap_image.umount()
        self.assertGreater(info["records"], 0)
        self.assertEqual(info["bad"], 0)


@unittest.skipUnless(ROOT and shutil.which("losetup") and shutil.which("mkfs.ext4") and shutil.which("fsck.ext4"),
                     "needs Linux root, FZ_FS_TESTS=1 and mkfs.ext4")
class Ext4RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fzrecx.", dir="/tmp")
        self.image = FatImage(os.path.join(self.tmp, "ext4.img")).create(96, "RECORDER", fstype="ext4")
        self.ram = os.path.join(self.tmp, "ram")

    def tearDown(self):
        try:
            self.image.umount()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_9_ext4_recovers_and_logs_parse(self):
        mount = self.image.mount()
        proc = start_writer(mount, self.ram)
        time.sleep(1.4)
        proc.kill()
        proc.wait(timeout=10)
        info = parse_dir(mount)
        self.assertGreater(info["records"], 50)
        self.assertEqual(info["bad"], 0)
        snapshot = os.path.join(self.tmp, "powercut-ext4.img")
        self.image.snapshot(snapshot)
        self.image.umount()
        self.assertLessEqual(self.image.fsck()["rc"], 2)
        copy = FatImage(snapshot)
        self.assertLessEqual(copy.fsck()["rc"], 2)
        copy_mount = copy.mount(ro=True)
        self.assertGreater(parse_dir(copy_mount)["records"], 0)
        copy.umount()


@unittest.skipUnless(ROOT and shutil.which("dmsetup") and shutil.which("blockdev")
                     and os.path.exists("/dev/mapper/control"),
                     "needs Linux root, FZ_FS_TESTS=1 and device-mapper")
class DmErrorRecorderTests(unittest.TestCase):
    def test_removed_stick_mid_run_falls_back_to_ram(self):
        tmp = tempfile.mkdtemp(prefix="fzdm.", dir="/tmp")
        image = os.path.join(tmp, "fs.img")
        mount = os.path.join(tmp, "mnt")
        os.makedirs(mount)
        name = "fzrec%d" % os.getpid()
        loop = None
        try:
            with open(image, "wb") as fh:
                fh.truncate(96 << 20)
            run(["mkfs.ext4", "-q", "-F", image])
            loop = run(["losetup", "-f", "--show", image]).stdout.strip()
            sectors = run(["blockdev", "--getsz", loop]).stdout.strip()
            run(["dmsetup", "create", name, "--table", "0 %s linear %s 0" % (sectors, loop)])
            run(["mount", "-t", "ext4", "/dev/mapper/" + name, mount])
            proc = start_writer(mount, os.path.join(tmp, "ram"))
            time.sleep(1.0)
            run(["dmsetup", "suspend", name])
            run(["dmsetup", "reload", name, "--table", "0 %s error" % sectors])
            run(["dmsetup", "resume", name])
            time.sleep(1.4)
            stats, err = stop_writer(proc)
            self.assertIsNotNone(stats, err)
            self.assertEqual(stats["where"], "ram")
            self.assertTrue(str(stats.get("fallback", "")).startswith("write:"), stats)
            self.assertGreater(parse_dir(os.path.join(tmp, "ram"))["records"], 0)
        finally:
            run(["umount", "-l", mount], check=False)
            run(["dmsetup", "remove", "-f", name], check=False)
            if loop:
                run(["losetup", "-d", loop], check=False)
            shutil.rmtree(tmp, ignore_errors=True)


def main():
    if "--writer" in sys.argv:
        index = sys.argv.index("--writer")
        return writer_main(sys.argv[index + 1:])
    unittest.main()


if __name__ == "__main__":
    raise SystemExit(main())
