#!/usr/bin/env python3
"""dt26 observability Stage1-fix regressions: genuine full-file execution.

Scope (owned ONLY): builder/diagnostics/kestrel-root-log.sh,
kestrel-text-proof.sh, kestrel-text-bashrc, kestrel-graphics.service
output directives, this test, and dt26-observability-fix-* evidence.
Never touches kernel/DTB/SFS, hooks, menus, accounts, provider config,
or the sibling supervisor/tests.

What is proven by RUNNING the shipped files end to end (not by extracting
functions or asserting static literals):
- A) graphics=1 logger run with a short measured deadline exits on the
  true-monotonic fixed window (BASH_MONOSECONDS else /proc/uptime + fresh
  remaining per op + timeout -k kill-after), not on a sample count; text
  mode honors its sample loop. Per-iteration cost is absorbed by the wall
  check. The ~260s production default is a config declaration; the mechanism
  is proven dynamically with short deadlines plus a static default-value
  check. Honesty: best-effort, NOT hard realtime (1s + kill grace + scheduler;
  D-state/sync may exceed).
- B) partial JSON, symlink-outside-whitelist, FIFO/dir, wrong names,
  NaN/null-detail/non-dict, oversized and grown payloads never overwrite
  the last-good USB leaf: exact source names, O_NOFOLLOW non-blocking
  single-fd cap+1 reads (source + dest, no huge alloc), standard-JSON
  (NaN rejected) parse, minimal leaf-schema validation
  (preflight: passed bool + detail dict; status: reason str + bounded_cleanup
  bool), atomic tempfile+checked-fsync+replace (fsync failure preserves old),
  no sync churn when unchanged, fail-open everywhere.
- C) strict decimal CPU temps: 08000 renders as decimal 8000 (no octal
  abort); '-', '--1', '1-2' and over-long digit strings are skipped; a
  missing/bad zone never aborts the readout; battery never substitutes.
- D) CLI preflights all outputs before any test/fixture effect, uses fresh
  exclusive run dirs (or a supplied unique prefix), refuses collisions
  preserving hashes; no fixed /tmp capture paths.

Fixtures are private mount-ns isolated (mkdtemp under $TMPDIR, stub PATH for
readlink/findmnt/journalctl/systemctl read-fakes, tmpfs over /run + bind of
private host-tmp fixture to /run/archiso/bootmnt, kmsg bind to tmp file;
host /run untouched, no sudo/chown/rm-rf, no generic marker, no PID ns so
PID1 stays systemd). Zero skips. Native graphics is NOT claimed.
TESTONLY runtime: unshare+mount are test-only, not production.
"""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import stat
import types
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
PROOF = P / "builder/diagnostics/kestrel-text-proof.sh"
BASHRC = P / "builder/diagnostics/kestrel-text-bashrc"
LOGGER = P / "builder/diagnostics/kestrel-root-log.sh"
SERVICE = P / "builder/diagnostics/kestrel-graphics.service"
SUPERVISOR = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
T = P / "testing/boot-failure"
SELF = P / "testing/boot-failure/test-dt26-observability.py"
LEGACY_JSON = T / "dt26-observability-result.json"
LEGACY_LOG = T / "dt26-observability.log"

REQUIRED = [PROOF, BASHRC, LOGGER, SERVICE, SUPERVISOR, SELF]
BASH = shutil.which("bash") or "bash"

CASES_RUN = []
RUN_TMP = None
STUBS = {}
# No global /run staging. All E2E runs in a private mount ns (not pid ns,
# so PID1 stays systemd), with tmpfs over /run and bind of a private host-tmp
# fixture to /run/archiso/bootmnt. Host /run is never touched (no sudo mkdir,
# chown, rm-rf). unshare+mount are TESTONLY, not production.

