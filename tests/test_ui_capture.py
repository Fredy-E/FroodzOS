#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-ui-capture: parsers, caps/rotation, the fz_record gate and the systemd wiring.

All test data is synthetic. Nothing here touches /run, /etc, /proc, the network or a device.
"""
import configparser
import importlib.machinery
import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / "builder/public-image/rootfs-overlay"
SCRIPT = OVL / "usr/local/sbin/fz-ui-capture"
QT_RULES = OVL / "etc/xdg/QtProject/qtlogging-froodzos-full.ini"
QT_ENV = OVL / "etc/xdg/plasma-workspace/env/90-froodzos-ui-record.sh"
SERVICE = OVL / "etc/systemd/system/fz-ui-capture.service"
SHOTS_SERVICE = OVL / "etc/systemd/system/fz-ui-shots.service"
SHOTS_TIMER = OVL / "etc/systemd/system/fz-ui-shots.timer"
WAYDROID_SERVICE = OVL / "etc/systemd/system/fz-waydroid-logcat.service"
COREDUMP = OVL / "etc/systemd/coredump.conf.d/90-froodzos.conf"
FIXTURES = Path(__file__).resolve().parent / "fixtures/ui-capture"
POSIX = sys.platform != "win32"


def load_module():
    loader = importlib.machinery.SourceFileLoader("fz_ui_capture", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


M = load_module()


def unit_parser(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def run_script(args, env):
    full_env = dict(os.environ)
    full_env.update(env)
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-B", str(SCRIPT)] + list(args),
                          capture_output=True, text=True, timeout=60, env=full_env)


class GateTests(unittest.TestCase):
    def test_record_gate_accepts_only_the_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            on = Path(tmp) / "on"
            off = Path(tmp) / "off"
            on.write_text("quiet splash fz_record=full\n", encoding="ascii")
            off.write_text("quiet splash fz_record=partial\n", encoding="ascii")
            self.assertTrue(M.record_on({"FZ_CMDLINE": str(on)}))
            self.assertFalse(M.record_on({"FZ_CMDLINE": str(off)}))
            self.assertTrue(M.record_on({"FZ_CMDLINE": "fz_record=full console=tty0"}))
            self.assertFalse(M.record_on({"FZ_CMDLINE": "not fz_record=fullish"}))

    def test_every_subcommand_is_a_noop_when_record_is_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmdline = Path(tmp) / "cmdline"
            cmdline.write_text("quiet\n", encoding="ascii")
            streams = Path(tmp) / "streams"
            state = Path(tmp) / "state"
            env = {
                "FZ_CMDLINE": str(cmdline),
                "FZ_LOG_DIR": str(streams),
                "FZ_UI_STATE": str(state),
                "FZ_UI_ENV_FILE": str(Path(tmp) / "missing-env"),
                "FZ_UI_LEGACY_ENV_FILE": str(Path(tmp) / "missing-legacy"),
            }
            for args in (["shots", "periodic"], ["shots", "event"], ["kwin-dump"],
                         ["journal-ui"], ["waydroid-logcat"]):
                result = run_script(args, env)
                self.assertEqual(result.returncode, 0, "%s: %s" % (args, result.stderr))
            self.assertFalse(streams.exists() and any(streams.rglob("*")))


class ParserTests(unittest.TestCase):
    def test_logcat_threadtime_lines_and_continuations(self):
        lines = (FIXTURES / "logcat-threadtime.txt").read_text(encoding="utf-8").splitlines()
        parsed = [M.parse_logcat_line(line) for line in lines]
        first = parsed[1]
        self.assertFalse(first["continuation"])
        self.assertEqual(first["pid"], 1234)
        self.assertEqual(first["tid"], 1200)
        self.assertEqual(first["level"], "I")
        self.assertEqual(first["tag"], "ActivityManager")
        self.assertIn("Start proc", first["msg"])
        self.assertTrue(parsed[0]["continuation"])          # "--------- beginning of main"
        self.assertTrue(parsed[5]["continuation"])          # Java stack trace line
        self.assertIn("Main.onCreate", parsed[5]["msg"])
        self.assertEqual(parsed[3]["level"], "E")
        self.assertEqual(parsed[3]["tag"], "AndroidRuntime")
        self.assertEqual(parsed[-1]["tag"], "chatty")

    def test_logcat_record_has_contract_fields_and_redacts(self):
        red = M.Redactor(b"x" * 32)
        line = ("11-25 18:00:00.123  1234  1200 I Auth: "
                "Authorization: Bearer ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA user@example.invalid")
        record = M.logcat_record(line, red)
        blob = json.dumps(record)
        self.assertEqual(record["source"], "logcat")
        self.assertIn("ts", record)
        self.assertIn("mono", record)
        self.assertEqual(record["pid"], 1234)
        self.assertNotIn("ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", blob)
        self.assertNotIn("user@example.invalid", blob)
        self.assertIn("<redacted:", blob)

    def test_journal_json_parser_normalizes_and_redacts(self):
        obj = {
            "__REALTIME_TIMESTAMP": "1764093600123456",
            "__MONOTONIC_TIMESTAMP": "123456789",
            "PRIORITY": "7",
            "SYSLOG_IDENTIFIER": "kwin_wayland",
            "_SYSTEMD_USER_UNIT": "plasma-kwin_wayland.service",
            "_PID": "4242",
            "_UID": "1000",
            "MESSAGE": ("window title is ghp_BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB "
                        "from 02:00:00:00:00:01 at /home/alice/secret.txt "
                        "hostname=FROODZ-PRIVATE user=bob"),
        }
        record, event = M.journal_record(obj, M.Redactor(b"k" * 32))
        self.assertFalse(event)
        self.assertEqual(record["source"], "journal")
        self.assertEqual(record["severity"], "debug")
        self.assertEqual(record["unit"], "plasma-kwin_wayland.service")
        self.assertEqual(record["pid"], 4242)
        self.assertEqual(record["mono"], 123.457)
        self.assertRegex(record["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        blob = json.dumps(record)
        self.assertNotIn("ghp_BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", blob)
        self.assertNotIn("02:00:00:00:00:01", blob)
        self.assertNotIn("/home/alice", blob)
        self.assertNotIn("FROODZ-PRIVATE", blob)
        self.assertNotIn("user=bob", blob)
        self.assertIn("<redacted:", blob)

    def test_journal_coredump_is_an_event(self):
        obj = {"__REALTIME_TIMESTAMP": "1764093600123456",
               "__MONOTONIC_TIMESTAMP": "1000000",
               "PRIORITY": "3", "SYSLOG_IDENTIFIER": "systemd-coredump",
               "MESSAGE": "Process 123 (plasmashell) of user 1000 dumped core."}
        record, event = M.journal_record(obj)
        self.assertTrue(event)
        self.assertEqual(record["event"], "coredump")
        self.assertEqual(record["severity"], "err")

    def test_journal_garbage_is_ignored(self):
        record, event = M.parse_journal_line("{not json")
        self.assertIsNone(record)
        self.assertFalse(event)

    def test_input_events_report_types_only(self):
        data = b"".join([
            M._EVENT.pack(1, 2, 0, 0, 0),     # EV_SYN
            M._EVENT.pack(1, 2, 1, 30, 1),    # EV_KEY with code KEY_A - must not leak
            M._EVENT.pack(1, 2, 2, 0, 5),     # EV_REL
            M._EVENT.pack(1, 2, 3, 53, 10),   # EV_ABS with a position code
        ])
        counts = M.summarize_input_events(data)
        self.assertEqual(counts, {"EV_SYN": 1, "EV_KEY": 1, "EV_REL": 1, "EV_ABS": 1})
        self.assertNotIn("30", json.dumps(counts))
        self.assertNotIn("53", json.dumps(counts))


class ScreenshotCapTests(unittest.TestCase):
    def make(self, directory, name, size):
        path = Path(directory) / name
        path.write_bytes(b"x" * size)
        return path

    def test_periodic_ring_and_total_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(10):
                self.make(tmp, "20260101T0000%02dZ-periodic.webp" % i, 1000)
            M.gc_shots(tmp, 100, 4, 20)
            periodic = sorted(p.name for p in Path(tmp).iterdir() if "-periodic" in p.name)
            self.assertEqual(len(periodic), 4)
            self.assertEqual(periodic[0], "20260101T000006Z-periodic.webp")  # oldest removed
            self.assertLessEqual(M._total_kb(M.shot_files(tmp)), 100)

    def test_cap_prunes_periodic_then_events_but_keeps_newest_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(4):
                self.make(tmp, "20260101T0000%02dZ-periodic.png" % i, 1000)
            for i in range(5):
                self.make(tmp, "20260101T0001%02dZ-event.png" % i, 1000)
            M.gc_shots(tmp, 2, 4, 20)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertIn("20260101T000104Z-event.png", names)
            self.assertNotIn("20260101T000100Z-event.png", names)
            self.assertLessEqual(M._total_kb(M.shot_files(tmp)), 2)

    def test_event_count_is_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(8):
                self.make(tmp, "20260101T0001%02dZ-event.webp" % i, 1000)
            M.gc_shots(tmp, 100, 10, 3)
            events = [p for p in Path(tmp).iterdir() if "-event" in p.name]
            self.assertEqual(len(events), 3)
            self.assertTrue((Path(tmp) / "20260101T000107Z-event.webp").exists())


class WriterTests(unittest.TestCase):
    def test_fallback_writer_writes_jsonl_and_rotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = M._ShimWriter("ui", max_bytes=100000, segment_bytes=4096, base_dir=tmp)
            for mono in (1.0, 2.0, 3.0):
                writer.write({"ts": "2026-01-01T00:00:00.000Z", "mono": mono,
                              "source": "test", "message": "x" * 2000})
            writer.close()
            segments = sorted((Path(tmp) / "ui").glob("*.jsonl"))
            self.assertGreaterEqual(len(segments), 2)
            records = []
            for segment in segments:
                for line in segment.read_text(encoding="utf-8").splitlines():
                    records.append(json.loads(line))
            self.assertEqual([r.get("mono") for r in records if "mono" in r], [1.0, 2.0, 3.0])
            self.assertEqual(records[-1]["_fz"], "stream_closed")

    def test_script_compiles_and_uses_the_streamwriter_contract(self):
        text = SCRIPT.read_text(encoding="utf-8")
        compile(text, str(SCRIPT), "exec")
        self.assertIn("SPDX-License-Identifier: GPL-2.0-or-later", text)
        self.assertNotIn("\r", text)
        self.assertIn("from fz_smartlog.writer import StreamWriter", text)
        self.assertIn("FZ_LOG_DIR", text)
        for sub in ("journal-ui", "kwin-dump", "shots", "waydroid-logcat", "enable-qt"):
            self.assertIn(sub, text)


class QtActivationTests(unittest.TestCase):
    def test_rules_are_curated_and_default_off(self):
        parser = unit_parser(QT_RULES)
        rules = parser["Rules"]
        self.assertEqual(rules["*.debug"], "false")
        self.assertEqual(rules["default.debug"], "true")
        for key in ("kwin_core.debug", "qt.qpa.*.debug", "org.kde.powerdevil.debug",
                    "xdp-kde-*.debug"):
            self.assertEqual(rules[key], "true")
        self.assertNotIn("qt.scenegraph.debug", rules)
        text = QT_RULES.read_text(encoding="utf-8")
        rule_lines = [line.strip() for line in text.splitlines()
                      if line.strip() and not line.lstrip().startswith(("#", "["))]
        self.assertNotIn("*.debug=true", rule_lines)
        self.assertLess(rule_lines.index("*.debug=false"),
                        rule_lines.index("kwin_core.debug=true"))

    def test_no_default_qtlogging_ini_is_shipped(self):
        # Qt reads QtProject/qtlogging.ini unconditionally; it must only exist after enable-qt.
        self.assertFalse((OVL / "etc/xdg/QtProject/qtlogging.ini").exists())

    def test_env_snippet_activates_only_when_full(self):
        text = QT_ENV.read_text(encoding="utf-8")
        self.assertIn("fz-record-on", text)
        self.assertIn("QT_LOGGING_CONF", text)
        self.assertIn("fz_record=full", text)
        if not POSIX or not shutil.which("sh"):
            self.skipTest("sh is not available")
        with tempfile.TemporaryDirectory() as tmp:
            full = Path(tmp) / "full.ini"
            full.write_text("[Rules]\n", encoding="utf-8")
            on = Path(tmp) / "on"
            off = Path(tmp) / "off"
            on.write_text("fz_record=full\n", encoding="ascii")
            off.write_text("quiet\n", encoding="ascii")

            def sourced(cmdline):
                env = dict(os.environ, FZ_CMDLINE=str(cmdline), FZ_QT_FULL=str(full))
                return subprocess.run(
                    ["sh", "-c", '. "$1"; printf "%s" "${QT_LOGGING_CONF:-}"',
                     "sh", str(QT_ENV)],
                    capture_output=True, text=True, timeout=30, env=env).stdout

            self.assertEqual(sourced(on), str(full))
            self.assertEqual(sourced(off), "")

    @unittest.skipIf(sys.platform == "win32", "symlinks need privileges on Windows")
    def test_enable_qt_links_and_unlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            full = Path(tmp) / "full.ini"
            full.write_text("[Rules]\n", encoding="utf-8")
            link = Path(tmp) / "etc/QtProject/qtlogging.ini"
            on = Path(tmp) / "on"
            off = Path(tmp) / "off"
            on.write_text("fz_record=full\n", encoding="ascii")
            off.write_text("quiet\n", encoding="ascii")
            env_on = {"FZ_CMDLINE": str(on), "FZ_QT_FULL": str(full), "FZ_QT_LINK": str(link)}
            env_off = {"FZ_CMDLINE": str(off), "FZ_QT_FULL": str(full), "FZ_QT_LINK": str(link)}
            self.assertTrue(M.enable_qt(env_on))
            self.assertTrue(os.path.islink(link))
            self.assertEqual(os.path.realpath(link), os.path.realpath(full))
            self.assertTrue(M.enable_qt(env_off))
            self.assertFalse(os.path.lexists(link))


class UnitLintTests(unittest.TestCase):
    def test_python_compiles_and_shell_syntax_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(str(SCRIPT), cfile=str(Path(tmp) / "fz.pyc"), doraise=True)
        if POSIX and shutil.which("sh"):
            result = subprocess.run(["sh", "-n", str(QT_ENV)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_capture_service_runs_before_the_greeter_without_starving(self):
        parser = unit_parser(SERVICE)
        unit = parser["Unit"]
        service = parser["Service"]
        self.assertIn("fz_record=full", unit["ConditionKernelCommandLine"])
        self.assertIn("sddm.service", unit["Before"])
        self.assertIn("systemd-journald.service", unit["After"])
        self.assertEqual(service["ExecStart"], "/usr/local/sbin/fz-ui-capture journal-ui")
        self.assertEqual(service["Restart"], "always")
        self.assertLessEqual(int(service["Nice"]), 15)
        self.assertNotEqual(service.get("IOSchedulingClass"), "idle")
        self.assertIn("TimeoutStopSec", service)
        self.assertEqual(parser["Install"]["WantedBy"], "multi-user.target")

    def test_shots_units_are_timer_only(self):
        service = unit_parser(SHOTS_SERVICE)
        self.assertEqual(service["Service"]["Type"], "oneshot")
        self.assertEqual(service["Service"]["ExecStart"], "/usr/local/sbin/fz-ui-capture shots periodic")
        self.assertLessEqual(int(service["Service"]["Nice"]), 15)
        self.assertIn("/usr/bin/spectacle", service["Unit"]["ConditionPathExists"])
        self.assertNotIn("Install", service)
        timer = unit_parser(SHOTS_TIMER)
        self.assertEqual(timer["Timer"]["OnUnitActiveSec"], "60s")
        self.assertIn("OnBootSec", timer["Timer"])
        self.assertEqual(timer["Timer"]["Unit"], "fz-ui-shots.service")
        self.assertEqual(timer["Install"]["WantedBy"], "timers.target")

    def test_waydroid_logcat_follows_the_container_lifecycle(self):
        parser = unit_parser(WAYDROID_SERVICE)
        unit = parser["Unit"]
        self.assertEqual(unit["BindsTo"], "waydroid-container.service")
        self.assertIn("waydroid-container.service", unit["After"])
        self.assertIn("fz_record=full", unit["ConditionKernelCommandLine"])
        service = parser["Service"]
        self.assertTrue(service["ExecStart"].endswith("waydroid-logcat"))
        self.assertEqual(service["Restart"], "always")
        self.assertLessEqual(int(service["Nice"]), 15)

    def test_coredump_is_bounded(self):
        parser = unit_parser(COREDUMP)
        coredump = parser["Coredump"]
        self.assertEqual(coredump["Storage"], "none")
        self.assertEqual(coredump["ProcessSizeMax"], "512M")
        self.assertIn("MaxUse", coredump)
        self.assertIn("KeepFree", coredump)

    def test_no_unit_uses_the_starving_nice_19(self):
        for path in (SERVICE, SHOTS_SERVICE, WAYDROID_SERVICE):
            self.assertNotIn("Nice=19", path.read_text(encoding="utf-8"))


class FixtureTests(unittest.TestCase):
    def test_fixtures_are_synthetic(self):
        text = (FIXTURES / "logcat-threadtime.txt").read_text(encoding="utf-8")
        self.assertIn("com.example.app", text)
        self.assertNotIn("gmail", text.lower())
        self.assertNotIn("almaza", text.lower())


if __name__ == "__main__":
    unittest.main()
