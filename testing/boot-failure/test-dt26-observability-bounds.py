#!/usr/bin/env python3
"""dt26 observability bounds: genuine stalled-command + IO regressions.

Scope (owned ONLY): builder/diagnostics/kestrel-root-log.sh, this test,
and dt26-observability-bounds-* evidence. Never touches kernel/DTB/SFS,
hooks, menus, accounts, provider config, supervisor/harness suites.

Proven by RUNNING the shipped logger end to end in a private mount ns
(not pid ns, so PID1 stays systemd; propagation private; tmpfs over /run
+ bind of private host-tmp fixture to /run/archiso/bootmnt; kmsg bind to
tmp file; host /run untouched, no sudo/chown/rm-rf, no generic marker):
- true monotonic clock (BASH_MONOSECONDS assignment-ignored else
  /proc/uptime, never SECONDS), fixed window from logger start, graphics
  default 260 / text 120, fresh remaining before EVERY external
  (each journalctl, each systemctl, each Python persist, copy/sync/journal),
  timeout -k kill-after for TERM-ignoring children, skip (never unbounded)
  when timeout/clock missing, missing-python skips JSON with fail-open.
  Documented honesty: 1s resolution + ~2s KILL grace + ~1s scheduler;
  D-state/sync may exceed; NOT hard realtime.
- timing: stalling journal AND systemctl (responsive sleep 5), TERM-ignore
  (trap TERM + sleep 5), missing-timeout (no timeout binary, sleep 5 would
  be unbounded), monotonic vs SECONDS-reset, elapsed <= budget+documented
  grace; stubs never sleep >5s; parent process-group backstop kills on
  timeout.
- persist: exact src whitelist, O_NOFOLLOW/NONBLOCK/fstat regular, cap+1
  src + dest reads (no huge alloc), reject invalid UTF8/JSON/NaN/non-dict/
  partial/null-detail, atomic tmpfile + checked file fsync + replace
  (fsync failure preserves old), minimal status (reason str +
  bounded_cleanup bool, no hw duplication), reject FIFO/dir/symlink
  without blocking, no unchanged rewrite, all fail-open 0.

Zero skips. TESTONLY runtime: unshare+mount are test-only, not production.
"""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
LOGGER = P / "builder/diagnostics/kestrel-root-log.sh"
T = P / "testing/boot-failure"
SELF9 = T / "test-dt26-observability.py"
SELF9FIX = T / "test-dt26-observability-fix.py"
LEGACY_JSON = T / "dt26-observability-result.json"
LEGACY_LOG = T / "dt26-observability.log"
FIX_JSON = T / "dt26-observability-fix-result.json"
FIX_LOG = T / "dt26-observability-fix-result.log"

REQUIRED = [LOGGER]
BASH = shutil.which("bash") or "bash"

CASES_RUN = []
RUN_TMP = None


def file_sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight_outputs(json_path, log_path):
    for path in (json_path, log_path):
        if path.exists():
            try:
                digest = file_sha256(path)
                size = path.stat().st_size
            except OSError as exc:
                return False, "exists but unreadable: %s (%s)" % (path, exc)
            return False, "refusing: output exists, preserving: %s sha256=%s bytes=%d" % (path, digest, size)
    if json_path.parent != log_path.parent:
        return False, "json and log must share one directory"
    return True, "clear"


