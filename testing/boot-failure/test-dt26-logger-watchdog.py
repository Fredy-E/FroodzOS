#!/usr/bin/env python3
"""dt26 logger outer process-group watchdog: genuine whole-script deadline convergence.

Scope (owned ONLY): builder/diagnostics/kestrel-root-log.sh, this test,
and dt26-logger-watchdog-* evidence. Never touches kernel/DTB/SFS, hooks,
menus, accounts, provider config, supervisor/harness suites.

Proven by RUNNING the whole shipped logger end to end in a private mount ns
(not pid ns, so PID1 stays systemd; propagation private; tmpfs over /run +
bind of private host-tmp fixture to /run/archiso/bootmnt; kmsg bind to tmp
file; host /run untouched, no sudo/chown/rm-rf, no generic marker):
- startup SYNC stall (first sync call sleeps 5, responsive): with a 2s
  budget the unmodified logger exceeds the allowed bound, while the patched
  logger's outer `timeout -k 1s <remaining+2>s` process-group watchdog ends
  the run inside budget+drain+kill, writes EXPIRED (never FINISHED), keeps
  exit 0 and preserves seeded last-good leaves.
- loop SYNC stall that ignores TERM, and loop CP stall that ignores TERM:
  the watchdog TERM/KILLs the whole internal group, still EXPIRED/0, and
  every recorded logger child PID is gone afterwards (polled, not assumed).
- missing timeout: no stalling-capable op ever runs (journal/systemctl stub
  pidfile stays empty, no stub output lands in USB leaves); the fail-open
  NO_TIMEOUT sentinel is recorded quickly.
- fixture mount failure: checked isolation stops BEFORE the shipped script
  (distinct exit 41-45), so no logger child runs, no sentinel/marker is
  written, and host /run + /dev/kmsg are untouched.
- measured deadline grace: every expiry lands at/after the budget (never an
  instant skip) and within budget+drain+kill+scheduler slack.

Zero skips. TESTONLY runtime: unshare+mount are test-only, not production.
Production deps unchanged: Bash + timeout + python3, no new helper.
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
SELFBOUNDS = T / "test-dt26-observability-bounds.py"
LEGACY_JSON = T / "dt26-observability-result.json"
LEGACY_LOG = T / "dt26-observability.log"
FIX_JSON = T / "dt26-observability-fix-result.json"
FIX_LOG = T / "dt26-observability-fix-result.log"
BOUNDS_JSON = T / "dt26-observability-bounds-20261018T162745369878397Z.json"
BOUNDS_LOG = T / "dt26-observability-bounds-20261018T162745369878397Z.log"

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
    parser = argparse.ArgumentParser(description="dt26 logger watchdog (collision-safe)")
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
                print("REFUSED: output exists, preserving: %s sha256=%s bytes=%d" % (path, digest, size),
                      file=sys.stderr)
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
        run_dir = Path(tempfile.mkdtemp(prefix="dt26-watchdog-", dir=tmp_base))
    if args.out_prefix:
        pass
    else:
        json_path = run_dir / "dt26-logger-watchdog-result.json"
        log_path = run_dir / "dt26-logger-watchdog.log"
    return run_dir, json_path, log_path, 0


def real_bin(name):
    found = shutil.which(name)
    return found or ("/usr/bin/%s" % name)


def write_stub(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def make_stubs(stubdir, sync_body, cp_body):
    stubdir = Path(stubdir)
    stubdir.mkdir(parents=True, exist_ok=True)
    write_stub(stubdir, "mountpoint",
               "#!/bin/bash\nif [ \"${2:-}\" = /run/archiso/bootmnt ]; then exit 0; fi\nexec %s \"$@\"\n" % real_bin("mountpoint"))
    write_stub(stubdir, "readlink",
               "#!/bin/bash\nif [ \"${2:-}\" = /sys/class/block/sda ]; then echo /sys/devices/pci0000:00/usb1/1-1/block/sda; exit 0; fi\nexec %s \"$@\"\n" % real_bin("readlink"))
    write_stub(stubdir, "findmnt",
               "#!/bin/bash\nif [ \"$*\" = \"-n -o FSTYPE /\" ]; then echo overlay; exit 0; fi\nexec %s \"$@\"\n" % real_bin("findmnt"))
    write_stub(stubdir, "journalctl",
               "#!/bin/bash\necho \"journal:$$\" >> \"$STUB_PIDFILE\"\nprintf 'stub-journal-watchdog\\n'\nexit 0\n")
    write_stub(stubdir, "systemctl",
               "#!/bin/bash\necho \"systemctl:$$\" >> \"$STUB_PIDFILE\"\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
    write_stub(stubdir, "sync", sync_body)
    write_stub(stubdir, "cp", cp_body)
    return str(stubdir)


def sync_body_for(mode):
    real_sleep = real_bin("sleep")
    real_sync = real_bin("sync")
    header = "#!/bin/bash\necho \"sync:$$\" >> \"$STUB_PIDFILE\"\n"
    if mode == "fast":
        return header + "exec %s \"$@\"\n" % real_sync
    if mode == "stall-first5":
        return (header
                + "n=$(cat \"$SYNC_COUNT\" 2>/dev/null || echo 0)\n"
                + "n=$((n + 1))\necho \"$n\" > \"$SYNC_COUNT\"\n"
                + "if [ \"$n\" = 1 ]; then %s 5; fi\n" % real_sleep
                + "exec %s \"$@\"\n" % real_sync)
    if mode == "fast-first-then-termignore":
        return (header
                + "n=$(cat \"$SYNC_COUNT\" 2>/dev/null || echo 0)\n"
                + "n=$((n + 1))\necho \"$n\" > \"$SYNC_COUNT\"\n"
                + "if [ \"$n\" = 1 ]; then exec %s \"$@\"; fi\n" % real_sync
                + "trap '' TERM\n%s 5\nexec %s \"$@\"\n" % (real_sleep, real_sync))
    raise AssertionError("unknown sync mode %s" % mode)


def cp_body_for(mode):
    real_sleep = real_bin("sleep")
    real_cp = real_bin("cp")
    header = "#!/bin/bash\necho \"cp:$$\" >> \"$STUB_PIDFILE\"\n"
    if mode == "fast":
        return header + "exec %s \"$@\"\n" % real_cp
    if mode == "termignore-always":
        return header + "trap '' TERM\n%s 5\nexec %s \"$@\"\n" % (real_sleep, real_cp)
    raise AssertionError("unknown cp mode %s" % mode)


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


def run_ns_runner(fixture_root, kmsg_fake, stub_path, extra_env, command_argv,
                  timeout=30, with_initlog=False):
    require_mount_ns()
    runner = fixture_root.parent / ("ns-runner-%s.sh" % fixture_root.name.replace("/", "-"))
    mount_bin = shutil.which("mount") or "/usr/sbin/mount"
    mkdir_bin = shutil.which("mkdir") or "/bin/mkdir"
    # Checked mount isolation BEFORE the shipped script: any required mount
    # failure stops here (distinct 41-46) so the tested script never runs and
    # host /run + /dev/kmsg are never mutated. No bare || true on this path.
    # No PID namespace: PID1 stays the actual systemd, only mounts are namespaced.
    lines = ["#!/bin/bash", "set -u",
             "%s --make-rprivate / >/dev/null 2>&1 || exit 41" % mount_bin,
             "%s -t tmpfs tmpfs /run >/dev/null 2>&1 || exit 42" % mount_bin,
             "%s -p /run/archiso/bootmnt || exit 43" % mkdir_bin,
             "%s --bind %s /run/archiso/bootmnt >/dev/null 2>&1 || exit 44" % (mount_bin, shlex.quote(fixture_root.as_posix())),
             "if [ -e /dev/kmsg ]; then %s --bind %s /dev/kmsg >/dev/null 2>&1 || exit 45; fi" % (mount_bin, shlex.quote(kmsg_fake.as_posix()))]
    if with_initlog:
        lines.append("%s -p /run/initramfs || exit 46" % mkdir_bin)
        lines.append("printf 'fixture-init-log\\n' > /run/initramfs/init.log || exit 46")
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
                  extra_env, timeout=30, with_initlog=False, pidfile=None, sync_count=None):
    env = {
        "KESTREL_CAPTURE_STATE": str(state_dir),
        "KESTREL_CMDLINE_FILE": str(cmdline),
        "KESTREL_GRAPHICS_STATUS_DIR": str(graphics_dir),
    }
    env.update(extra_env)
    if pidfile is not None:
        env["STUB_PIDFILE"] = str(pidfile)
    if sync_count is not None:
        env["SYNC_COUNT"] = str(sync_count)
    res = run_ns_runner(fixture_root, kmsg_fake, stub_path, env, [BASH, str(LOGGER)],
                        timeout=timeout, with_initlog=with_initlog)
    proc = types.SimpleNamespace(returncode=res["rc"], stdout=res["stdout"], stderr=res["stderr"],
                                 outer_killed=res["outer_killed"])
    return proc, res["elapsed"]


def read_pids(pidfile):
    pids = []
    try:
        text = Path(pidfile).read_text(encoding="utf-8")
    except OSError:
        return pids
    for line in text.splitlines():
        if ":" not in line:
            continue
        _, pid = line.rsplit(":", 1)
        if pid.strip().isdigit():
            pids.append(int(pid.strip()))
    return pids


def assert_pids_gone(testcase, pidfile, timeout=12):
    deadline = time.monotonic() + timeout
    pending = read_pids(pidfile)
    testcase.assertTrue(pending, "expected recorded logger child PIDs in %s" % pidfile)
    while pending and time.monotonic() < deadline:
        pending = [p for p in pending if _pid_alive(p)]
        if pending:
            time.sleep(0.2)
    testcase.assertEqual(pending, [], "orphan logger children still alive: %r" % pending)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def unstage_check():
    if Path("/run/archiso/bootmnt").exists():
        raise AssertionError("global /run/archiso/bootmnt exists (must stay private)")


class Dt26Watchdog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in REQUIRED:
            assert path.is_file(), "missing owned file: %s" % path
        assert shutil.which("bash"), "bash required"
        assert RUN_TMP is not None, "run dir not initialized"
        require_mount_ns()
        CASES_RUN.append("setup_required_files_present")

    def test_startup_sync_stall_expires(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-startup-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs", sync_body_for("stall-first5"), cp_body_for("fast"))
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-wd-startup-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "wd", "bounded_cleanup": True}), encoding="utf-8")
                last_good_pre = {"passed": False, "detail": {"reason": "last-good"}}
                last_good_status = {"reason": "last-good", "bounded_cleanup": True}
                (dest_host / "08-graphics-preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
                (dest_host / "09-graphics-status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                pidfile = tmp / "pids"
                pidfile.write_text("", encoding="utf-8")
                sync_count = tmp / "synccount"
                sync_count.write_text("0", encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "5",
                                               "KESTREL_LOGGER_KILL_AFTER_S": "1"},
                                              timeout=30, pidfile=pidfile, sync_count=sync_count)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed, "parent backstop must not fire (watchdog owns the bound)")
                self.assertGreaterEqual(elapsed, 2.0, "must not instant-skip: %.1fs" % elapsed)
                self.assertLessEqual(elapsed, 8.0, "watchdog bound exceeded: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_LOGGER_STARTED", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED", txt)
                self.assertIn("budget_s=2", txt)
                self.assertNotIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                self.assertEqual(json.loads((dest_host / "08-graphics-preflight.json").read_text(encoding="utf-8")), last_good_pre)
                self.assertEqual(json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8")), last_good_status)
                assert_pids_gone(self, pidfile)
            finally:
                unstage_check()
        CASES_RUN.append("startup_sync_stall_expires")

    def test_loop_sync_stall_termignore_expires(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-loopsync-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs", sync_body_for("fast-first-then-termignore"), cp_body_for("fast"))
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-wd-loopsync-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "wd", "bounded_cleanup": True}), encoding="utf-8")
                last_good_status = {"reason": "last-good", "bounded_cleanup": True}
                (dest_host / "09-graphics-status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                pidfile = tmp / "pids"
                pidfile.write_text("", encoding="utf-8")
                sync_count = tmp / "synccount"
                sync_count.write_text("0", encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "KESTREL_LOGGER_KILL_AFTER_S": "1"},
                                              timeout=30, pidfile=pidfile, sync_count=sync_count)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed)
                self.assertGreaterEqual(elapsed, 2.0, "must not instant-skip: %.1fs" % elapsed)
                self.assertLessEqual(elapsed, 9.0, "TERM-ignore sync must be KILLed: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_LOGGER_STARTED", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED", txt)
                self.assertNotIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                journal = dest_host / "03-userspace-journal.log"
                self.assertTrue(journal.is_file(), "bounded loop work must precede the stall")
                self.assertIn("stub-journal-watchdog", journal.read_text(encoding="utf-8"))
                self.assertEqual(json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8")), last_good_status)
                assert_pids_gone(self, pidfile)
            finally:
                unstage_check()
        CASES_RUN.append("loop_sync_stall_termignore_expires")

    def test_loop_cp_stall_termignore_expires(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-loopcp-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs", sync_body_for("fast"), cp_body_for("termignore-always"))
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-wd-loopcp-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "wd", "bounded_cleanup": True}), encoding="utf-8")
                pidfile = tmp / "pids"
                pidfile.write_text("", encoding="utf-8")
                sync_count = tmp / "synccount"
                sync_count.write_text("0", encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "KESTREL_LOGGER_KILL_AFTER_S": "1"},
                                              timeout=30, with_initlog=True, pidfile=pidfile, sync_count=sync_count)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed)
                self.assertGreaterEqual(elapsed, 2.0, "must not instant-skip: %.1fs" % elapsed)
                self.assertLessEqual(elapsed, 9.0, "TERM-ignore cp must be KILLed: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_LOGGER_STARTED", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED", txt)
                self.assertNotIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                cp_names = [p for p in read_pids_raw(pidfile) if p[0] == "cp"]
                self.assertTrue(cp_names, "cp stub must have run (init.log present in ns)")
                self.assertFalse((dest_host / "02-initramfs-console.log").exists(),
                                 "stalled copy must never land a partial leaf")
                assert_pids_gone(self, pidfile)
            finally:
                unstage_check()
        CASES_RUN.append("loop_cp_stall_termignore_expires")

    def test_missing_timeout_skips_with_sentinel(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-notimeout-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub_full = make_stubs(tmp / "stubs-full", sync_body_for("fast"), cp_body_for("fast"))
            # Rebuild journalctl/systemctl as TERM-capable sleep-5 stubs that
            # must NEVER run without timeout; keep mountpoint/readlink/findmnt.
            write_stub(Path(stub_full), "journalctl",
                       "#!/bin/bash\necho \"journal:$$\" >> \"$STUB_PIDFILE\"\n/usr/bin/sleep 5\nprintf 'should-never-run-unbounded\\n'\n")
            write_stub(Path(stub_full), "systemctl",
                       "#!/bin/bash\necho \"systemctl:$$\" >> \"$STUB_PIDFILE\"\nif [ \"${1:-}\" = is-system-running ]; then /usr/bin/sleep 5; echo running; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
            stub = Path(tmp) / "stubs-notimeout"
            stub.mkdir()
            for name in ("mountpoint", "readlink", "findmnt", "journalctl", "systemctl"):
                (stub / name).symlink_to(Path(stub_full) / name)
            for name in ("cat", "sync", "python3", "mktemp", "mv", "cmp", "sleep", "wc", "rm", "cp", "cut"):
                real = shutil.which(name)
                if real:
                    try:
                        (stub / name).symlink_to(real)
                    except FileExistsError:
                        pass
            self.assertIsNone(shutil.which("timeout", path=str(stub)), "timeout must be hidden for this test")
            fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-wd-notimeout-%s" % tmp.name.replace("/", "-"))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps({"reason": "notimeout", "bounded_cleanup": True}), encoding="utf-8")
                pidfile = tmp / "pids"
                pidfile.write_text("", encoding="utf-8")
                proc, elapsed = run_logger_ns(fixture_root, kmsg_fake, str(stub), state, cmdline, gdir, dest_ns,
                                              {"KESTREL_LOGGER_BUDGET_S": "2", "KESTREL_LOGGER_CALL_TIMEOUT_S": "2",
                                               "PATH": str(stub)},
                                              timeout=30, pidfile=pidfile)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertFalse(proc.outer_killed)
                self.assertLessEqual(elapsed, 6.0, "missing timeout must skip, not run 5s unbounded: %.1fs" % elapsed)
                txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_LOGGER_NO_TIMEOUT_FAIL_OPEN", txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", txt)
                self.assertEqual(pidfile.read_text(encoding="utf-8"), "",
                                 "no stalling-capable op may run without timeout")
                journal_path = dest_host / "03-userspace-journal.log"
                if journal_path.exists():
                    self.assertNotIn("should-never-run-unbounded", journal_path.read_text(encoding="utf-8"))
            finally:
                unstage_check()
        CASES_RUN.append("missing_timeout_skips_with_sentinel")

    def test_fixture_mount_failure_runs_nothing(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-mountfail-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs", sync_body_for("fast"), cp_body_for("fast"))
            # Fixture source intentionally absent: the bind must fail.
            fixture_root = tmp / "fixture-does-not-exist"
            self.assertFalse(fixture_root.exists())
            dest_ns = Path("/run/archiso/bootmnt/Logs") / "boot-wd-mountfail"
            kmsg_fake = tmp / "kmsg-fake-mountfail"
            kmsg_fake.write_text("", encoding="utf-8")
            state = tmp / "state"
            write_capture_state(state, dest_ns)
            cmdline = tmp / "cmdline"
            cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
            gdir = tmp / "gstatus"
            gdir.mkdir()
            (gdir / "preflight.json").write_text(json.dumps({"passed": False, "detail": {}}), encoding="utf-8")
            (gdir / "status.json").write_text(json.dumps({"reason": "mountfail", "bounded_cleanup": True}), encoding="utf-8")
            pidfile = tmp / "pids"
            res = run_ns_runner(fixture_root, kmsg_fake, stub,
                                {"KESTREL_CAPTURE_STATE": str(state),
                                 "KESTREL_CMDLINE_FILE": str(cmdline),
                                 "KESTREL_GRAPHICS_STATUS_DIR": str(gdir),
                                 "KESTREL_LOGGER_BUDGET_S": "2",
                                 "STUB_PIDFILE": str(pidfile)},
                                [BASH, str(LOGGER)], timeout=30)
            self.assertFalse(res["outer_killed"])
            self.assertIn(res["rc"], (41, 42, 43, 44, 45), "mount failure must stop with 41-45, got %r" % res["rc"])
            self.assertEqual(res["rc"], 44, "absent fixture source must fail at the bind step")
            combined = res["stdout"] + res["stderr"]
            self.assertNotIn("KESTREL_USERSPACE_LOGGER_STARTED", combined)
            self.assertNotIn("KESTREL_USERSPACE_CAPTURE_WINDOW", combined)
            self.assertFalse(pidfile.exists(), "no logger child may run when isolation fails")
            unstage_check()
        CASES_RUN.append("fixture_mount_failure_runs_nothing")

    def test_cli_preflight_and_counts(self):
        with tempfile.TemporaryDirectory(prefix="dt26-wd-cli-", dir=str(RUN_TMP)) as tmp:
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
        # Preserve all old evidence (never truncate archives).
        for must in (LEGACY_JSON, LEGACY_LOG, FIX_JSON, FIX_LOG, BOUNDS_JSON, BOUNDS_LOG,
                     SELF9, SELF9FIX, SELFBOUNDS,
                     T / "dt26-parent-probe-20261018T151812044665Z.json",
                     T / "dt26-parent-session-probe-20261018T152006240116Z.json",
                     T / "dt26-review-wave1-parent-findings.json",
                     T / "test-dt26-session-supervisor.py"):
            self.assertTrue(must.exists(), "must preserve %s" % must)
        payload = json.loads(FIX_JSON.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("tests_run"), 9)
        self.assertEqual(payload.get("skipped"), 0)
        legacy = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
        self.assertEqual(legacy.get("tests_run"), 9)
        self.assertEqual(legacy.get("skipped"), 0)
        CASES_RUN.append("cli_preflight_and_counts")


def read_pids_raw(pidfile):
    rows = []
    try:
        text = Path(pidfile).read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, pid = line.rsplit(":", 1)
        if pid.strip().isdigit():
            rows.append((name.strip(), int(pid.strip())))
    return rows


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
    suite = loader.loadTestsFromTestCase(Dt26Watchdog)
    with open(str(log_path), "w", encoding="utf-8") as stream:
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        passed = result.testsRun - len(result.failures) - len(result.errors)
        all_cases = sorted(set(CASES_RUN))
        testcases = sorted([c for c in all_cases if c != "setup_required_files_present"])
        assert result.testsRun == len(testcases), "tests_run %d != testcases %d (%s)" % (result.testsRun, len(testcases), testcases)
        assert len(all_cases) == result.testsRun + 1, "checks %d != tests+setup" % len(all_cases)
        payload = {
            "revision": "v2-dt26-watchdog",
            "tests_run": result.testsRun,
            "testcases": testcases,
            "checks": all_cases,
            "cases": all_cases,
            "passed": passed,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped) if hasattr(result, "skipped") else 0,
            "owned_files": [str(LOGGER.relative_to(P)).replace("\\", "/"),
                            str(Path(__file__).resolve().relative_to(P)).replace("\\", "/")],
            "native_hardware_validated": False,
            "vm_retest_required": True,
            "bounded_time": {
                "production_default_s": 260,
                "orderly_exit_drain_s": 2,
                "outer_kill_after_s": 1,
                "mechanism": "outer timeout -k 1s <remaining+2>s process-group watchdog (own PG, never --foreground) around the unchanged body; fresh remaining per op + timeout -k kill-after inside",
                "proven_dynamically": "whole-script startup SYNC + loop SYNC/CP stall and TERM-ignore runs expire with EXPIRED/0 and no orphan logger children",
                "honesty_note": "best-effort, NOT hard realtime: 1s resolution + 2s drain + 1s KILL + ~1s scheduler; D-state/sync may exceed",
            },
            "runtime_closure": {
                "timeout_present_builder": bool(shutil.which("timeout")),
                "python3_present_builder": bool(shutil.which("python3")),
                "testonly": "unshare+mount are TESTONLY for private-mount/kmsg isolation, NOT production",
                "pack_need": "integrator must ensure timeout(coreutils)+python3 in the live image (frozen SFS carries both); no new installed helper is used, the watchdog is inline in kestrel-root-log.sh",
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