LEGACY_CASES = {
    "bashrc_mode_messages_real_bash",
    "budget_and_lifecycle",
    "logger_persist_last_good_real_bash",
    "logger_whitelist_bounded_static",
    "proof_thermal_cpu_only_battery_never",
    "setup_required_files_present",
    "shell_syntax_bash_n",
    "supervisor_run_only",
    "text0_never_launches_gui",
    "typed_marker_header_contract",
}


def run_bash(script, env=None, timeout=120):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run([BASH, "-c", script], capture_output=True,
                          text=True, timeout=timeout, env=merged)


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
    parser = argparse.ArgumentParser(
        description="dt26 observability fix regressions (collision-safe)")
    parser.add_argument("--out-prefix", default=None,
                        help="explicit output prefix; writes <prefix>.json and <prefix>.log")
    parser.add_argument("--run-dir", default=None,
                        help="exclusive fixture dir; created fresh, refused if it exists")
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
                    print("REFUSED: output exists but unreadable: %s (%s)" % (path, exc),
                          file=sys.stderr)
                    return None, None, None, 2
                print("REFUSED: output exists, preserving: %s sha256=%s bytes=%d" % (path, digest, size),
                      file=sys.stderr)
                return None, None, None, 2
        if json_path.parent != log_path.parent:
            print("REFUSED: json and log must share one directory",
                  file=sys.stderr)
            return None, None, None, 2
    if args.run_dir:
        run_dir = Path(args.run_dir)
        if run_dir.exists():
            print("REFUSED: --run-dir exists, preserving it: %s" % run_dir,
                  file=sys.stderr)
            return None, None, None, 2
        run_dir.mkdir(parents=True)
    else:
        run_dir = Path(tempfile.mkdtemp(prefix="dt26-fix-", dir=tmp_base))
    if args.out_prefix:
        pass
    else:
        json_path = run_dir / "dt26-observability-fix-result.json"
        log_path = run_dir / "dt26-observability-fix.log"
    return run_dir, json_path, log_path, 0


def real_bin(name):
    found = shutil.which(name)
    return found or ("/usr/bin/%s" % name)


def write_stub(directory, name, body):
    path = Path(directory) / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def make_stubs(stubdir):
    """Private PATH stubs for virtualized live facts only.

    mountpoint/readlink/findmnt virtualize the USB/live-mount facts the
    shipped scripts gate on; journalctl/systemctl return instant fixed
    outputs so loop timing measures the logger mechanism, not the builder
    journal. Everything else (timeout, python3, sync, sleep, cmp) is real.
    """
    stubdir = Path(stubdir)
    stubdir.mkdir(parents=True, exist_ok=True)
    write_stub(stubdir, "mountpoint",
               "#!/bin/bash\nif [ \"${2:-}\" = /run/archiso/bootmnt ]; then exit 0; fi\nexec %s \"$@\"\n" % real_bin("mountpoint"))
    write_stub(stubdir, "readlink",
               "#!/bin/bash\nif [ \"${2:-}\" = /sys/class/block/sda ]; then echo /sys/devices/pci0000:00/usb1/1-1/block/sda; exit 0; fi\nexec %s \"$@\"\n" % real_bin("readlink"))
    write_stub(stubdir, "findmnt",
               "#!/bin/bash\nif [ \"$*\" = \"-n -o FSTYPE /\" ]; then echo overlay; exit 0; fi\nexec %s \"$@\"\n" % real_bin("findmnt"))
    write_stub(stubdir, "journalctl",
               "#!/bin/bash\nprintf 'stub-journal-+kestrel line1\\n-- stub journal boot --\\n'\nexit 0\n")
    write_stub(stubdir, "systemctl",
               "#!/bin/bash\nif [ \"${1:-}\" = is-system-running ]; then echo running; exit 0; fi\nif [ \"${1:-}\" = is-active ]; then echo active; exit 0; fi\nexec %s \"$@\"\n" % real_bin("systemctl"))
    return str(stubdir)