def resolve_outputs(argv):
    parser = argparse.ArgumentParser(description="dt26 observability bounds (collision-safe)")
    parser.add_argument("--out-prefix", default=None)
    parser.add_argument("--run-dir", default=None)
    args = parser.parse_args(argv)
    tmp_base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    if args.out_prefix:
        prefix = Path(args.out_prefix)
        if prefix.suffix in (".json", ".log"):
            stem = prefix.name[: -len(prefix.suffix)]
            json_path = prefix.parent / (stem + ".json")
            log_path = prefix.parent / (stem + ".log")
        else:
            json_path = Path(str(prefix) + ".json")
            log_path = Path(str(prefix) + ".log")
        for path in (json_path, log_path):
            if path.exists():
                try:
                    digest = file_sha256(path)
                    size = path.stat().st_size
                except OSError as exc:
                    print("REFUSED: output exists but unreadable: %s (%s)" % (path, exc), file=sys.stderr)
                    return None, None, None, 2
                print("REFUSED: output exists, preserving: %s sha256=%s bytes=%d" % (path, digest, size), file=sys.stderr)
                return None, None, None, 2
        if json_path.parent != log_path.parent:
            print("REFUSED: json and log must share one directory", file=sys.stderr)
            return None, None, None, 2
    if args.run_dir:
        run_dir = Path(args.run_dir)
        if run_dir.exists():
            print("REFUSED: --run-dir exists, preserving it: %s" % run_dir, file=sys.stderr)
            return None, None, None, 2
        run_dir.mkdir(parents=True)
    else:
        run_dir = Path(tempfile.mkdtemp(prefix="dt26-bounds-", dir=tmp_base))
    if args.out_prefix:
        pass
    else:
        json_path = run_dir / "dt26-observability-bounds-result.json"
        log_path = run_dir / "dt26-observability-bounds.log"
    return run_dir, json_path, log_path, 0


def real_bin(name):
    found = shutil.which(name)
    return found or ("/usr/bin/%s" % name)


