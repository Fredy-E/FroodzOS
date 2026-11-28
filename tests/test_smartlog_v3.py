#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""smartlog v3 core: writer, destination fallback, budgets, redaction, index and legacy files.

All secrets and identifiers below are synthetic.  No root, systemd, /proc or
hardware access is required; POSIX process details are skipped or use a plain
subprocess kill.
"""
import errno
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / "builder/public-image/rootfs-overlay"
PKG = OVL / "usr/local/lib/fz-smartlog"
SCRIPT = OVL / "usr/local/sbin/fz-smartlog"
WRITE_CLI = OVL / "usr/local/sbin/fz-smartlog-write"
UNIT = OVL / "etc/systemd/system/fz-smartlog.service"
sys.path.insert(0, str(PKG))

from fz_smartlog import record_full  # noqa: E402
from fz_smartlog.config import Config  # noqa: E402
from fz_smartlog.dest import Dest, DestManager  # noqa: E402
from fz_smartlog.index import build_index, write_index  # noqa: E402
from fz_smartlog.redact import Redactor  # noqa: E402
from fz_smartlog.snapshot import HISTORY_COLUMNS, HISTORY_EXTRA, Snapshotter  # noqa: E402
from fz_smartlog.writer import (  # noqa: E402
    DestinationFailed, StreamWriter, read_jsonl,
)

FAKE_PSK = "correct horse battery staple"
FAKE_SSID = "FAKE-SSID-01"
FAKE_MAC = "02:00:00:00:00:01"
FAKE_EMAIL = "alice@example.invalid"
FAKE_SERIAL = "FAKE-SERIAL-0001"
FAKE_TOKEN = "ghp_" + "A" * 36


def _env_with(**values):
    old = {key: os.environ.get(key) for key in values}
    os.environ.update({key: str(value) for key, value in values.items()})
    return old


def _restore_env(old):
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class TempMixin:
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fz-smartlog-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def sub(self, name):
        path = os.path.join(self.tmp, name)
        os.makedirs(path, exist_ok=True)
        return path

    def writer(self, stream="journal", **kw):
        base = self.sub("streams-%d" % int(time.time() * 1000000 % 1000000))
        options = dict(base_dir=base, max_bytes=1 << 20, segment_bytes=4096,
                       sync_ms=1000000, sync_bytes=1 << 20, privacy="owner")
        options.update(kw)
        return StreamWriter(stream, **options), base

    def all_records(self, base, stream="journal"):
        records, bad = [], []
        directory = os.path.join(base, stream)
        if not os.path.isdir(directory):
            return records, bad
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".jsonl"):
                continue
            recs, errors, _trailing = read_jsonl(os.path.join(directory, name))
            records.extend(recs)
            bad.extend(errors)
        return records, bad


class WriterTests(TempMixin, unittest.TestCase):
    def test_rotation_boundaries_and_segment_names(self):
        writer, base = self.writer(segment_bytes=256)
        for index in range(20):
            self.assertTrue(writer.write({"mono": index, "msg": "x" * 20}))
        writer.close("test")
        files = sorted(name for name in os.listdir(os.path.join(base, "journal"))
                       if name.endswith(".jsonl"))
        self.assertGreaterEqual(len(files), 3)
        self.assertEqual(files[0], "000001.jsonl")
        self.assertEqual(files[1], "000002.jsonl")
        for name in files[:-1]:
            self.assertLessEqual(os.path.getsize(os.path.join(base, "journal", name)),
                                 256 + 8)
        records, bad = self.all_records(base)
        self.assertEqual(bad, [])
        data = [r for r in records if "_fz" not in r and "mono" in r]
        self.assertEqual(len(data), 20)
        self.assertIn("stream_closed", [r.get("_fz") for r in records])

    def test_stream_cap_writes_marker_and_stops(self):
        writer, base = self.writer(max_bytes=600, segment_bytes=256)
        results = [writer.write({"mono": i, "msg": "y" * 20}) for i in range(50)]
        self.assertTrue(writer.capped)
        self.assertIn(False, results)
        self.assertFalse(writer.write({"mono": 99, "msg": "after"}))
        writer.close("test")
        records, bad = self.all_records(base)
        self.assertEqual(bad, [])
        self.assertIn("stream_cap", [r.get("_fz") for r in records])

    def test_destination_failed_on_erofs_open(self):
        def bad_open(path, flags, mode=0o777):
            raise OSError(errno.EROFS, "read-only")
        with self.assertRaises(DestinationFailed):
            StreamWriter("journal", base_dir=self.tmp, open_func=bad_open)

    def test_destination_failed_on_eio_write(self):
        calls = {"n": 0}
        real_write = os.write

        def bad_write(fd, data):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError(errno.EIO, "i/o error")
            return real_write(fd, data)

        writer = StreamWriter("journal", base_dir=self.tmp, write_func=bad_write)
        with self.assertRaises(DestinationFailed):
            writer.write({"mono": 1, "msg": "x"})

    def test_sync_cadence(self):
        class Clock:
            value = 0.0
            def __call__(self):
                return self.value

        clock = Clock()
        syncs = []
        writer = StreamWriter("journal", base_dir=self.tmp, clock=clock,
                              sync_ms=1000, sync_bytes=1 << 30,
                              fdatasync_func=lambda fd: syncs.append(clock.value))
        writer.write({"mono": 1, "msg": "a"})
        clock.value = 0.5
        writer.write({"mono": 2, "msg": "b"})
        self.assertEqual(syncs, [])
        clock.value = 1.1
        writer.write({"mono": 3, "msg": "c"})
        self.assertEqual(len(syncs), 1)
        self.assertAlmostEqual(syncs[0], 1.1)

    def test_close_flushes_before_closing(self):
        syncs = []
        writer = StreamWriter("journal", base_dir=self.tmp,
                              sync_ms=1000000, sync_bytes=1 << 30,
                              fdatasync_func=lambda fd: syncs.append(fd))
        writer.write({"mono": 1, "msg": "x"})
        self.assertEqual(syncs, [])
        writer.close("test")
        self.assertGreaterEqual(len(syncs), 1)

    def test_close_writes_closed_record_and_torn_tail_is_tolerated(self):
        writer, base = self.writer()
        writer.write({"mono": 1, "msg": "complete"})
        writer.close("unit-test")
        path = os.path.join(base, "journal", "000001.jsonl")
        with open(path, "ab") as fh:
            fh.write(b'{"mono":2,"msg":"torn"')
        records, bad, trailing = read_jsonl(path)
        self.assertEqual(bad, [])
        self.assertTrue(trailing)
        self.assertTrue(any(r.get("_fz") == "stream_closed" for r in records))

    def test_kill_subprocess_leaves_parseable_file(self):
        base = self.sub("kill-streams")
        code = (
            "import sys, time\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from fz_smartlog.writer import StreamWriter\n"
            "w = StreamWriter('kernel', base_dir=sys.argv[1], max_bytes=1<<30,"
            " segment_bytes=1<<30, sync_ms=20, sync_bytes=1)\n"
            "i = 0\n"
            "while True:\n"
            "    w.write({'mono': i, 'msg': 'x' * 200})\n"
            "    i += 1\n"
            "    time.sleep(0.01)\n"
        )
        proc = subprocess.Popen([sys.executable, "-I", "-c", code, base, str(PKG)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            path = os.path.join(base, "kernel", "000001.jsonl")
            deadline = time.time() + 10
            while time.time() < deadline:
                if os.path.exists(path) and os.path.getsize(path) > 500:
                    break
                time.sleep(0.05)
            self.assertTrue(os.path.exists(path))
            proc.kill()
            proc.wait(timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
        records, bad, _trailing = read_jsonl(path)
        self.assertTrue(any("_fz" not in r and r.get("msg") for r in records))
        self.assertEqual(bad, [])


class DestinationTests(TempMixin, unittest.TestCase):
    def config(self, **kw):
        values = dict(bootmnt=os.path.join(self.tmp, "bootmnt"),
                      persist=os.path.join(self.tmp, "persist"),
                      ram=os.path.join(self.tmp, "ram"),
                      state=os.path.join(self.tmp, "state"),
                      boot_id="test-boot", marker_ok=True,
                      min_free_mb=100, halt_free_mb=50, yellow_free_mb=200)
        values.update(kw)
        return Config(**values)

    def test_falls_back_to_ram_when_stick_and_persist_are_too_full(self):
        dest = DestManager(self.config(), free_mb_func=lambda path: 10,
                           probe_func=lambda path: (True, "ok"),
                           walk_bytes_func=lambda path: 0)
        current = dest.choose_initial()
        self.assertEqual(current.kind, "ram")

    def test_marker_absent_uses_ram_only(self):
        dest = DestManager(self.config(marker_ok=False),
                           free_mb_func=lambda path: 10 ** 9,
                           probe_func=lambda path: (True, "ok"),
                           walk_bytes_func=lambda path: 0)
        self.assertEqual(dest.choose_initial().kind, "ram")

    def test_free_space_tiers_and_hard_floor(self):
        config = self.config()
        now = [0.0]
        dest = DestManager(config, clock=lambda: now[0],
                           free_mb_func=lambda path: 150,
                           probe_func=lambda path: (True, "ok"),
                           walk_bytes_func=lambda path: 0)
        dest.choose_initial()
        tier = dest.tier()
        self.assertEqual(tier.name, "red")
        self.assertTrue(tier.can_write("kernel", 7))
        self.assertFalse(tier.can_write("terminal", 7))
        self.assertTrue(tier.can_write("journal", 3))
        self.assertFalse(tier.can_write("journal", 7))
        dest.free_mb_func = lambda path: 40
        now[0] = 100.0
        self.assertEqual(dest.tier().name, "halt")
        self.assertFalse(dest.tier().can_write("kernel", 7))

    def test_hard_boot_cap_keeps_only_kernel_and_errors(self):
        dest = DestManager(self.config(), free_mb_func=lambda path: 10 ** 6,
                           probe_func=lambda path: (True, "ok"),
                           walk_bytes_func=lambda path: 600 << 20)
        dest.choose_initial()
        tier = dest.tier()
        self.assertEqual(tier.name, "hard")
        self.assertTrue(tier.can_write("kernel", 7))
        self.assertFalse(tier.can_write("terminal", 7))
        self.assertFalse(tier.can_write("journal", 7))
        self.assertTrue(tier.can_write("journal", 3))

    def test_switch_chain_and_reprobe(self):
        probes = {"stick": True, "persist": True, "ram": True}
        dest = DestManager(self.config(), free_mb_func=lambda path: 10 ** 6,
                           probe_func=lambda path: (True, "ok"),
                           walk_bytes_func=lambda path: 0)
        self.assertEqual(dest.choose_initial().kind, "stick")
        probes["persist"] = False
        probes["stick"] = False

        def probe(path):
            return (True, "ok")

        # Inject the failure by switching to a manager whose later candidates fail.
        dest.probe_func = lambda path: (False, "injected")
        switched = dest.switch("injected")
        self.assertEqual(switched.kind, "ram")
        self.assertTrue(dest.failures)

    def test_prune_never_deletes_current_or_previous(self):
        config = self.config(max_stick_mb=1, min_free_mb=0)
        root = os.path.join(config.bootmnt, "Logs")
        for name, size in (("boot-old", 2 << 20), ("boot-prev", 1 << 20),
                           ("boot-current", 1 << 20)):
            path = os.path.join(root, name)
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, "boot.json"), "w", encoding="utf-8") as fh:
                json.dump({"started_epoch": {"boot-old": 1, "boot-prev": 2,
                                             "boot-current": 3}[name]}, fh)
            with open(os.path.join(path, "data.bin"), "wb") as fh:
                fh.write(b"x" * size)
        dest = DestManager(config, free_mb_func=lambda path: 10 ** 6,
                           probe_func=lambda path: (True, "ok"))
        dest.current = dest.make_dest("stick")
        deleted = dest.prune("boot-current")
        self.assertIn("boot-old", deleted)
        self.assertTrue(os.path.isdir(os.path.join(root, "boot-current")))
        self.assertTrue(os.path.isdir(os.path.join(root, "boot-prev")))
        self.assertFalse(os.path.isdir(os.path.join(root, "boot-old")))


class RedactionTests(TempMixin, unittest.TestCase):
    def test_redacted_mode_removes_synthetic_secrets(self):
        red = Redactor(key=b"0" * 32, mode="redacted")
        text = ('ssid="%s" mac %s mail %s serial=%s token=%s psk="%s"\n'
                % (FAKE_SSID, FAKE_MAC, FAKE_EMAIL, FAKE_SERIAL, FAKE_TOKEN, FAKE_PSK))
        out = red.text(text)
        for value in (FAKE_SSID, FAKE_MAC, FAKE_EMAIL, FAKE_SERIAL, FAKE_TOKEN, FAKE_PSK):
            self.assertNotIn(value, out)
        self.assertIn("<redacted:ssid:", out)
        self.assertIn("<redacted:mac:", out)
        self.assertIn("<redacted:psk:", out)
        self.assertEqual(red.text(out), out)  # idempotent

    def test_owner_mode_keeps_ssid_and_mac_but_never_psk(self):
        red = Redactor(mode="owner")
        out = red.text('ssid="%s" mac %s psk="%s"\n' % (FAKE_SSID, FAKE_MAC, FAKE_PSK))
        self.assertIn(FAKE_SSID, out)
        self.assertIn(FAKE_MAC, out)
        self.assertNotIn(FAKE_PSK, out)
        self.assertIn("<redacted:psk>", out)

    def test_writer_applies_privacy(self):
        writer, base = self.writer(privacy="redacted",
                                   redactor=Redactor(key=b"0" * 32, mode="redacted"))
        writer.write({"mono": 1, "MESSAGE": "psk=%s" % FAKE_PSK})
        writer.close("test")
        text = open(os.path.join(base, "journal", "000001.jsonl"),
                    encoding="utf-8").read()
        self.assertNotIn(FAKE_PSK, text)
        self.assertIn("<redacted:psk:", text)


class IndexTests(TempMixin, unittest.TestCase):
    def test_index_shape_and_completion(self):
        boot = self.sub("boot-test")
        writer = StreamWriter("journal", base_dir=os.path.join(boot, "streams"))
        writer.write({"mono": 1.0, "ts": "2026-01-01T00:00:00.000Z",
                      "MESSAGE": "one"})
        writer.close("test")
        os.makedirs(os.path.join(boot, "smart"), exist_ok=True)
        with open(os.path.join(boot, "smart", "snap-001-up59.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("snapshot\n")
        event_dir = os.path.join(boot, "events", "20260101T000000Z-resume")
        os.makedirs(event_dir, exist_ok=True)
        with open(os.path.join(event_dir, "event.json"), "w", encoding="utf-8") as fh:
            json.dump({"utc": "2026-01-01T00:00:00Z", "mono": 1.0,
                       "reason": "resume", "severity": "event"}, fh)
        with open(os.path.join(boot, "summary.json"), "w", encoding="utf-8") as fh:
            json.dump({"battery": {"capacity": "100"}}, fh)
        index = build_index(boot, boot_id="boot-test", complete=True,
                            dest_kind="ram", dest_path=boot, now=1767225660)
        self.assertEqual(index["schema"], 3)
        self.assertTrue(index["complete"])
        self.assertEqual(index["boot_id"], "boot-test")
        self.assertIn("journal", index["streams"])
        segment = index["streams"]["journal"]["segments"][0]
        self.assertTrue(segment["complete"])
        self.assertIn("sha256", segment)
        self.assertEqual(segment["first_mono"], 1.0)
        self.assertEqual(index["snapshots"][0]["seq"], 1)
        self.assertEqual(index["events"][0]["reason"], "resume")
        self.assertEqual(index["summary"]["battery"]["capacity"], "100")
        self.assertTrue(any(f["path"] == "smart/snap-001-up59.txt"
                            for f in index["files"]))
        path = write_index(boot, index)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(json.load(open(path, encoding="utf-8"))["schema"], 3)


class SnapshotTests(TempMixin, unittest.TestCase):
    def make(self, **kw):
        root = self.sub("fakeroot")
        options = dict(deadline_s=5, max_kb=256, privacy="owner")
        options.update(kw)
        return Snapshotter(self.tmp, boot_id="test-boot", where="ram", root=root,
                           host=False, **options)

    def test_legacy_file_names_summary_and_history(self):
        snap = self.make()
        sections = ["\n== fake\nhello\n"]
        first = snap.write(1, "periodic", uptime=59, sections=sections)
        self.assertTrue(first.endswith("snap-001-up59.txt"))
        event = snap.write(5, "resume", uptime=100, sections=sections)
        self.assertTrue(event.endswith("event-resume-up100.txt"))
        final = snap.write(999, "final", uptime=120, sections=sections)
        self.assertTrue(final.endswith("snap-999-up120.txt"))
        smart = os.path.join(self.tmp, "smart")
        for name in ("summary.txt", "history.tsv", "events.log",
                     "snap-001-up59.txt", "event-resume-up100.txt",
                     "snap-999-up120.txt"):
            self.assertTrue(os.path.exists(os.path.join(smart, name)), name)
        summary = open(os.path.join(smart, "summary.txt"), encoding="utf-8").read()
        for needle in ("FAILED UNITS:", "SUSPEND:", "failed_resume=",
                       "WIFI: present=", "associated=", "KERNEL: errors",
                       "WAYDROID:", "excluded from kernel error count"):
            self.assertIn(needle, summary)
        lines = open(os.path.join(smart, "history.tsv"), encoding="utf-8").read().splitlines()
        self.assertEqual(lines[0].split("\t")[:16], list(HISTORY_COLUMNS))
        self.assertEqual(lines[0].split("\t")[16:], list(HISTORY_EXTRA))
        self.assertEqual(len(lines), 4)  # header + three snapshots
        self.assertEqual(lines[1].split("\t")[1], "59")

    def test_failed_unit_names_survive_the_ascii_bullet(self):
        def runner(argv, timeout=None, **kw):
            text = " ".join(argv)
            if "--failed" in text:
                return "\n".join(["* archlinux-keyring-wkd-sync.service loaded failed failed Refresh keys",
                                  "● plasma-ksplash.service loaded failed failed Splash",
                                  "bare.service loaded failed failed Bare", ""])
            return ""
        snap = self.make(runner=runner)
        self.assertEqual(snap._failed_units(),
                         ["archlinux-keyring-wkd-sync.service", "plasma-ksplash.service", "bare.service"])

    def test_truncation_and_deadline_markers(self):
        snap = self.make(max_kb=1)
        body = snap.compose("header\n", ["\n== huge\n" + "x" * 5000 + "\n"])
        self.assertIn("TRUNCATED reason=size", body)
        self.assertLess(len(body), 2000)
        snap.deadline = 0
        body = snap.compose("header\n", [])
        self.assertIn("SNAPSHOT_PARTIAL reason=deadline", body)

    def test_kernel_error_count_excludes_android_init_noise(self):
        def runner(cmd, timeout):
            text = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if "--level=err" in text:
                return "real host error\nuid_1000 cgroup Read-only file system\n"
            if "--level=warn" in text:
                return "a warning\n"
            return "Oops: 0000 [#1] SMP\n"

        snap = self.make(runner=runner)
        counts = snap._kernel_counts()
        self.assertEqual(counts["errors"], 1)
        self.assertEqual(counts["android_noise"], 1)
        self.assertEqual(counts["warnings"], 1)
        self.assertEqual(counts["oops_like"], 1)

    def test_bounded_log_exports_keep_legacy_names(self):
        snap = self.make(runner=lambda cmd, timeout: "line one\nline two\n")
        snap.deadline = snap.clock() + 10
        made = snap.export_logs("final")
        names = [os.path.basename(path) for path in made]
        self.assertIn("dmesg-final.log.gz", names)
        self.assertIn("journal-final.log.gz", names)
        self.assertTrue(os.path.exists(
            os.path.join(snap.smart_dir, "dmesg-final.done")))
        with open(os.path.join(snap.smart_dir, "dmesg-final.log.gz"), "rb") as fh:
            import gzip
            self.assertIn(b"line one", gzip.decompress(fh.read()))

    def test_summary_mentions_named_failed_unit_and_resume_device(self):
        snap = self.make()
        metrics = snap.metrics()
        metrics.update({"failed_unit_names": "iio-sensor-proxy.service",
                        "failed_units": "1", "failed_resume": "1",
                        "last_failed_dev": "phy0", "last_failed_step": "resume",
                        "wifi_ifaces": "1", "wifi_up": "0",
                        "wifi_associated": "no", "kernel_errors": "3",
                        "android_noise": "7", "uptime": "59"})
        lines = "\n".join(snap.summary_lines(metrics))
        self.assertIn("FAILED UNITS: iio-sensor-proxy.service", lines)
        self.assertIn("failed_resume=1", lines)
        self.assertIn("last_failed_dev=phy0", lines)
        self.assertIn("WIFI: present=1 up=0 associated=no", lines)
        self.assertIn("KERNEL: errors 3 (excluded 7", lines)


class ContractTests(TempMixin, unittest.TestCase):
    def test_record_full_reads_proc_cmdline_or_env(self):
        path = os.path.join(self.tmp, "cmdline")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("console=tty1 fz_record=full\n")
        self.assertTrue(record_full(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("console=tty1 fz_record=fullx\n")
        self.assertFalse(record_full(path))
        old = _env_with(FZ_CMDLINE=path)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("fz_record=full\n")
            self.assertTrue(record_full())
        finally:
            _restore_env(old)

    def test_env_contract_and_env_file(self):
        from fz_smartlog.supervisor import Runtime
        config = Config(boot_id="test-boot", ram=os.path.join(self.tmp, "ram"),
                        state=os.path.join(self.tmp, "state"), marker_ok=False,
                        privacy="owner")
        runtime = Runtime(config)
        runtime.dest.current = Dest("ram", os.path.join(self.tmp, "ram"),
                                    os.path.join(self.tmp, "ram", "boot-test-boot"),
                                    "test-boot")
        env = runtime.build_env()
        self.assertEqual(env["FZ_LOG_DIR"], runtime.dest.current.streams_dir)
        self.assertEqual(env["FZ_LOG_BOOT_ID"], "test-boot")
        self.assertEqual(env["FZ_LOG_DEST_KIND"], "ram")
        self.assertEqual(env["FZ_LOG_SEGMENT_BYTES"], str(8 << 20))
        self.assertEqual(env["FZ_LOG_SYNC_MS"], "1000")
        self.assertEqual(env["FZ_LOG_SYNC_BYTES"], "65536")
        self.assertEqual(env["FZ_LOG_PRIVACY"], "owner")
        self.assertEqual(env["FZ_LOG_SCHEMA"], "3")
        runtime.write_env()
        env_path = os.path.join(config.state, "env")
        self.assertTrue(os.path.exists(env_path))
        text = open(env_path, encoding="utf-8").read()
        self.assertIn("FZ_LOG_SCHEMA='3'", text)
        self.assertIn("FZ_LOG_DIR=", text)

    def test_record_full_creates_plugin_directories(self):
        from fz_smartlog.supervisor import Runtime
        cmdline = os.path.join(self.tmp, "cmdline")
        with open(cmdline, "w", encoding="utf-8") as fh:
            fh.write("fz_record=full\n")
        config = Config(boot_id="test-boot", ram=os.path.join(self.tmp, "ram"),
                        state=os.path.join(self.tmp, "state"), marker_ok=False,
                        cmdline=cmdline, record_full=True)
        runtime = Runtime(config)
        runtime.dest.current = Dest("ram", os.path.join(self.tmp, "ram"),
                                    os.path.join(self.tmp, "ram", "boot-test-boot"),
                                    "test-boot")
        runtime._setup_layout()
        for stream in ("terminal", "ui", "waydroid"):
            self.assertTrue(os.path.isdir(os.path.join(
                runtime.dest.current.streams_dir, stream)))

    def test_unit_file_is_early_and_does_not_starve_the_writer(self):
        text = UNIT.read_text()
        self.assertIn("DefaultDependencies=no", text)
        self.assertIn("After=systemd-journald.service", text)
        self.assertIn("local-fs.target", text)
        self.assertIn("Before=basic.target", text)
        self.assertIn("Type=notify", text)
        self.assertIn("Restart=always", text)
        self.assertIn("TimeoutStopSec=25", text)
        self.assertIn("WantedBy=sysinit.target", text)
        self.assertNotIn("Nice=19", text)
        self.assertNotIn("IOSchedulingClass=idle", text)

    def test_cli_status_on_ram_without_marker(self):
        bootmnt = self.sub("nomarker")
        ram = self.sub("ram")
        cmdline = os.path.join(self.tmp, "cmdline")
        with open(cmdline, "w", encoding="utf-8") as fh:
            fh.write("console=tty1\n")
        env = dict(os.environ, FZ_SMARTLOG_BOOTMNT=bootmnt,
                   FZ_SMARTLOG_RAM=ram, FZ_BOOT_ID="test-boot",
                   FZ_CMDLINE=cmdline)
        proc = subprocess.run([sys.executable, "-I", str(SCRIPT), "status"],
                              capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema"], 3)
        self.assertFalse(data["marker"])
        self.assertEqual(data["dest_candidates"], ["ram"])
        self.assertFalse(data["record_full"])

    def test_snapshot_cli_creates_manual_event_file(self):
        boot = self.sub("cli-boot")
        bootmnt = self.sub("cli-nomarker")
        cmdline = os.path.join(self.tmp, "cmdline")
        with open(cmdline, "w", encoding="utf-8") as fh:
            fh.write("console=tty1\n")
        env = dict(os.environ, FZ_SMARTLOG_BOOTMNT=bootmnt,
                   FZ_SMARTLOG_RAM=boot, FZ_BOOT_ID="test-boot",
                   FZ_CMDLINE=cmdline, FZ_LOG_PRIVACY="owner")
        proc = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "snapshot", "--dest", boot,
             "--reason", "manual", "--seq", "5", "--no-commands"],
            capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        names = os.listdir(os.path.join(boot, "smart"))
        self.assertTrue(any(name.startswith("event-manual-up") for name in names), names)

    def test_write_cli_honours_privacy(self):
        base = self.sub("write-cli")
        env = dict(os.environ, FZ_LOG_DIR=base, FZ_LOG_PRIVACY="redacted",
                   FZ_LOG_SEGMENT_BYTES=str(8 << 20))
        payload = json.dumps({"mono": 1, "MESSAGE": "psk=%s" % FAKE_PSK}) + "\n"
        proc = subprocess.run([sys.executable, "-I", str(WRITE_CLI), "terminal"],
                              input=payload, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        records, bad = self.all_records(base, "terminal")
        self.assertEqual(bad, [])
        self.assertTrue(records)
        text = open(os.path.join(base, "terminal", "000001.jsonl"),
                    encoding="utf-8").read()
        self.assertNotIn(FAKE_PSK, text)
        self.assertIn("<redacted:psk:", text)


class SourceThreadTests(unittest.TestCase):
    """Regression: source threads must actually run their loop() (an early draft never did)."""

    def test_source_thread_runs_loop_and_survives_a_crash(self):
        from fz_smartlog import supervisor as sup

        calls = []

        class FakeRuntime:
            def marker(self, text):
                calls.append(("marker", text))

        class Probe(sup.Source):
            def loop(self):
                calls.append(("loop", len([c for c in calls if c[0] == "loop"])))
                if len([c for c in calls if c[0] == "loop"]) == 1:
                    raise RuntimeError("synthetic crash")

        src = Probe(FakeRuntime(), "probe")
        src.sleep = lambda _seconds: None
        src.start()
        src.join(5)
        self.assertFalse(src.is_alive())
        loops = [c for c in calls if c[0] == "loop"]
        self.assertEqual(len(loops), 2)
        self.assertTrue(any(c[0] == "marker" and "SOURCE_CRASH" in c[1] for c in calls))


class BootOrderingTests(unittest.TestCase):
    """Regression: the recorder starts in sysinit, so no unit it orders against may need basic.target."""

    UNITS = ROOT / "builder" / "public-image" / "rootfs-overlay" / "etc" / "systemd" / "system"

    def _unit(self, name):
        return (self.UNITS / name).read_text(encoding="utf-8")

    def test_recorder_does_not_wait_for_late_units(self):
        text = self._unit("fz-smartlog.service")
        self.assertIn("Before=basic.target", text)
        self.assertIn("DefaultDependencies=no", text)
        for line in text.splitlines():
            if line.startswith(("After=", "Wants=", "Requires=")):
                self.assertNotIn("fz-persist", line)

    def test_sysinit_helpers_have_no_default_dependencies(self):
        for name in ("fz-record-journald.service", "fz-record-kernel.service"):
            text = self._unit(name)
            self.assertIn("DefaultDependencies=no", text, name)
            self.assertNotIn("Before=multi-user.target", text, name)


class FalseAlarmRules(unittest.TestCase):
    """Measured on the first native record boot: debug chatter raised four 'oops' and one 'coredump' event."""

    def test_dynamic_debug_lines_are_not_oops(self):
        from fz_smartlog import snapshot, supervisor
        noisy = "initramfs: dynamic_debug: Device is queued (SEQNUM=3774, ACTION=add)"
        for rx in (supervisor.KERNEL_CRITICAL, snapshot.OOPS_RE):
            self.assertIsNone(rx.search(noisy), rx.pattern)
            self.assertIsNone(rx.search("echo debug: nothing"), rx.pattern)
            self.assertIsNotNone(rx.search("kernel BUG: unable to handle"), rx.pattern)
            self.assertIsNotNone(rx.search("[  5.1] BUG: soft lockup"), rx.pattern)
            self.assertIsNotNone(rx.search("Internal error: Oops: 96000005"), rx.pattern)
            self.assertIsNotNone(rx.search("Call trace:"), rx.pattern)

    def test_coredump_unit_name_in_debug_chatter_is_not_an_event(self):
        text = (PKG / "fz_smartlog/supervisor.py").read_text(encoding="utf-8")
        self.assertNotIn('"coredump" in message.lower()', text)
        self.assertIn('SYSLOG_IDENTIFIER") == "systemd-coredump"', text)

    def test_recorder_start_timeout_survives_a_debug_flooded_boot(self):
        text = UNIT.read_text(encoding="utf-8")
        start = int(next(l for l in text.splitlines() if l.startswith("TimeoutStartSec=")).split("=")[1])
        dog = int(next(l for l in text.splitlines() if l.startswith("WatchdogSec=")).split("=")[1])
        self.assertGreaterEqual(start, 90)   # r22 timed out at 20 s twice and was restarted twice
        self.assertGreaterEqual(dog, 60)


if __name__ == "__main__":
    unittest.main()