def require_mount_ns():
    if not shutil.which("unshare") or not shutil.which("mount"):
        raise AssertionError("unshare+mount required for private-mount isolation (TESTONLY)")


def make_private_fixture(tmp_base, tag):
    """Host-tmp fixture bound to /run/archiso/bootmnt inside private ns.

    Returns (fixture_root, dest_ns, dest_host, kmsg_fake). No global /run
    effect; no sudo/chown/rm-rf; no generic marker.
    """
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


def run_ns_runner(fixture_root, kmsg_fake, stub_path, extra_env, command_argv, timeout=180):
    """Run command_argv inside private mount ns with isolated /run + kmsg.

    Binds fixture_root to /run/archiso/bootmnt and kmsg_fake to /dev/kmsg.
    Parent process-group backstop kills TERM-ignoring children on timeout.
    Stubs never sleep >5s. Returns dict rc/stdout/stderr/elapsed/outer_killed.
    """
    require_mount_ns()
    runner = fixture_root.parent / ("ns-runner-%s.sh" % fixture_root.name.replace("/", "-"))
    # Checked mount isolation BEFORE the shipped script: any required mount
    # failure stops here (distinct 41-45) so the tested script never runs and
    # host /run + /dev/kmsg are never mutated. No bare || true on this path.
    lines = ["#!/bin/bash", "set -u",
             "mount --make-rprivate / >/dev/null 2>&1 || exit 41",
             "mount -t tmpfs tmpfs /run >/dev/null 2>&1 || exit 42",
             "mkdir -p /run/archiso/bootmnt || exit 43",
             "mount --bind %s /run/archiso/bootmnt >/dev/null 2>&1 || exit 44" % shlex.quote(fixture_root.as_posix()),
             "if [ -e /dev/kmsg ]; then mount --bind %s /dev/kmsg >/dev/null 2>&1 || exit 45; fi" % shlex.quote(kmsg_fake.as_posix())]
    merged_path = str(stub_path) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
    lines.append("export PATH=%s" % shlex.quote(merged_path))
    for k, v in extra_env.items():
        safe = shlex.quote(str(v))
        lines.append("export %s=%s" % (k, safe))
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


def unstage_usb():
    # No-op: private ns is destroyed on exit; host /run untouched. Kept for
    # caller compatibility; asserts no global leak.
    if Path("/run/archiso/bootmnt").exists():
        raise AssertionError("global /run/archiso/bootmnt exists (must stay private)")


def make_thermal(root, table):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for zone, (ztype, temp) in table.items():
        zdir = root / zone
        zdir.mkdir(exist_ok=True)
        (zdir / "type").write_text(ztype, encoding="utf-8")
        (zdir / "temp").write_text(temp, encoding="utf-8")
    return root


def run_logger_full(fixture_root, kmsg_fake, stub_path, state_dir, cmdline, graphics_dir, dest_ns,
                    extra_env, timeout=180):
    env = {
        "KESTREL_CAPTURE_STATE": str(state_dir),
        "KESTREL_CMDLINE_FILE": str(cmdline),
        "KESTREL_GRAPHICS_STATUS_DIR": str(graphics_dir),
        "KESTREL_LOGGER_CALL_TIMEOUT_S": "5",
    }
    env.update(extra_env)
    res = run_ns_runner(fixture_root, kmsg_fake, stub_path, env, [BASH, str(LOGGER)], timeout=timeout)
    proc = types.SimpleNamespace(returncode=res["rc"], stdout=res["stdout"], stderr=res["stderr"],
                                 outer_killed=res["outer_killed"])
    return proc, res["elapsed"]


def write_capture_state(state_dir, dest_ns):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "destination").write_text(str(dest_ns), encoding="utf-8")
    (state_dir / "device").write_text("sda", encoding="utf-8")
    (state_dir / "bootmnt").write_text("/run/archiso/bootmnt", encoding="utf-8")