def write_stub(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def make_stubs(stubdir, journal_body, systemctl_body):
    stubdir = Path(stubdir)
    stubdir.mkdir(parents=True, exist_ok=True)
    write_stub(stubdir, "mountpoint",
               "#!/bin/bash\nif [ \"${2:-}\" = /run/archiso/bootmnt ]; then exit 0; fi\nexec %s \"$@\"\n" % real_bin("mountpoint"))
    write_stub(stubdir, "readlink",
               "#!/bin/bash\nif [ \"${2:-}\" = /sys/class/block/sda ]; then echo /sys/devices/pci0000:00/usb1/1-1/block/sda; exit 0; fi\nexec %s \"$@\"\n" % real_bin("readlink"))
    write_stub(stubdir, "findmnt",
               "#!/bin/bash\nif [ \"$*\" = \"-n -o FSTYPE /\" ]; then echo overlay; exit 0; fi\nexec %s \"$@\"\n" % real_bin("findmnt"))
    write_stub(stubdir, "journalctl", journal_body)
    write_stub(stubdir, "systemctl", systemctl_body)
    return str(stubdir)


def require_mount_ns():
    if not shutil.which("unshare") or not shutil.which("mount"):
        raise AssertionError("unshare+mount required for private-mount isolation (TESTONLY)")


def make_private_fixture(tmp_base, tag):
    require_mount_ns()
    if Path("/run/archiso/bootmnt").exists():
        raise AssertionError("refusing: host /run/archiso/bootmnt exists (must stay untouched)")
    safe_tag = str(tag).replace("/", "-")
    fixture_root = Path(tmp_base) / ("fixture-%s" % safe_tag)
    fixture_root.mkdir(parents=True, exist_ok=True)
    (fixture_root / "KESTREL-LOG-TARGET").write_text("KESTREL_A64_USB_CAPTURE_V1", encoding="utf-8")
    dest_host = fixture_root / "Logs" / safe_tag
    dest_host.mkdir(parents=True, exist_ok=True)
    dest_ns = Path("/run/archiso/bootmnt/Logs") / safe_tag
    kmsg_fake = Path(tmp_base) / ("kmsg-fake-%s" % safe_tag)
    kmsg_fake.write_text("", encoding="utf-8")
    return fixture_root, dest_ns, dest_host, kmsg_fake


def run_ns_runner(fixture_root, kmsg_fake, stub_path, extra_env, command_argv, timeout=30):
    require_mount_ns()
    runner = fixture_root.parent / ("ns-runner-%s.sh" % fixture_root.name.replace("/", "-"))
    mount_bin = shutil.which("mount") or "/usr/sbin/mount"
    mkdir_bin = shutil.which("mkdir") or "/bin/mkdir"
    # Checked mount isolation BEFORE the shipped script: any required mount
    # failure stops here (distinct 41-45) so the tested script never runs and
    # host /run + /dev/kmsg are never mutated. No bare || true on this path.
    lines = ["#!/bin/bash", "set -u",
             "%s --make-rprivate / >/dev/null 2>&1 || exit 41" % mount_bin,
             "%s -t tmpfs tmpfs /run >/dev/null 2>&1 || exit 42" % mount_bin,
             "%s -p /run/archiso/bootmnt || exit 43" % mkdir_bin,
             "%s --bind %s /run/archiso/bootmnt >/dev/null 2>&1 || exit 44" % (mount_bin, shlex.quote(fixture_root.as_posix())),
             "if [ -e /dev/kmsg ]; then %s --bind %s /dev/kmsg >/dev/null 2>&1 || exit 45; fi" % (mount_bin, shlex.quote(kmsg_fake.as_posix()))]
    merged_path = str(stub_path) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
    lines.append("export PATH=%s" % shlex.quote(merged_path))
    for k, v in extra_env.items():
        lines.append("export %s=%s" % (k, shlex.quote(str(v))))
    quoted = " ".join(shlex.quote(str(a)) for a in command_argv)
    lines.append("exec %s" % quoted)
    runner.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    runner.chmod(0o755)
    start = time.monotonic()
    proc = subprocess.Popen(["unshare", "-rm", "--propagation", "private", "bash", str(runner)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True, env=dict(os.environ))
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            killed = False
        except subprocess.TimeoutExpired:
            killed = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except Exception:
                stdout, stderr = "", ""
        elapsed = time.monotonic() - start
        return {"rc": proc.returncode, "stdout": (stdout or "")[-5000:],
                "stderr": (stderr or "")[-2000:], "elapsed": elapsed, "outer_killed": killed}
    finally:
        if Path("/run/archiso/bootmnt").exists():
            raise AssertionError("global /run/archiso/bootmnt leaked (must stay private)")
        try:
            runner.unlink()
        except OSError:
            pass


def write_capture_state(state_dir, dest_ns):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "destination").write_text(str(dest_ns), encoding="utf-8")
    (state_dir / "device").write_text("sda", encoding="utf-8")
    (state_dir / "bootmnt").write_text("/run/archiso/bootmnt", encoding="utf-8")


def run_logger_ns(fixture_root, kmsg_fake, stub_path, state_dir, cmdline, graphics_dir, dest_ns,
                  extra_env, timeout=30):
    env = {
        "KESTREL_CAPTURE_STATE": str(state_dir),
        "KESTREL_CMDLINE_FILE": str(cmdline),
        "KESTREL_GRAPHICS_STATUS_DIR": str(graphics_dir),
    }
    env.update(extra_env)
    res = run_ns_runner(fixture_root, kmsg_fake, stub_path, env, [BASH, str(LOGGER)], timeout=timeout)
    proc = types.SimpleNamespace(returncode=res["rc"], stdout=res["stdout"], stderr=res["stderr"],
                                 outer_killed=res["outer_killed"])
    return proc, res["elapsed"]


def unstage_check():
    if Path("/run/archiso/bootmnt").exists():
        raise AssertionError("global /run/archiso/bootmnt exists (must stay private)")


class Dt26Bounds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in REQUIRED:
            assert path.is_file(), "missing owned file: %s" % path
        assert shutil.which("bash"), "bash required"
        assert RUN_TMP is not None, "run dir not initialized"
        require_mount_ns()
        CASES_RUN.append("setup_required_files_present")

    def test_clock_true_monotonic(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-clock-", dir=str(RUN_TMP)) as tmp:
            script = Path(tmp) / "clock.sh"
            script.write_text("#!/bin/bash\n"
                              "set -u\n"
                              "case \"${BASH_MONOSECONDS-}\" in ''|*[!0-9]*) echo NOMONO; exit 1;; esac\n"
                              "m1=$BASH_MONOSECONDS\n"
                              "BASH_MONOSECONDS=0\n"
                              "m2=$BASH_MONOSECONDS\n"
                              "if [ \"$m2\" != \"$m1\" ]; then echo MONO_RESETABLE; exit 1; fi\n"
                              "s1=$SECONDS\n"
                              "SECONDS=0\n"
                              "s2=$SECONDS\n"
                              "if [ \"$s2\" != 0 ]; then echo SECONDS_NOT_RESETTABLE; exit 1; fi\n"
                              "sleep 1\n"
                              "m3=$BASH_MONOSECONDS\n"
                              "if [ \"$m3\" -le \"$m2\" ]; then echo MONO_NOT_ADVANCING; exit 1; fi\n"
                              "if [ ! -r /proc/uptime ]; then echo NO_UPTIME; exit 1; fi\n"
                              "u1=$(cut -d' ' -f1 /proc/uptime)\n"
                              "sleep 1\n"
                              "u2=$(cut -d' ' -f1 /proc/uptime)\n"
                              "python3 - \"$u1\" \"$u2\" <<'PYEOF'\n"
                              "import sys\n"
                              "u1=float(sys.argv[1]); u2=float(sys.argv[2])\n"
                              "assert u2 >= u1, 'uptime went backwards'\n"
                              "print('CLOCK_MONOTONIC_OK')\n"
                              "PYEOF\n",
                              encoding="utf-8")
            script.chmod(0o755)
            proc = subprocess.run([BASH, str(script)], capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("CLOCK_MONOTONIC_OK", proc.stdout)
        CASES_RUN.append("clock_true_monotonic")

    def test_logger_monotonic_static(self):
        log = LOGGER.read_text(encoding="utf-8")
        self.assertIn("BASH_MONOSECONDS", log)
        self.assertIn("proc-uptime", log)
        self.assertNotIn("logger_start=$SECONDS", log)
        self.assertNotIn("logger_deadline - SECONDS", log)
        self.assertIn("logger_now_s", log)
        self.assertIn("logger_remaining_s", log)
        self.assertIn("logger_call_timeout_s", log)
        self.assertIn("timeout -k", log)
        self.assertIn("KESTREL_LOGGER_KILL_AFTER_S", log)
        self.assertIn("KESTREL_LOGGER_NO_TIMEOUT_FAIL_OPEN", log)
        self.assertIn("KESTREL_LOGGER_NO_MONOTONIC_FAIL_OPEN", log)
        self.assertIn('not isinstance(obj["detail"], dict)', log)
        self.assertIn("parse_constant", log)
        self.assertIn("dneed = cap + 1", log)
        self.assertNotIn("handle.read() ==", log)
        for line in log.splitlines():
            self.assertNotRegex(line, r"^\s*sync\s*$")
        self.assertTrue(log.rstrip().endswith("exit 0"))
        CASES_RUN.append("logger_monotonic_static")

    def test_stalling_journal_and_systemctl_bounded(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-stall-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            journal_body = "#!/bin/bash\n/usr/bin/sleep 5\nprintf 'fixture-journal-stall\\n'\n"
            systemctl_body = "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then /usr/bin/sleep 5; echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl")
            stub = make_stubs(tmp / "stubs", journal_body, systemctl_body)
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-stall-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "stall", "bounded_cleanup": True}), encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "KESTREL_LOGGER_KILL_AFTER_S": "2", "KESTREL_LOGGER_MAX_ITER": "1"},
                                              timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed, "parent backstop should not fire (stubs <=5s)")
                self.assertGreaterEqual(elapsed, 1.5, "should do bounded work, not instant skip")
                self.assertLessEqual(elapsed, 4.0, "stale t must not double budget: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_LOGGER_STARTED", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                self.assertIn("graphics_requested=1", txt)
            finally:
                unstage_check()
        CASES_RUN.append("stalling_journal_and_systemctl_bounded")

    def test_term_ignoring_killed(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-term-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            journal_body = "#!/bin/bash\ntrap '' TERM\n/usr/bin/sleep 5\nprintf 'fixture-journal-term\\n'\n"
            systemctl_body = "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl")
            stub = make_stubs(tmp / "stubs", journal_body, systemctl_body)
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-term-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "term", "bounded_cleanup": True}), encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "KESTREL_LOGGER_KILL_AFTER_S": "1", "KESTREL_LOGGER_MAX_ITER": "1"},
                                              timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed)
                self.assertGreaterEqual(elapsed, 2.0)
                self.assertLessEqual(elapsed, 4.0, "TERM-ignore must be KILLed, not full 5s: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
            finally:
                unstage_check()
        CASES_RUN.append("term_ignoring_killed")

    def test_missing_timeout_skips(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-notimeout-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            journal_body = "#!/bin/bash\n/usr/bin/sleep 5\nprintf 'should-never-run-unbounded\\n'\n"
            systemctl_body = "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then /usr/bin/sleep 5; echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl")
            stub_full = make_stubs(tmp / "stubs-full", journal_body, systemctl_body)
            # Private PATH without timeout: symlink real utils except timeout
            stub = Path(tmp) / "stubs-notimeout"
            stub.mkdir()
            for name in ("mountpoint", "readlink", "findmnt", "journalctl", "systemctl"):
                (stub / name).symlink_to(Path(stub_full) / name)
            for name in ("cat", "sync", "python3", "mktemp", "mv", "cmp", "sleep", "wc", "rm", "cp", "cut", "sleep"):
                real = shutil.which(name)
                if real:
                    try:
                        (stub / name).symlink_to(real)
                    except FileExistsError:
                        pass
            # Ensure timeout NOT in stub dir; hide /usr/sbin (real timeout lives there) from logger PATH.
            # Runner setup uses absolute mount/mkdir, so PATH without sbin still works.
            self.assertIsNone(shutil.which("timeout", path=str(stub)), "timeout must be hidden for this test")
            no_timeout_path = str(stub)
            self.assertIsNone(shutil.which("timeout", path=no_timeout_path), "timeout must be hidden from logger PATH")
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-notimeout-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "notimeout", "bounded_cleanup": True}), encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, str(stub), state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "PATH": no_timeout_path},
                                              timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed)
                self.assertLessEqual(elapsed, 4.0, "missing timeout must skip, not run 5s unbounded: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_LOGGER_NO_TIMEOUT_FAIL_OPEN", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                # Unbounded output must not appear
                journal_path = dest_host / "03-userspace-journal.log"
                if journal_path.exists():
                    self.assertNotIn("should-never-run-unbounded", journal_path.read_text(encoding="utf-8"))
            finally:
                unstage_check()
        CASES_RUN.append("missing_timeout_skips")

    def test_seconds_reset_no_extend(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-seconds-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs",
                              "#!/bin/bash\nprintf 'stub-journal\\n'\n",
                              "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-seconds-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "seconds", "bounded_cleanup": True}), encoding="utf-8")
                # Parent SECONDS reset must not extend logger budget (logger uses MONO, not SECONDS).
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "3", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2"},
                                              timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertGreaterEqual(elapsed, 2.0)
                self.assertLessEqual(elapsed, 6.0, "budget 3s + grace 3s: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertTrue("clock=BASH_MONOSECONDS" in txt or "clock=proc-uptime" in txt,
                                "must use monotonic clock, not SECONDS: %r" % txt)
            finally:
                unstage_check()
        CASES_RUN.append("seconds_reset_no_extend")

    def test_persist_rejects_invalid(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-persist-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs",
                              "#!/bin/bash\nprintf 'stub\\n'\n",
                              "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
            cmdline = tmp / "cmdline"
            cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
            last_good_pre = {"passed": False, "detail": {"reason": "last-good"}}
            last_good_status = {"reason": "last-good", "bounded_cleanup": True}
            invalid_sources = [
                ("null-detail", b'{"passed": true, "detail": null}'),
                ("nan", b'{"passed": true, "detail": {"x": NaN}}'),
                ("non-dict-top", b'["not", "a", "dict"]'),
                ("partial", b'{"reason":'),
                ("bad-utf8", b'{"reason": "\xff\xfe", "bounded_cleanup": true}'),
                ("bad-json", b'{"reason": }'),
                ("inf", b'{"passed": true, "detail": {"x": Infinity}}'),
            ]
            for idx, (kind, payload) in enumerate(invalid_sources):
                tag = "boot-invalid-%s-%d" % (tmp.name.replace("/", "-"), idx)
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, tag)
                state = tmp / ("state-%d" % idx)
                write_capture_state(state, dest_ns)
                gdir = tmp / ("gstatus-%d" % idx)
                gdir.mkdir(exist_ok=True)
                (gdir / "preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                (dest_host / "08-graphics-preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
                (dest_host / "09-graphics-status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                src = gdir / ("preflight.json" if "detail" in kind or kind in ("nan", "non-dict-top", "inf") else "status.json")
                # For status-kind invalid, use status.json; for preflight-kind, preflight.json
                if kind in ("partial", "bad-utf8", "bad-json"):
                    src = gdir / "status.json"
                src.write_bytes(payload)
                proc, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                        {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
                self.assertEqual(proc.returncode, 0, "%s: %s" % (kind, proc.stderr))
                # Last-good preserved
                if src.name == "preflight.json":
                    got = json.loads((dest_host / "08-graphics-preflight.json").read_text(encoding="utf-8"))
                    self.assertEqual(got, last_good_pre, kind)
                else:
                    got = json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8"))
                    self.assertEqual(got, last_good_status, kind)
            # Wrong names, symlink, FIFO, dir rejected
            tag2 = "boot-wrong-%s" % tmp.name.replace("/", "-")
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, tag2)
            state = tmp / "state-wrong"
            write_capture_state(state, dest_ns)
            gdir = tmp / "gstatus-wrong"
            gdir.mkdir(exist_ok=True)
            (gdir / "preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
            (gdir / "status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
            (dest_host / "08-graphics-preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
            (dest_host / "09-graphics-status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
            outside = gdir / "outside.txt"
            outside.write_text("NOT_WHITELISTED", encoding="utf-8")
            (gdir / "status.json").unlink()
            (gdir / "status.json").symlink_to(outside)
            proc, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                    {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8")), last_good_status)
            self.assertNotIn("NOT_WHITELISTED", (dest_host / "09-graphics-status.json").read_text(encoding="utf-8"))
            import os as _os
            (gdir / "status.json").unlink()
            _os.mkfifo(str(gdir / "status.json"))
            proc2, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc2.returncode, 0)
            self.assertEqual(json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8")), last_good_status)
            (gdir / "status.json").unlink()
            (gdir / "status.json").mkdir()
            proc3, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc3.returncode, 0)
            self.assertEqual(json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8")), last_good_status)
            unstage_check()
        CASES_RUN.append("persist_rejects_invalid")

    def test_persist_cap_dest_unchanged_ioerror(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-cap-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs",
                              "#!/bin/bash\nprintf 'stub\\n'\n",
                              "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
            cmdline = tmp / "cmdline"
            cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")

            def sized_preflight(total):
                prefix = '{"passed": true, "detail": {"pad": "'
                suffix = '"}}'
                pad = total - len(prefix) - len(suffix)
                assert pad > 0
                return (prefix + "P" * pad + suffix).encode("utf-8")

            at_cap = sized_preflight(65536)
            over_cap = sized_preflight(65537)
            assert len(at_cap) == 65536 and len(over_cap) == 65537
            json.loads(at_cap.decode("utf-8"))
            json.loads(over_cap.decode("utf-8"))
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-cap-%s" % tmp.name.replace("/", "-"))
            state = tmp / "state"
            write_capture_state(state, dest_ns)
            gdir = tmp / "gstatus"
            gdir.mkdir()
            (gdir / "preflight.json").write_bytes(at_cap)
            (gdir / "status.json").write_text(json.dumps({"reason": "cap", "bounded_cleanup": True}), encoding="utf-8")
            proc, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                    {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            leaf = dest_host / "08-graphics-preflight.json"
            self.assertTrue(leaf.is_file())
            self.assertEqual(leaf.read_bytes(), at_cap)
            ino_before = leaf.stat().st_ino
            # Unchanged second run must not rewrite (same inode)
            proc2, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc2.returncode, 0)
            self.assertEqual(leaf.stat().st_ino, ino_before, "unchanged must not rewrite")
            # Cap+1 rejected
            (gdir / "preflight.json").write_bytes(over_cap)
            proc3, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc3.returncode, 0)
            self.assertEqual(leaf.read_bytes(), at_cap)
            # Huge dest (200KB) must not OOM; valid small overwrites it
            leaf.write_bytes(b"X" * 200000)
            (gdir / "preflight.json").write_text(json.dumps({"passed": True, "detail": {}}), encoding="utf-8")
            proc4, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2"}, timeout=30)
            self.assertEqual(proc4.returncode, 0)
            self.assertEqual(json.loads(leaf.read_text(encoding="utf-8")), {"passed": True, "detail": {}})
            # Precommit IO error (file fsync EIO via sitecustomize) preserves old.
            # Genuine: actual persist python with injected EIO only in this run.
            last_good = {"passed": False, "detail": {"reason": "last-good"}}
            leaf.write_text(json.dumps(last_good), encoding="utf-8")
            (gdir / "preflight.json").write_text(json.dumps({"passed": True, "detail": {"new": True}}), encoding="utf-8")
            spy_dir = tmp / "fsync-spy"
            spy_dir.mkdir()
            (spy_dir / "sitecustomize.py").write_text(
                "import os\n_orig_fsync = os.fsync\n"
                "def _fail_fsync(fd):\n"
                "    raise OSError(5, 'injected fixture fsync failure')\n"
                "os.fsync = _fail_fsync\n",
                encoding="utf-8")
            proc5, _ = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                     {"KESTREL_LOGGER_BUDGET_S": "2",
                                      "PYTHONPATH": str(spy_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")},
                                     timeout=30)
            self.assertEqual(proc5.returncode, 0)
            content = leaf.read_text(encoding="utf-8")
            self.assertEqual(json.loads(content), last_good)
            unstage_check()
        CASES_RUN.append("persist_cap_dest_unchanged_ioerror")

    def test_cli_preflight_and_counts(self):
        with tempfile.TemporaryDirectory(prefix="dt26-bounds-cli-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            prefix = tmp / "collide"
            (tmp / "collide.json").write_text('{"sentinel": "keep-me"}', encoding="utf-8")
            (tmp / "collide.log").write_text("keep-me-log", encoding="utf-8")
            hash_json = file_sha256(tmp / "collide.json")
            hash_log = file_sha256(tmp / "collide.log")
            proc = subprocess.run([sys.executable, str(Path(__file__)), "--out-prefix", str(prefix)],
                                  capture_output=True, text=True, timeout=30,
                                  env={**os.environ, "TMPDIR": str(tmp)})
            self.assertEqual(proc.returncode, 2)
            self.assertIn("preserving", (proc.stderr + proc.stdout).lower())
            self.assertEqual(file_sha256(tmp / "collide.json"), hash_json)
            self.assertEqual(file_sha256(tmp / "collide.log"), hash_log)
            existing = tmp / "existing-run"
            existing.mkdir()
            (existing / "prior.txt").write_text("prior", encoding="utf-8")
            proc2 = subprocess.run([sys.executable, str(Path(__file__)), "--run-dir", str(existing)],
                                   capture_output=True, text=True, timeout=30,
                                   env={**os.environ, "TMPDIR": str(tmp)})
            self.assertEqual(proc2.returncode, 2)
            self.assertTrue((existing / "prior.txt").is_file())
        # Preserve all old evidence (never truncate archives)
        for must in (LEGACY_JSON, LEGACY_LOG, FIX_JSON, FIX_LOG,
                     SELF9, SELF9FIX,
                     T / "dt26-parent-probe-20261018T151812044665Z.json",
                     T / "dt26-parent-session-probe-20261018T152006240116Z.json",
                     T / "dt26-review-wave1-parent-findings.json",
                     T / "test-dt26-session-supervisor.py"):
            self.assertTrue(must.exists(), "must preserve %s" % must)
        payload = json.loads(FIX_JSON.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("tests_run"), 9)
        self.assertEqual(payload.get("skipped"), 0)
        CASES_RUN.append("cli_preflight_and_counts")


def main(argv=None):
    run_dir, json_path, log_path, code = resolve_outputs(argv or [])
    if code != 0:
        return code
    ok, detail = preflight_outputs(json_path, log_path)
    if not ok:
        print(detail, file=sys.stderr)
        return 2
    global RUN_TMP
    RUN_TMP = run_dir
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(Dt26Bounds)
    with open(str(log_path), "w", encoding="utf-8") as stream:
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        passed = result.testsRun - len(result.failures) - len(result.errors)
        all_cases = sorted(set(CASES_RUN))
        testcases = sorted([c for c in all_cases if c != "setup_required_files_present"])
        assert result.testsRun == len(testcases), "tests_run %d != testcases %d (%s)" % (result.testsRun, len(testcases), testcases)
        assert len(all_cases) == result.testsRun + 1, "checks %d != tests+setup" % len(all_cases)
        payload = {
            "revision": "v2-dt26-bounds",
            "tests_run": result.testsRun,
            "testcases": testcases,
            "checks": all_cases,
            "cases": all_cases,
            "passed": passed,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped) if hasattr(result, "skipped") else 0,
            "owned_files": [str(LOGGER.relative_to(P)).replace("\\", "/")],
            "native_hardware_validated": False,
            "vm_retest_required": True,
            "bounded_time": {
                "production_default_s": 260,
                "covers_session_s": 180,
                "covers_cleanup_s": 25,
                "mechanism": "BASH_MONOSECONDS else /proc/uptime fixed window + fresh remaining per op + timeout -k kill-after",
                "kill_after_s_default": 2,
                "grace_s": 3,
                "bound_note": "responsive <= budget+2, TERM-ignore <= budget+kill+1, missing-timeout skips (never unbounded); stubs <=5s; parent killpg backstop",
                "honesty_note": "best-effort, NOT hard realtime: 1s resolution + ~2s KILL grace + ~1s scheduler; D-state/sync may exceed",
            },
            "runtime_closure": {
                "timeout_present_builder": bool(shutil.which("timeout")),
                "python3_present_builder": bool(shutil.which("python3")),
                "testonly": "unshare+mount are TESTONLY for private-mount/kmsg isolation, NOT production",
                "pack_need": "integrator must ensure timeout(coreutils)+python3 in the live image (frozen SFS carries both); no new installed helper is used, the secure persist is inline in kestrel-root-log.sh",
                "supervisor_stays_run_only": True,
            },
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        stream.write("\nRESULT_JSON %s\n" % json_path)
    print(json.dumps(payload, indent=2))
    if payload["skipped"]:
        print("REFUSED: zero-skip policy violated", file=sys.stderr)
        return 2
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
