#!/usr/bin/env python3
"""Focused dt26 native text/graphics diagnostic observability tests.

Scope (owned ONLY): builder/diagnostics/kestrel-root-log.sh,
kestrel-text-proof.sh, kestrel-text-bashrc, kestrel-graphics.service
output directives, plus this test and its dt26-observability-* evidence.
Never touches kernel/DTB/SFS, hooks, menus, accounts, or provider config.

What is verified (fail-open for boot, bounded for logging):
- text graphics=0 never launches a GUI; typed proof keeps its marker/header
  atomic temp+rename+sync contract and startup proof.
- typed command prints a concise real CPU readout from cpu/cpuss zones;
  battery data is never substituted; missing sensors do not wedge.
- helper revision is labeled helper identity, never UKI identity.
- USB logger alone persists ONLY whitelisted
  /run/kestrel-graphics/preflight.json + status.json and bounded
  kestrel-graphics.service journal output, with atomic last-good,
  strict byte caps, no secret/environment dumps.
- supervisor stays /run-only (no USB writes added there).
- exact-token kestrel_graphics=1 detection; graphics=1 observes a ~260s
  true-monotonic (BASH_MONOSECONDS else /proc/uptime, never SECONDS) fixed
  window from logger start (>= 180s session + 25s cleanup) with fresh
  remaining before every external and timeout -k kill-after bounded calls;
  text keeps 120 samples (KESTREL_TEXT_SAMPLES override is a test seam only,
  default 120 preserved).
- logger failures never become boot blockers (fail-open, exit 0 after start).
- parent unit keeps ExecStartPre/Post, Restart=no, TimeoutStopSec=30 and
  gains only StandardOutput/StandardError journal+console directives.

Genuine shell: behavioral unit claims execute real bash from the shipped
files (bash -n plus extracted real functions run against fixtures).
Extracted-function and static checks are labeled as unit scope only; genuine
invoked full-file loop/helper coverage lives in
test-dt26-observability-fix.py, which runs the shipped logger and proof end
to end against safe fixtures. Zero skips: missing files or missing bash are
hard failures, never skips.

CLI safety: outputs are preflighted BEFORE any test or fixture effect. By
default results go to a fresh exclusive run dir under $TMPDIR; --out-prefix
selects explicit outputs but refuses collisions, preserving existing
JSON/log hashes. The archived dt26-observability-result.json/.log are never
truncated by a default run.
"""
import argparse
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
PROOF = P / "builder/diagnostics/kestrel-text-proof.sh"
BASHRC = P / "builder/diagnostics/kestrel-text-bashrc"
LOGGER = P / "builder/diagnostics/kestrel-root-log.sh"
SERVICE = P / "builder/diagnostics/kestrel-graphics.service"
SUPERVISOR = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
T = P / "testing/boot-failure"
LEGACY_RESULT_JSON = T / "dt26-observability-result.json"
LEGACY_RESULT_LOG = T / "dt26-observability.log"

REQUIRED = [PROOF, BASHRC, LOGGER, SERVICE, SUPERVISOR]
BASH = shutil.which("bash") or shutil.which("bash.exe") or "bash"

CASES_RUN = []
RUN_TMP = None


def run_bash(script, env=None, timeout=60):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    proc = subprocess.run([BASH, "-c", script], capture_output=True,
                          text=True, timeout=timeout, env=merged)
    return proc


def file_sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight_outputs(json_path, log_path):
    """Refuse before ANY test/fixture effect if outputs already exist.

    Returns (ok, detail). ok False means the caller must exit without
    running anything, preserving the existing files untouched.
    """
    for path in (json_path, log_path):
        if path.exists():
            try:
                digest = file_sha256(path)
                size = path.stat().st_size
            except OSError as exc:
                return False, "exists but unreadable: %s (%s)" % (path, exc)
            return False, "refusing: output exists, preserving hash: %s sha256=%s bytes=%d" % (path, digest, size)
    if json_path.parent != log_path.parent:
        return False, "json and log must share one directory"
    return True, "clear"