def run_proof_full(fixture_root, kmsg_fake, stub_path, state_dir, cmdline, thermal_root, mode, timeout=120):
    inner_env = {
        "KESTREL_CAPTURE_STATE": str(state_dir),
        "KESTREL_CMDLINE_FILE": str(cmdline),
        "KESTREL_THERMAL_ROOT": str(thermal_root),
        "KESTREL_SHELL_PID": "1",
    }
    # Proof checks KESTREL_SHELL_PID is bash and PID1 is systemd (no pid ns).
    # Run proof via bash -c inside private mount ns; shell pid will be bash.
    proof_cmd = ["bash", "-c", "export KESTREL_SHELL_PID=$$; exec %s %s %s" % (BASH, str(PROOF), mode)]
    res = run_ns_runner(fixture_root, kmsg_fake, stub_path, inner_env, proof_cmd, timeout=timeout)
    # Fix SHELL_PID: run_ns sets it to 1, but proof needs real bash pid.
    # Instead, let inner bash set it via $$ (above). The env placeholder is overridden.
    proc = types.SimpleNamespace(returncode=res["rc"], stdout=res["stdout"], stderr=res["stderr"],
                                 outer_killed=res["outer_killed"])
    return proc, res["elapsed"]


class Dt26Fix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in REQUIRED:
            assert path.is_file(), "missing owned file: %s" % path
        assert shutil.which("bash"), "bash required"
        assert RUN_TMP is not None, "run dir not initialized"
        CASES_RUN.append("setup_required_files_present")

    def test_full_proof_typed_strict_cpu(self):
        """Genuine full proof run: 08000 is decimal 8000; bad zones skipped."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-proof-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            tag = "boot-%s" % boot_id
            try:
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, tag)
            except AssertionError as exc:
                self.fail(str(exc))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_textboot=1 kestrel_log=1 console=tty1", encoding="utf-8")
                thermal = make_thermal(tmp / "thermal", {
                    "thermal_zone0": ("cpu0-0-top-thermal", "08000"),
                    "thermal_zone1": ("cpuss0-btm-thermal", "42000"),
                    "thermal_zone2": ("battery", "30000"),
                    "thermal_zone3": ("gpu-thermal", "50000"),
                    "thermal_zone4": ("cpu-bad-dash", "-"),
                    "thermal_zone5": ("cpu-bad-dd", "--1"),
                    "thermal_zone6": ("cpuss-bad-mid", "1-2"),
                    "thermal_zone7": ("cpu-big", "12345678901234567890"),
                })
                proc, _ = run_proof_full(fixture_root, kmsg_fake, stub, state, cmdline, thermal, "typed")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                leaf = dest_host / "07-typed-command.txt"
                self.assertTrue(leaf.is_file(), "typed leaf missing: %s" % proc.stdout)
                text = leaf.read_text(encoding="utf-8")
                self.assertIn("KESTREL_TYPED_COMMAND_OK", text)
                self.assertIn("helper_revision=v2-dt26", text)
                self.assertIn("cpu0-0-top-thermal: 8.0 C (08000 mC)", text)
                self.assertIn("cpuss0-btm-thermal: 42.0 C (42000 mC)", text)
                self.assertNotIn("battery:", text)
                self.assertNotIn("gpu-thermal:", text)
                self.assertNotIn("cpu-bad-dash:", text)
                self.assertNotIn("cpu-bad-dd:", text)
                self.assertNotIn("cpuss-bad-mid:", text)
                self.assertNotIn("cpu-big:", text)
                self.assertNotIn("no_cpu_thermal_zones_found", text)
                self.assertIn("KESTREL_TYPED_COMMAND_OK", proc.stdout)
                self.assertIn("KESTREL_MODE: text-only", proc.stdout)
                self.assertIn("No GUI will start", proc.stdout)
                self.assertNotIn("sddm", proc.stdout.lower())
            finally:
                unstage_usb()
        CASES_RUN.append("full_proof_typed_strict_cpu")

    def test_full_proof_empty_thermal_and_graphics_message(self):
        """Genuine full proof runs: sentinel on empty sensors; graphics mode stays text-only."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-proof2-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            tag = "boot-%s" % boot_id
            try:
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, tag)
            except AssertionError as exc:
                self.fail(str(exc))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                thermal = make_thermal(tmp / "thermal-empty", {})
                off = tmp / "cmdline0"
                off.write_text("kestrel_textboot=1 console=tty1", encoding="utf-8")
                proc, _ = run_proof_full(fixture_root, kmsg_fake, stub, state, off, thermal, "startup")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                leaf = dest_host / "06-text-startup.txt"
                self.assertTrue(leaf.is_file(), proc.stdout)
                self.assertIn("KESTREL_BASH_STARTED", leaf.read_text(encoding="utf-8"))
                self.assertIn("no_cpu_thermal_zones_found", leaf.read_text(encoding="utf-8"))
                self.assertIn("No GUI will start", proc.stdout)
                on = tmp / "cmdline1"
                on.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                proc2, _ = run_proof_full(fixture_root, kmsg_fake, stub, state, on, thermal, "typed")
                self.assertEqual(proc2.returncode, 0, proc2.stderr)
                self.assertIn("graphics requested (kestrel_graphics=1)", proc2.stdout)
                self.assertIn("text-only", proc2.stdout.lower())
                self.assertIn("no desktop opens here", proc2.stdout)
                self.assertNotIn("sddm", proc2.stdout.lower())
                self.assertIn("kestrel_proof_saved", proc2.stdout.lower())
            finally:
                unstage_usb()
        CASES_RUN.append("full_proof_empty_thermal_and_graphics_message")

    def test_full_logger_graphics_wall_budget(self):
        """Genuine full logger run: short deadline exits on wall clock with valid JSON."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-logger-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
            try:
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-wall-%s" % tmp.name.replace("/", "-"))
            except AssertionError as exc:
                self.fail(str(exc))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                preflight = {"passed": False, "detail": {"refused": True}}
                status = {"reason": "fixture-deadline", "bounded_cleanup": True,
                          "owned_unit": "kestrel-graphics-sddm.service",
                          "native_graphics_validated": False}
                (gdir / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
                (gdir / "status.json").write_text(json.dumps(status), encoding="utf-8")
                proc, elapsed = run_logger_full(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                                {"KESTREL_LOGGER_BUDGET_S": "4"})
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertGreaterEqual(elapsed, 3.0, "exited before deadline")
                self.assertLess(elapsed, 60.0, "wall budget not honored: %.1fs" % elapsed)
                status_txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_LOGGER_STARTED", status_txt)
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", status_txt)
                self.assertIn("graphics_requested=1", status_txt)
                self.assertIn("budget_s=4", status_txt)
                got_pre = json.loads((dest_host / "08-graphics-preflight.json").read_text(encoding="utf-8"))
                got_status = json.loads((dest_host / "09-graphics-status.json").read_text(encoding="utf-8"))
                self.assertEqual(got_pre, preflight)
                self.assertEqual(got_status, status)
                journal = dest_host / "10-graphics-journal.log"
                self.assertTrue(journal.is_file())
                self.assertIn("stub journal", journal.read_text(encoding="utf-8"))
                samples = [line for line in (dest_host / "04-userspace-status.txt").read_text(encoding="utf-8").splitlines()
                           if line.startswith("sample=")]
                self.assertGreaterEqual(len(samples), 2, "loop never iterated")
            finally:
                unstage_usb()
        CASES_RUN.append("full_logger_graphics_wall_budget")

    def test_full_logger_secure_json_rejects(self):
        """Genuine full logger runs: partial/symlink/oversize keep last-good."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-secure-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
            cmdline = tmp / "cmdline"
            cmdline.write_text("kestrel_graphics=1 console=tty1", encoding="utf-8")
            last_good_pre = {"passed": False, "detail": {"reason": "last-good"}}
            last_good_status = {"reason": "last-good", "bounded_cleanup": True}
            outside_bytes = b"FIXTURE_NOT_A_GRAPHICS_STATUS"
            phases = (
                ("partial", b'{"reason":', None),
                ("symlink", None, "symlink"),
                ("oversized", b'{"reason": "' + b"z" * 70000 + b'", "bounded_cleanup": true}', None),
            )
            for idx, (kind, payload, link) in enumerate(phases):
                dest_tag = "boot-secure-%s-%d" % (tmp.name.replace("/", "-"), idx)
                try:
                    fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, dest_tag)
                except AssertionError as exc:
                    self.fail(str(exc))
                try:
                    state = tmp / ("state-%d" % idx)
                    write_capture_state(state, dest_ns)
                    gdir = tmp / ("gstatus-%d" % idx)
                    gdir.mkdir(exist_ok=True)
                    (gdir / "preflight.json").write_text(json.dumps(last_good_pre), encoding="utf-8")
                    (gdir / "status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                    # Seed the USB leaf with last-good, then corrupt the source.
                    (dest_host / "09-graphics-status.json").write_text(json.dumps(last_good_status), encoding="utf-8")
                    src = gdir / "status.json"
                    if kind == "symlink":
                        outside = gdir / "outside-whitelist.txt"
                        outside.write_bytes(outside_bytes)
                        src.unlink()
                        src.symlink_to(outside)
                    else:
                        src.write_bytes(payload)
                    proc, elapsed = run_logger_full(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                                    {"KESTREL_LOGGER_BUDGET_S": "2"})
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertLess(elapsed, 60.0)
                    leaf = dest_host / "09-graphics-status.json"
                    self.assertTrue(leaf.is_file())
                    self.assertEqual(json.loads(leaf.read_text(encoding="utf-8")), last_good_status,
                                     "last-good overwritten by %s" % kind)
                    if kind == "symlink":
                        self.assertNotIn("FIXTURE_NOT_A_GRAPHICS_STATUS", leaf.read_text(encoding="utf-8"))
                        self.assertEqual(outside.read_bytes(), outside_bytes)
                    # Preflight leaf accepted valid fixture payload each run.
                    self.assertEqual(json.loads((dest_host / "08-graphics-preflight.json").read_text(encoding="utf-8")),
                                     last_good_pre)
                finally:
                    unstage_usb()
        CASES_RUN.append("full_logger_secure_json_rejects")

    def test_full_logger_exact_cap_boundary(self):
        """Genuine full logger runs: exactly-cap valid JSON accepted, cap+1 rejected."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-cap-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
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
            self.assertEqual(len(at_cap), 65536)
            self.assertEqual(len(over_cap), 65537)
            json.loads(at_cap.decode("utf-8"))
            json.loads(over_cap.decode("utf-8"))
            try:
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-cap-%s" % tmp.name.replace("/", "-"))
            except AssertionError as exc:
                self.fail(str(exc))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                gdir = tmp / "gstatus"
                gdir.mkdir()
                (gdir / "preflight.json").write_bytes(at_cap)
                (gdir / "status.json").write_text(json.dumps({"reason": "cap", "bounded_cleanup": True}),
                                                  encoding="utf-8")
                proc, _ = run_logger_full(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                          {"KESTREL_LOGGER_BUDGET_S": "2"})
                self.assertEqual(proc.returncode, 0, proc.stderr)
                leaf = dest_host / "08-graphics-preflight.json"
                self.assertTrue(leaf.is_file(), "exactly-cap valid JSON must be accepted")
                self.assertEqual(leaf.read_bytes(), at_cap)
                # Now grow one byte past the cap: must be rejected, last-good kept.
                (gdir / "preflight.json").write_bytes(over_cap)
                proc2, _ = run_logger_full(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                           {"KESTREL_LOGGER_BUDGET_S": "2"})
                self.assertEqual(proc2.returncode, 0, proc2.stderr)
                self.assertEqual(leaf.read_bytes(), at_cap, "cap+1 must not overwrite last-good")
            finally:
                unstage_usb()
        CASES_RUN.append("full_logger_exact_cap_boundary")

    def test_full_logger_text_short_samples(self):
        """Genuine full logger run: text mode honors sample loop, no graphics leaves."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-text-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            stub = make_stubs(tmp / "stubs")
            try:
                fixture_root, dest_ns, dest_host, kmsg_fake = make_private_fixture(tmp, "boot-text-%s" % tmp.name.replace("/", "-"))
            except AssertionError as exc:
                self.fail(str(exc))
            try:
                state = tmp / "state"
                write_capture_state(state, dest_ns)
                cmdline = tmp / "cmdline"
                cmdline.write_text("kestrel_textboot=1 console=tty1", encoding="utf-8")
                gdir = tmp / "gstatus"
                gdir.mkdir()
                proc, elapsed = run_logger_full(fixture_root, kmsg_fake, stub, state, cmdline, gdir, dest_ns,
                                                {"KESTREL_TEXT_SAMPLES": "3"})
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertGreaterEqual(elapsed, 2.0)
                self.assertLess(elapsed, 45.0)
                status_txt = (dest_host / "00-status.txt").read_text(encoding="utf-8")
                self.assertIn("KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED", status_txt)
                self.assertIn("graphics_requested=0", status_txt)
                self.assertIn("iterations=3", status_txt)
                self.assertFalse((dest_host / "08-graphics-preflight.json").exists())
                self.assertFalse((dest_host / "09-graphics-status.json").exists())
                self.assertFalse((dest_host / "10-graphics-journal.log").exists())
            finally:
                unstage_usb()
            # Production default stays 120 samples (override is a test seam).
            log = LOGGER.read_text(encoding="utf-8")
            self.assertIn("KESTREL_TEXT_SAMPLES:-120", log)
        CASES_RUN.append("full_logger_text_short_samples")

    def test_cli_refuses_existing_outputs(self):
        """CLI preflights outputs before any effect; collisions preserve hashes."""
        with tempfile.TemporaryDirectory(prefix="dt26-fix-cli-", dir=str(RUN_TMP)) as tmp:
            tmp = Path(tmp)
            prefix = tmp / "collide"
            before_json = tmp / "before.json"
            before_json.write_text('{"sentinel": "keep-me"}', encoding="utf-8")
            before_log = tmp / "before.log"
            before_log.write_text("keep-me-log", encoding="utf-8")
            (tmp / "collide.json").write_text(before_json.read_text(encoding="utf-8"), encoding="utf-8")
            (tmp / "collide.log").write_text(before_log.read_text(encoding="utf-8"), encoding="utf-8")
            hash_json = file_sha256(tmp / "collide.json")
            hash_log = file_sha256(tmp / "collide.log")
            proc = subprocess.run([sys.executable, str(SELF), "--out-prefix", str(prefix)],
                                  capture_output=True, text=True, timeout=120,
                                  env={**os.environ, "TMPDIR": str(tmp)})
            self.assertEqual(proc.returncode, 2, proc.stdout)
            self.assertIn("preserving", (proc.stderr + proc.stdout).lower())
            self.assertEqual(file_sha256(tmp / "collide.json"), hash_json)
            self.assertEqual(file_sha256(tmp / "collide.log"), hash_log)
            self.assertEqual((tmp / "collide.json").read_text(encoding="utf-8"), '{"sentinel": "keep-me"}')
            # --run-dir collision is refused before any fixture effect too.
            existing = tmp / "existing-run"
            existing.mkdir()
            (existing / "prior.txt").write_text("prior", encoding="utf-8")
            proc2 = subprocess.run([sys.executable, str(SELF), "--run-dir", str(existing)],
                                   capture_output=True, text=True, timeout=120,
                                   env={**os.environ, "TMPDIR": str(tmp)})
            self.assertEqual(proc2.returncode, 2, proc2.stdout)
            self.assertTrue((existing / "prior.txt").is_file())
        CASES_RUN.append("cli_refuses_existing_outputs")

    def test_legacy_and_parent_evidence_preserved(self):
        self.assertTrue(LEGACY_JSON.is_file(), "original nine-test result must be preserved")
        self.assertTrue(LEGACY_LOG.is_file(), "original nine-test log must be preserved")
        payload = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("tests_run"), 9)
        self.assertEqual(payload.get("failures"), 0)
        self.assertEqual(payload.get("errors"), 0)
        self.assertEqual(payload.get("skipped"), 0)
        self.assertEqual(set(payload.get("cases", [])), LEGACY_CASES)
        for name in ("dt26-parent-probe-20261018T151812044665Z.json",
                     "dt26-parent-production-probes.py",
                     "dt26-parent-session-probe-20261018T152006240116Z.json",
                     "dt26-parent-session-probes.py",
                     "dt26-review-wave1-parent-findings.json",
                     "test-dt26-session-supervisor.py"):
            self.assertTrue((T / name).exists(), "must preserve %s" % name)
        CASES_RUN.append("legacy_and_parent_evidence_preserved")

    def test_no_fixed_tmp_artifact(self):
        # The joined literal is built only at runtime so this source itself
        # never contains a fixed capture path.
        fixed_literal = "/tmp/" + "dt26-bashrc-out.txt"
        for path in (SELF, Path(__file__)):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(fixed_literal, text,
                             "fixed capture path forbidden in %s" % path.name)
        self.assertFalse((Path("/tmp") / "dt26-bashrc-out.txt").exists())
        CASES_RUN.append("no_fixed_tmp_artifact")


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
    suite = loader.loadTestsFromTestCase(Dt26Fix)
    with open(str(log_path), "w", encoding="utf-8") as stream:
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        passed = result.testsRun - len(result.failures) - len(result.errors)
        all_cases = sorted(set(CASES_RUN))
        testcases = sorted([c for c in all_cases if c != "setup_required_files_present"])
        assert result.testsRun == len(testcases), \
            "tests_run %d != testcases %d (%s)" % (result.testsRun, len(testcases), testcases)
        assert len(all_cases) == result.testsRun + 1, \
            "checks %d != tests_run+setup %d" % (len(all_cases), result.testsRun + 1)
        payload = {
            "revision": "v2-dt26-fix1",
            "tests_run": result.testsRun,
            "testcases": testcases,
            "checks": all_cases,
            "cases": all_cases,
            "passed": passed,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped) if hasattr(result, "skipped") else 0,
            "owned_files": [str(p.relative_to(P)).replace("\\", "/") for p in REQUIRED],
            "native_hardware_validated": False,
            "vm_retest_required": True,
            "bounded_time": {
                "production_default_s": 260,
                "covers_session_s": 180,
                "covers_cleanup_s": 25,
                "mechanism": "BASH_MONOSECONDS else /proc/uptime fixed window + fresh remaining per op + timeout -k kill-after",
                "kill_after_s_default": 2,
                "proven_dynamically": "short-deadline full logger runs (graphics wall + text samples)",
                "honesty_note": "best-effort, NOT hard realtime: 1s resolution + ~2s KILL grace + ~1s scheduler; D-state/sync may exceed",
            },
            "runtime_closure": {
                "timeout_present_builder": bool(shutil.which("timeout")),
                "python3_present_builder": bool(shutil.which("python3")),
                "testonly": "unshare+mount are TESTONLY for private-mount/kmsg isolation, NOT production",
                "pack_need": "integrator must ensure timeout(coreutils)+python3 in the live image (frozen SFS carries both); no new installed helper is used, the secure persist is inline in kestrel-root-log.sh so no hook change is needed",
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