def resolve_outputs(argv):
    """Decide output paths. Default: fresh exclusive run dir, never legacy.

    Collision preflight happens BEFORE any mkdir/mkdtemp effect: an
    --out-prefix that already exists is refused without creating a run dir.
    """
    parser = argparse.ArgumentParser(
        description="dt26 observability unit tests (collision-safe outputs)")
    parser.add_argument("--out-prefix", default=None,
                        help="explicit output prefix; writes <prefix>.json and <prefix>.log")
    parser.add_argument("--run-dir", default=None,
                        help="exclusive fixture dir; created fresh, refused if it exists")
    args = parser.parse_args(argv)
    tmp_base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    # Pre-compute out-prefix collision BEFORE any mkdir/mkdtemp (no effects yet).
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
        run_dir = Path(tempfile.mkdtemp(prefix="dt26-observability-",
                                        dir=tmp_base))
    if args.out_prefix:
        pass
    else:
        json_path = run_dir / "dt26-observability-result.json"
        log_path = run_dir / "dt26-observability.log"
    return run_dir, json_path, log_path, 0


def extract_function(source_text, name):
    """Extract a real `name() { ... }` function body from shell source.

    Unit scope only: proves the extracted function behaves in real bash,
    not that the whole shipped file executes. Full-file coverage lives in
    test-dt26-observability-fix.py.
    """
    lines = source_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^" + re.escape(name) + r"\(\)\s*\{", line.strip()):
            start = i
            break
    assert start is not None, "function %s not found in shipped file" % name
    depth = 0
    for j in range(start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if j > start and depth <= 0:
            return "\n".join(lines[start:j + 1])
    raise AssertionError("unbalanced function %s" % name)


class Dt26Observability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in REQUIRED:
            assert path.is_file(), "missing owned file: %s" % path
        assert shutil.which("bash") or Path(BASH).exists(), "bash required"
        CASES_RUN.append("setup_required_files_present")

    def test_shell_syntax_real_bash(self):
        for path in (PROOF, BASHRC, LOGGER):
            proc = subprocess.run([BASH, "-n", str(path)],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0,
                             "bash -n failed for %s: %s" % (path.name, proc.stderr))
        CASES_RUN.append("shell_syntax_bash_n")

    def test_text0_never_launches_gui(self):
        proof = PROOF.read_text(encoding="utf-8")
        rc = BASHRC.read_text(encoding="utf-8")
        for text, name in ((proof, "proof"), (rc, "bashrc")):
            self.assertNotIn("systemctl start", text, name)
            self.assertNotIn("systemctl restart", text, name)
            self.assertNotIn("kestrel-graphics-supervisor", text, name)
            self.assertNotIn("sddm", text.lower(), name)
        self.assertIn("No GUI will start", rc)
        self.assertIn("does not open a desktop", rc)
        self.assertIn("kestrel_graphics=1", rc)
        # Exact-token match (surrounding spaces), not substring.
        self.assertRegex(rc, r'case\s+" \$_kestrel_cmdline "\s+in\s+\*" kestrel_graphics=1 "\*')
        CASES_RUN.append("text0_never_launches_gui")

    def test_typed_marker_header_contract_static(self):
        proof = PROOF.read_text(encoding="utf-8")
        self.assertIn("marker=KESTREL_TYPED_COMMAND_OK", proof)
        self.assertIn("marker=KESTREL_BASH_STARTED", proof)
        self.assertIn("leaf=06-text-startup.txt", proof)
        self.assertIn("leaf=07-typed-command.txt", proof)
        self.assertIn('mktemp "$dest/.text-proof-XXXXXX"', proof)
        self.assertIn('mv -f -- "$temp" "$dest/$leaf"', proof)
        self.assertIn('sync -f "$temp"', proof)
        self.assertIn('sync -f "$dest/$leaf"', proof)
        # Helper revision labeled helper identity, never bare UKI-style revision=.
        self.assertIn("helper_revision=v2-dt26", proof)
        self.assertIn("not UKI", proof)
        self.assertNotRegex(proof, r"(?m)^\s*'revision=v2-",
                            "bare revision= label reads as UKI identity")
        CASES_RUN.append("typed_marker_header_contract")

    def test_proof_thermal_strict_decimal_unit(self):
        """Unit scope: extracted readout in real bash; strict decimal only."""
        proof = PROOF.read_text(encoding="utf-8")
        func = extract_function(proof, "kestrel_cpu_thermal_readout")
        with tempfile.TemporaryDirectory(prefix="dt26-thermal-") as tmp:
            root = Path(tmp)
            for zone, temp in (("thermal_zone0", ("cpu0-0-top-thermal", "42000")),
                               ("thermal_zone1", ("cpuss0-btm-thermal", "43500")),
                               ("thermal_zone2", ("battery", "30000")),
                               ("thermal_zone3", ("gpu-thermal", "50000"))):
                zdir = root / zone
                zdir.mkdir()
                (zdir / "type").write_text(temp[0])
                (zdir / "temp").write_text(temp[1])
            harness = "thermal_root=%s\n" % root.as_posix() + func + "\nkestrel_cpu_thermal_readout\n"
            proc = run_bash(harness)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("cpu0-0-top-thermal", proc.stdout)
            self.assertIn("cpuss0-btm-thermal", proc.stdout)
            self.assertNotIn("battery", proc.stdout)
            self.assertNotIn("gpu-thermal", proc.stdout)
            # Missing sensors: empty root never wedges, prints sentinel.
            with tempfile.TemporaryDirectory(prefix="dt26-thermal-empty-") as tmp2:
                harness2 = "thermal_root=%s\n" % Path(tmp2).as_posix() + func + "\nkestrel_cpu_thermal_readout\n"
                proc2 = run_bash(harness2)
                self.assertEqual(proc2.returncode, 0, proc2.stderr)
                self.assertIn("no_cpu_thermal_zones_found", proc2.stdout)
                self.assertIn("battery never substituted", proc2.stdout)
        # Strict decimal table: 08000 is decimal 8000, never octal-abort;
        # '-', '--1', '1-2' and over-long digit strings are skipped, and a
        # bad zone can never abort the readout (exit stays 0).
        with tempfile.TemporaryDirectory(prefix="dt26-thermal-strict-") as tmp3:
            root3 = Path(tmp3)
            zone = root3 / "thermal_zone0"
            zone.mkdir()
            (zone / "type").write_text("cpu0-0-top-thermal")
            for value, expect in (("08000", "8.0 C (08000 mC)"),
                                  ("42000", "42.0 C (42000 mC)"),
                                  ("-05000", "-5.0 C (-05000 mC)"),
                                  ("0000000", "0.0 C (0000000 mC)")):
                (zone / "temp").write_text(value)
                harness = "thermal_root=%s\n" % root3.as_posix() + func + "\nkestrel_cpu_thermal_readout\n"
                proc = run_bash(harness)
                self.assertEqual(proc.returncode, 0,
                                 "bad-zone abort for %r: %s" % (value, proc.stderr))
                self.assertIn(expect, proc.stdout, "value %r" % value)
            for value in ("-", "--1", "1-2", "12345678",
                          "99999999999999999999", "+12", "12 ", " 12"):
                (zone / "temp").write_text(value)
                harness = "thermal_root=%s\n" % root3.as_posix() + func + "\nkestrel_cpu_thermal_readout\n"
                proc = run_bash(harness)
                self.assertEqual(proc.returncode, 0,
                                 "bad-zone abort for %r: %s" % (value, proc.stderr))
                self.assertIn("no_cpu_thermal_zones_found", proc.stdout,
                              "malformed %r must be skipped" % value)
                self.assertNotIn("cpu0-0-top-thermal:", proc.stdout,
                                 "malformed %r must not render" % value)
        CASES_RUN.append("proof_thermal_strict_decimal_unit")

    def test_bashrc_mode_messages_real_bash(self):
        with tempfile.TemporaryDirectory(prefix="dt26-cmdline-") as tmp:
            off = Path(tmp) / "cmdline0"
            off.write_text("kestrel_textboot=1 kestrel_log=1 kestrel_graphics=0 console=tty1")
            on = Path(tmp) / "cmdline1"
            on.write_text("kestrel_textboot=1 kestrel_graphics=1 console=tty1")
            tricky = Path(tmp) / "cmdlineX"
            tricky.write_text("kestrel_graphics=10")
            for fixture, expect_graphics in ((off, False), (on, True), (tricky, False)):
                # Per-test temporary capture path: never a fixed /tmp file.
                fd, out_path = tempfile.mkstemp(prefix="dt26-bashrc-out-",
                                                dir=tmp)
                os.close(fd)
                # Source the REAL bashrc in a clean bash with a stubbed proof
                # path (absolute target absent -> || true keeps us alive).
                # Private mount ns + kmsg bind so host dmesg untouched.
                # Checked isolation: any mount failure stops BEFORE sourcing
                # the shipped bashrc (no || true on the isolation path).
                kmsg_fake = Path(tmp) / ("kmsg-fake-%s" % fixture.name)
                kmsg_fake.write_text("", encoding="utf-8")
                inner = ("mount --make-rprivate / >/dev/null 2>&1 || exit 41; "
                         + "if [ -e /dev/kmsg ]; then mount --bind %s /dev/kmsg >/dev/null 2>&1 || exit 45; fi; " % shlex.quote(kmsg_fake.as_posix())
                         + "export KESTREL_CMDLINE_FILE=%s; " % shlex.quote(fixture.as_posix())
                         + "export PATH=/usr/bin:/bin; "
                         + "set +u; "
                         + "PS1=x; "
                         + "source %s >%s 2>&1 || true; " % (shlex.quote(BASHRC.as_posix()), shlex.quote(out_path))
                         + "cat %s" % shlex.quote(out_path))
                try:
                    proc = subprocess.run(
                        ["unshare", "-rm", "--propagation", "private",
                         "bash", "-c", inner],
                        capture_output=True, text=True, timeout=30,
                        env=dict(os.environ))
                except FileNotFoundError as exc:
                    self.fail("unshare required for kmsg isolation: %s" % exc)
                self.assertEqual(proc.returncode, 0,
                                 "checked mount/kmsg isolation failed: %s" % proc.stderr)
                # kmsg_fake may contain the KESTREL_BASH_STARTED line; host dmesg untouched.
                out = proc.stdout
                try:
                    if expect_graphics:
                        self.assertIn("REQUESTED (kestrel_graphics=1)", out,
                                      "graphics message missing: %r" % out)
                        self.assertIn("text-only", out.lower())
                    else:
                        self.assertIn("text-only", out.lower())
                        self.assertIn("No GUI will start", out)
                    self.assertIn("does not open a desktop", out)
                finally:
                    try:
                        os.unlink(out_path)
                    except OSError:
                        pass
            forbidden_fixed_capture = Path("/tmp") / "dt26-bashrc-out.txt"
            self.assertFalse(forbidden_fixed_capture.exists(),
                             "fixed /tmp capture path must not be used")
        CASES_RUN.append("bashrc_mode_messages_real_bash")

    def test_logger_wall_budget_and_bounds_static(self):
        """Unit scope: logger declares a wall budget, not sample-seconds."""
        log = LOGGER.read_text(encoding="utf-8")
        self.assertIn("08-graphics-preflight.json", log)
        self.assertIn("09-graphics-status.json", log)
        self.assertIn("10-graphics-journal.log", log)
        self.assertIn("preflight.json", log)
        self.assertIn("status.json", log)
        self.assertIn("kestrel-graphics.service", log)
        self.assertIn("graphics_json_max=65536", log)
        self.assertIn("graphics_journal_max=131072", log)
        # Text keeps the validated 120-sample default (env override is a
        # test seam only, default preserved).
        self.assertIn("KESTREL_TEXT_SAMPLES:-120", log)
        # Graphics uses a monotonic wall budget, not sample counts.
        self.assertIn("KESTREL_LOGGER_BUDGET_S:-260", log)
        self.assertNotIn("total_samples=260", log,
                         "260 iterations are not 260 seconds")
        self.assertIn("BASH_MONOSECONDS", log)
        self.assertIn("proc-uptime", log)
        self.assertNotIn("logger_start=$SECONDS", log)
        self.assertNotIn("logger_deadline - SECONDS", log)
        self.assertIn("logger_deadline", log)
        self.assertIn("logger_remaining_s", log)
        self.assertIn("logger_now_s", log)
        self.assertIn("logger_call_timeout_s", log)
        self.assertIn("timeout -k", log)
        self.assertIn("KESTREL_LOGGER_KILL_AFTER_S", log)
        self.assertIn("KESTREL_LOGGER_NO_TIMEOUT_FAIL_OPEN", log)
        self.assertIn("KESTREL_LOGGER_NO_MONOTONIC_FAIL_OPEN", log)
        self.assertRegex(log, r'case\s+" \$_graphics_cmdline "\s+in\s+\*" kestrel_graphics=1 "\*')
        # Secure persist: exact names, O_NOFOLLOW, single-fd cap+1 read,
        # complete-JSON parse, minimal leaf-schema validation, atomic replace.
        for marker in ("O_NOFOLLOW", "O_NONBLOCK", "json.loads",
                       "parse_constant", "os.replace", "os.fsync", "08-graphics-preflight.json",
                       '"passed"', '"bounded_cleanup"', '"detail"', '"reason"'):
            self.assertIn(marker, log, "missing secure-persist marker: %s" % marker)
        self.assertIn('not isinstance(obj["detail"], dict)', log)
        self.assertIn("dneed = cap + 1", log)
        self.assertNotIn("handle.read() ==", log)
        # No bare global sync (per-file sync -f only, and only on change).
        for line in log.splitlines():
            self.assertNotRegex(line, r"^\s*sync\s*$",
                                "bare global sync causes churn: %r" % line)
        # No secret/environment dumps (bare paths/commands, not comments).
        for banned in ("printenv", "/proc/1/environ", "systemctl show",
                       "Environment=", "/etc/shadow", ".ssh/", "gpg "):
            self.assertNotIn(banned, log, "logger must not dump: %s" % banned)
        # Fail-open tail.
        self.assertIn("persist_whitelisted_file", log)
        self.assertIn("|| true", log)
        self.assertTrue(log.rstrip().endswith("exit 0"))
        CASES_RUN.append("logger_wall_budget_and_bounds_static")

    def test_logger_persist_last_good_unit(self):
        """Unit scope: extracted persist enforces names/caps/schema in bash."""
        log = LOGGER.read_text(encoding="utf-8")
        func = extract_function(log, "persist_whitelisted_file")
        with tempfile.TemporaryDirectory(prefix="dt26-persist-") as tmp:
            dest = Path(tmp) / "dest"
            srcd = Path(tmp) / "src"
            dest.mkdir()
            srcd.mkdir()
            gstatus = srcd / "status.json"
            gpreflight = srcd / "preflight.json"
            gstatus.write_text('{"reason": "refused", "bounded_cleanup": false}')
            gpreflight.write_text('{"passed": false, "detail": {"refused": true}}')

            def harness_for(src_path, leaf):
                return ("dest=%s\n" % dest.as_posix()
                        + "graphics_src_dir=%s\n" % srcd.as_posix()
                        + func + "\n"
                        + "persist_whitelisted_file %s %s 65536\n" % (src_path, leaf)
                        + "echo PERSIST_RC=$?; cat %s 2>/dev/null || echo NOLEAF\n" % (dest / leaf).as_posix())

            # Valid status + preflight (detail dict) payloads are accepted.
            proc = run_bash(harness_for(gstatus.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("PERSIST_RC=0", proc.stdout)
            self.assertIn('"bounded_cleanup": false', proc.stdout)
            proc = run_bash(harness_for(gpreflight.as_posix(), "08-graphics-preflight.json"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"passed": false', proc.stdout)
            # Partial JSON preserves prior valid output.
            pre = dest / "09-graphics-status.json"
            pre.write_text('{"reason": "last-good", "bounded_cleanup": true}')
            staged = srcd / "status.json"
            staged.write_text('{"reason":')
            proc2 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            self.assertIn("PERSIST_RC=0", proc2.stdout)
            self.assertIn('"last-good"', (dest / "09-graphics-status.json").read_text())
            # Symlink source preserves prior valid output, copies nothing.
            staged.unlink()
            outside = srcd / "outside-whitelist.txt"
            outside.write_text("FIXTURE_NOT_A_STATUS")
            staged.symlink_to(outside)
            proc3 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc3.returncode, 0, proc3.stderr)
            self.assertIn("PERSIST_RC=0", proc3.stdout)
            content = (dest / "09-graphics-status.json").read_text()
            self.assertIn('"last-good"', content)
            self.assertNotIn("FIXTURE_NOT_A_STATUS", content)
            # Wrong leaf/source pairing is rejected without blocking.
            proc4 = run_bash(harness_for(outside.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc4.returncode, 0, proc4.stderr)
            self.assertIn("PERSIST_RC=0", proc4.stdout)
            # Oversized source preserves prior valid output.
            if staged.exists() or staged.is_symlink():
                staged.unlink()
            staged.write_bytes(b'{"reason": "' + b"y" * 70000 + b'", "bounded_cleanup": true}')
            proc5 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc5.returncode, 0, proc5.stderr)
            self.assertIn("PERSIST_RC=0", proc5.stdout)
            self.assertIn('"last-good"', (dest / "09-graphics-status.json").read_text())
            # Absent source preserves prior valid output and still exits 0.
            if staged.exists() or staged.is_symlink():
                staged.unlink()
            proc6 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc6.returncode, 0, proc6.stderr)
            self.assertIn("PERSIST_RC=0", proc6.stdout)
            self.assertIn('"last-good"', (dest / "09-graphics-status.json").read_text())
            # FIFO and directory at the whitelisted name are rejected
            # without blocking; prior valid output preserved.
            import os as _os
            _os.mkfifo(staged.as_posix())
            proc7 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc7.returncode, 0, proc7.stderr)
            self.assertIn("PERSIST_RC=0", proc7.stdout)
            self.assertIn('"last-good"', (dest / "09-graphics-status.json").read_text())
            staged.unlink()
            staged.mkdir()
            proc8 = run_bash(harness_for(staged.as_posix(), "09-graphics-status.json"))
            self.assertEqual(proc8.returncode, 0, proc8.stderr)
            self.assertIn("PERSIST_RC=0", proc8.stdout)
            self.assertIn('"last-good"', (dest / "09-graphics-status.json").read_text())
        CASES_RUN.append("logger_persist_last_good_unit")

    def test_supervisor_stays_run_only(self):
        sup = SUPERVISOR.read_text(encoding="utf-8")
        self.assertIn("/run/kestrel-graphics", sup)
        for banned in ("bootmnt/Logs", "/run/archiso/bootmnt", "KESTREL-LOG-TARGET",
                       "remount", "mktemp", "journal+console"):
            self.assertNotIn(banned, sup, "supervisor must stay /run-only: %s" % banned)
        CASES_RUN.append("supervisor_run_only")

    def test_budget_and_lifecycle(self):
        log = LOGGER.read_text(encoding="utf-8")
        svc = SERVICE.read_text(encoding="utf-8")
        sup = SUPERVISOR.read_text(encoding="utf-8")
        self.assertIn("KESTREL_LOGGER_BUDGET_S:-260", log)
        self.assertIn("MAX_SECONDS = 180", sup)
        self.assertIn("CLEANUP_BUDGET_S = 25", sup)
        self.assertTrue(180 + 25 <= 260, "logger budget must cover session+cleanup")
        # Parent lifecycle preserved; only output directives added.
        self.assertIn("ExecStartPre=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed", svc)
        self.assertIn("ExecStopPost=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed", svc)
        self.assertIn("Restart=no", svc)
        self.assertIn("TimeoutStopSec=30", svc)
        self.assertIn("StandardOutput=journal+console", svc)
        self.assertIn("StandardError=journal+console", svc)
        self.assertNotIn("Restart=always", svc)
        self.assertNotIn("WantedBy=graphical", svc)
        CASES_RUN.append("budget_and_lifecycle")


def main(argv=None):
    # Preflight BEFORE any test or fixture effect: never truncate archives.
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
    suite = loader.loadTestsFromTestCase(Dt26Observability)
    with open(str(log_path), "w", encoding="utf-8") as stream:
        runner = unittest.TextTestRunner(stream=stream, verbosity=2)
        result = runner.run(suite)
        passed = result.testsRun - len(result.failures) - len(result.errors)
        # Reconcile: CASES_RUN includes setUpClass setup check plus 9 test methods.
        all_cases = sorted(set(CASES_RUN))
        testcases = sorted([c for c in all_cases if c != "setup_required_files_present"])
        checks = all_cases
        assert result.testsRun == len(testcases), \
            "tests_run %d != testcases %d (%s)" % (result.testsRun, len(testcases), testcases)
        assert len(checks) == result.testsRun + 1, \
            "checks %d != tests_run+setup %d" % (len(checks), result.testsRun + 1)
        payload = {
            "revision": "v2-dt26",
            "tests_run": result.testsRun,
            "testcases": testcases,
            "checks": checks,
            "cases": all_cases,
            "passed": passed,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped) if hasattr(result, "skipped") else 0,
            "owned_files": [str(p.relative_to(P)).replace("\\", "/") for p in REQUIRED],
            "native_hardware_validated": False,
            "vm_retest_required": True,
            "out_prefix_note": "extracted-function/static checks are unit scope only; full-file loop coverage is in test-dt26-observability-fix.py",
            "bounded_time": {
                "production_default_s": 260,
                "covers_session_s": 180,
                "covers_cleanup_s": 25,
                "mechanism": "BASH_MONOSECONDS else /proc/uptime fixed window + fresh remaining per op + timeout -k kill-after",
                "kill_after_s_default": 2,
                "honesty_note": "best-effort, NOT hard realtime: 1s clock resolution + ~2s KILL grace + ~1s scheduler; D-state/sync may exceed",
            },
            "runtime_closure": {
                "timeout_present_builder": bool(shutil.which("timeout")),
                "python3_present_builder": bool(shutil.which("python3")),
                "testonly": "unshare+mount are TESTONLY for private-mount/kmsg isolation, NOT production",
                "pack_need": "integrator must ensure timeout(coreutils)+python3 in the live image (frozen SFS carries both); no new installed helper is used, the secure persist is inline in kestrel-root-log.sh so no hook change is needed",
                "supervisor_stays_run_only": True,
            },
        }
        import json
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        stream.write("\nRESULT_JSON %s\n" % json_path)
    print(json.dumps(payload, indent=2))
    if payload["skipped"]:
        print("REFUSED: zero-skip policy violated", file=sys.stderr)
        return 2
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
