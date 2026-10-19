#!/usr/bin/env python3
"""dt26 parser regression tests (pure TDD, no QEMU/VM/image).

Uses ACTUAL retained old v2 serial bytes for the expected C RED case, plus
clearly SYNTHETIC fixtures (PIDs 5001/5002, boot-ids 11111111-... and
aaaaaaaa-...) for positives and negatives covering the NEW dt26 observer
schemas (08-graphics-preflight.json, 09-graphics-status.json,
10-graphics-journal.log) and the QA 09-unit-chaos.json contract. No VM boot,
no FAT, no lock, no secrets. Writes fresh dt26-efi-parser-test-result.json
only.
"""
import argparse
import ast
import importlib.util
import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

T = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure")
if not T.exists():
    T = Path("D:/CachyOS-ARM64/testing/boot-failure")
PARSER_PATH = T / "dt26-efi-parser.py"
HARNESS_PATH = T / "dt26-efi-harness.py"
PREPARE_PATH = T / "dt26-prepare-efi-fixture.py"
RESULT_PATH = T / "dt26-efi-parser-test-result.json"
OLD_V2_LOG = T / "dt25-efi-graphics-fw-off-v2.log"

PASS = 0
FAIL = 0
SKIP = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name + (f" :: {detail}" if detail else ""))
        print(f"FAIL {name} {detail}")


def load_parser():
    spec = importlib.util.spec_from_file_location(
        "dt26_efi_parser", str(PARSER_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_harness():
    spec = importlib.util.spec_from_file_location(
        "dt26_efi_harness", str(HARNESS_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SYN_BOOT = "11111111-2222-3333-4444-555555555555"
SYN_BOOT_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def synth_clean(pass_mode=True, missing_child_after=False,
                pid0_before=False, kill_fail=False,
                live_child=False, marker_left=False,
                echo_only=False):
    """Build clearly SYNTHETIC serial clean text (PIDs 5001/5002)."""
    if echo_only:
        # Command-echo contamination only: markers inside `echo ...;`
        # lines, never newline-delimited actual records.
        return (
            "KESTREL-TEXT# echo ===C-START-FAKE-PARENT===; "
            "systemctl start foo; echo C_PARENT_PID_BEFORE=5001; "
            "echo ===C-CHILD-AFTER===; echo MARKER_ABSENT_POST\n"
        )
    ppid = "0" if pid0_before else "5001"
    cpid = "0" if pid0_before else "5002"
    if pid0_before:
        p_active, p_sub = "inactive", "dead"
        c_active, c_sub = "inactive", "dead"
    else:
        p_active, p_sub = "active", "running"
        c_active, c_sub = "active", "running"
    kill_actual = ("C_KILL_RC=1\nKILL_CMD_FAIL\n"
                   if kill_fail else "C_KILL_RC=0\nKILL_SENT\n")
    if live_child or not pass_mode:
        after_c = "ActiveState=active\nSubState=running\nMainPID=5002\nResult=success"
    else:
        after_c = "ActiveState=inactive\nSubState=dead\nMainPID=0\nResult=success"
    marker_post = "" if marker_left else "\nMARKER_ABSENT_POST\n"
    parts = [
        "\n===C-START-FAKE-PARENT===\n",
        f"ActiveState={p_active}\nSubState={p_sub}\nMainPID={ppid}\nResult=success\n"
        f"C_PARENT_PID_BEFORE={ppid}\n",
        "\n===C-START-FAKE-CHILD===\n",
        f"ActiveState={c_active}\nSubState={c_sub}\nMainPID={cpid}\nResult=success\n"
        f"C_CHILD_PID_BEFORE={cpid}\n",
        "\n===C-KILL-PARENT-MAIN-SIGKILL===\n",
        kill_actual,
        "\n===C-PARENT-AFTER===\n",
        "ActiveState=failed\nSubState=failed\nMainPID=0\nResult=signal\n"
        "C_PARENT_PID_AFTER=0\n",
        "\n===C-CHILD-AFTER===\n" if not missing_child_after else "\n",
        ("C_CHILD_PID_AFTER=0\n" if (not live_child and not pid0_before)
         else "C_CHILD_PID_AFTER=5002\n")
        + after_c + "\n" + marker_post
        if not missing_child_after else "",
        "\n===C-CLEANUP-OWNED-FAKE-ONLY===\n",
        "\nSTALE_MARKER_CREATED\n",
        "\nPRE_CLEARED_MARKER\n",
        "\nFAKE_MARKER_CREATED\n",
        "\nKESTREL_C_DONE\n",
    ]
    return "".join(parts)


def synth_preflight(passed=False):
    return {
        "passed": passed, "reason": "preflight-fail",
        "detail": {"thermal": {"ok": False}, "drm": {"ok": False}},
        "thermal": {"ok": False, "errors": ["missing_sensor:cpu0-0-top-thermal"]},
        "drm": {"ok": False, "errors": ["no-drm-devices"]},
        "drm_snapshot": {"card": "card0", "connectors": []},
        "native_graphics_validated": False,
    }


def synth_status():
    return {
        "reason": "preflight-fail", "bounded_cleanup": True,
        "owned_unit": "kestrel-graphics-sddm.service", "owned_session": None,
        "owned_stopped": True, "owned_gone": True, "tty2_restored": True,
        "steps": [{"cmd": ["systemctl", "stop", "kestrel-graphics-sddm.service"],
                   "ok": True}],
        "restart_text": "getty@tty2.service",
        "native_graphics_validated": False,
        "session_active_is_not_pixel_proof": True,
    }


def synth_journal():
    return (
        "Oct 18 12:00:00 live kestrel-graphics-supervisor[1]: "
        "KESTREL_GRAPHICS_PREFLIGHT_FAIL\n"
        "Oct 18 12:00:05 live kestrel-graphics-supervisor[1]: "
        "KESTREL_GRAPHICS_CLEANUP_DONE_preflight-fail\n"
    )


def synth_09(valid=True, malformed=False, wrong_bid=False,
             marker_left=False, live_child=False, string_pids=False,
             zero_pid=False):
    if malformed:
        return "not-a-dict"
    ppid = "5001" if string_pids else 5001
    cpid = "5002" if string_pids else 5002
    if zero_pid:
        ppid, cpid = 0, 0
    d = {
        "record": "09-unit-chaos", "boot_id": SYN_BOOT,
        "stale_marker_created": True,
        "parent_execstart_verified_sleep": True,
        "parent_active_before": True, "parent_pid_before": ppid,
        "execstartpre_cleared_marker": True,
        "fake_marker_created": True,
        "child_active_before": True, "child_pid_before": cpid,
        "kill_rc": 0, "kill_sent": True,
        "parent_after": {"ActiveState": "failed", "SubState": "failed",
                         "MainPID": 0, "Result": "signal"},
        "child_after_auto": {"ActiveState": "inactive", "SubState": "dead",
                             "MainPID": 0, "Result": "success"}
        if not live_child else {"ActiveState": "active",
                                "SubState": "running", "MainPID": 5002,
                                "Result": "success"},
        "old_child_pid_gone": True if not live_child else False,
        "marker_absent_post": False if marker_left else True,
        "cleanup_owned_fake_only": True, "measured_within_s": 15,
    }
    if wrong_bid:
        d["boot_id"] = SYN_BOOT_A
    if not valid:
        d.pop("kill_rc")
    return d


def synth_audit(valid=True, bad_hex=False, bad_rev=False,
                bad_path=False, truncated=False):
    h = "ab" * 32
    if bad_hex:
        h = "ZZ" * 32
    if truncated:
        h = "ab" * 31 + "a"  # 63 chars
    d = {
        "passed": True, "revision": "v2-dt26" if not bad_rev else "v2-dt25b",
        "uki_sha256": h, "initramfs_sha256": "cd" * 32,
        "sfs_sha256": "ef" * 32, "uki_bytes": 100, "sfs_bytes": 200,
        "uki_path": "/home/builder/uki-v2-dt26/vmlinuz-live.efi"
        if not bad_path else "/tmp/evil.efi",
        "initramfs_path": "/home/builder/uki-v2-dt26/live-initramfs.img",
        "qemu_firmware": {"sha256": "12" * 32, "bytes": 10,
                          "path": "/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"},
        "guard_policy": {"passed": True, "required_sensor_count": 20},
        "initramfs_validation": {"passed": True},
    }
    if not valid:
        d["passed"] = False
    return d


def undefined_names(path):
    """Stdlib-only undefined-name scan (no installs)."""
    tree = ast.parse(Path(path).read_text())
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                defined.add(a.asname or a.name)
        elif isinstance(node, ast.FunctionDef):
            defined.add(node.name)
            for a in node.args.args:
                defined.add(a.arg)
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for n in ast.walk(node.target):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    defined.add(n.id)
        elif isinstance(node, ast.ExceptHandler):
            if node.name:
                defined.add(node.name)
    import builtins
    builtin_set = set(dir(builtins)) | {
        "re", "json", "pathlib", "sys", "time", "os", "select",
        "subprocess", "hashlib", "fcntl", "shutil", "argparse", "Path",
    }
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in defined and node.id not in builtin_set \
                    and not node.id.startswith("_"):
                bad.append((node.lineno, node.id))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default=str(RESULT_PATH),
                    help="fresh caller-owned JSON output (exclusive)")
    ap.add_argument("--tag", default=None,
                    help="fresh tag; result=T/<tag>-parser-test-result.json")
    ap.add_argument("--run-dir", default=None,
                    help="fresh caller-owned dir holding the result JSON")
    args = ap.parse_args(argv)
    if args.tag:
        result_path = T / (args.tag + "-parser-test-result.json")
    elif args.run_dir:
        result_path = Path(args.run_dir) / RESULT_PATH.name
    else:
        result_path = Path(args.result)
    # Collision preflight FIRST: validate + reserve before ANY test, import,
    # compile, or temp-fixture side effects. Never unlink/overwrite.
    # Atomic exclusive reservation BEFORE any import/compile/fixture effects.
    # Concurrent winner refuses here without loading tests; old hash preserved
    # (O_EXCL, never truncate). Own in-progress descriptor finalized below.
    if args.run_dir:
        try:
            Path(args.run_dir).mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            pass
        except FileNotFoundError:
            raise AssertionError(
                f"missing parent for result {result_path.parent}")
    assert result_path.parent.exists(), \
        f"missing parent for result {result_path.parent}"
    import os as _os
    try:
        _res_fd = _os.open(str(result_path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
    except FileExistsError:
        raise AssertionError(
            f"collision: {result_path} exists, use fresh --result/--tag/--run-dir")
    # Reserved; now run all checks under a finalizer that writes accurate
    # failure status into OUR descriptor if anything raises (never touches
    # an archived file: _res_fd is our fresh O_EXCL descriptor).
    try:
        mod = load_parser()
        # 1. Compile-only (no NameErrors by py_compile).
        for p, label in [(str(PARSER_PATH), "parser"),
                         (str(HARNESS_PATH), "harness"),
                         (str(PREPARE_PATH), "prepare"),
                         (str(Path(__file__)), "test")]:
            try:
                py_compile.compile(p, doraise=True)
                check(f"compile-{label}", True)
            except Exception as e:
                check(f"compile-{label}", False, str(e)[:200])
        # 2. Undefined-name scan on new files (available checker, no install).
        for p, label in [(str(PARSER_PATH), "parser"),
                         (str(HARNESS_PATH), "harness"),
                         (str(PREPARE_PATH), "prepare")]:
            bad = undefined_names(p)
            critical = [b for b in bad if b[1] in (
                "child_block", "parent_block", "undefined_helper")]
            check(f"undefined-scan-{label}-no-critical", len(critical) == 0,
                  str(critical[:5]))
        # 3. Actual retained old v2 bytes => expected C RED.
        try:
            raw = OLD_V2_LOG.read_bytes().decode(errors="replace")
            clean = mod.strip_ansi(raw)
            check("v2-log-loads", len(clean) > 10000, str(len(clean)))
            passed, checks, detail = mod.evaluate_c_serial(clean)
            check("v2-actual-is-RED-not-pass",
                  passed is False, f"detail={detail}")
            check("v2-RED-detail-child-stays-active",
                  detail == "RED-child-stays-active", detail)
            check("v2-parent-before-active",
                  checks.get("c_fake_parent_active_before") is True)
            check("v2-child-before-active",
                  checks.get("c_fake_child_active_before") is True)
            check("v2-kill-rc0-sent", checks.get("c_kill_sent") is True)
            check("v2-parent-failed-pid0-signal",
                  checks.get("c_parent_failed_after_sigkill") is True)
            check("v2-child-after-false-conjunctive",
                  checks.get("c_child_inactive_gone_after_parent_sigkill") is False)
            # Actual PIDs from retained old capture (1147/1169).
            check("v2-actual-pids-1147-1169",
                  "1147" in clean and "1169" in clean)
            # Command-echo markers must not count as actual without newlines.
            echo_frag = ("KESTREL-TEXT# echo ===C-START-FAKE-PARENT===; "
                         "systemctl start x")
            check("v2-echo-marker-not-actual",
                  mod.actual_block(echo_frag, "===C-START-FAKE-PARENT===",
                                   "===C-START-FAKE-CHILD===") is None)
            check("v2-anchored-false-for-echo-only",
                  mod.is_anchored_marker(echo_frag, "===C-START-FAKE-PARENT===") is False)
        except Exception as e:
            check("v2-actual-RED-suite", False, f"{type(e).__name__}: {e}"[:300])
        # 4. Synthetic PASS (clearly synthetic PIDs/boot-id).
        try:
            c = synth_clean(pass_mode=True)
            passed, checks, detail = mod.evaluate_c_serial(c)
            check("synthetic-pass", passed is True, detail)
            check("synthetic-pass-detail",
                  detail == "child-inactive-gone-marker-absent", detail)
            check("synthetic-anchored-true-for-executed",
                  mod.is_anchored_marker(c, "KILL_SENT") is True)
        except Exception as e:
            check("synthetic-pass", False, str(e)[:200])
        # 5. Negatives: each must FAIL (not vacuous pass).
        for name, kwargs in [
            ("missing-blocks", {"missing_child_after": True}),
            ("pid0-before", {"pid0_before": True}),
            ("failed-kill", {"kill_fail": True}),
            ("live-child-after", {"live_child": True}),
            ("stale-marker-left", {"marker_left": True}),
            ("command-echo-only", {"echo_only": True}),
        ]:
            try:
                c = synth_clean(pass_mode=False, **kwargs)
                passed, _, detail = mod.evaluate_c_serial(c)
                check(f"negative-{name}-fails-closed", passed is False, detail)
            except Exception as e:
                check(f"negative-{name}-fails-closed", False, str(e)[:200])
        # 6. NEW production observer schemas (synthetic, clearly labeled).
        # Stable contract: passed bool + reason + detail dict; top-level
        # thermal/drm duplicates NOT required.
        try:
            ok, errs, _ = mod.validate_preflight_record(synth_preflight())
            check("preflight-synthetic-refusal-valid", ok is True, str(errs[:3]))
            ok, _, _ = mod.validate_preflight_record(synth_preflight(passed=True))
            check("preflight-success-schema-valid", ok is True)
            ok, _, _ = mod.validate_preflight_record("not-a-dict")
            check("preflight-malformed-fails", ok is False)
            d = synth_preflight()
            d.pop("detail")
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-missing-field-fails", ok is False)
            d = synth_preflight()
            d["passed"] = "false"
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-passed-not-bool-fails", ok is False)
            d = synth_preflight()
            d["native_graphics_validated"] = True
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-native-true-fails", ok is False)
            d = synth_preflight()
            d["detail"] = "preflight-fail"
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-detail-not-dict-fails", ok is False)
            # Top-level duplicates are legacy: absence must still validate.
            d = {"passed": False, "reason": "preflight-fail",
                 "detail": {"thermal": {"ok": False}, "drm": {"ok": False}},
                 "native_graphics_validated": False}
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-no-top-duplicates-valid", ok is True)
            # Early unknown-baseline: reason + empty detail, no hardware yet.
            d = {"passed": False, "reason": "unknown-baseline",
                 "detail": {}, "native_graphics_validated": False}
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-early-unknown-baseline-valid", ok is True)
            d = {"passed": False, "reason": "preflight-fail",
                 "detail": {"thermal": "bad"}, "native_graphics_validated": False}
            ok, _, _ = mod.validate_preflight_record(d)
            check("preflight-detail-thermal-not-dict-fails", ok is False)
        except Exception as e:
            check("preflight-suite", False, str(e)[:200])
        try:
            ok, errs, _ = mod.validate_status_record(synth_status())
            check("status-synthetic-valid", ok is True, str(errs[:3]))
            ok, _, _ = mod.validate_status_record("not-a-dict")
            check("status-malformed-fails", ok is False)
            d = synth_status()
            d.pop("steps")
            ok, _, _ = mod.validate_status_record(d)
            check("status-missing-field-fails", ok is False)
            d = synth_status()
            d["owned_unit"] = "display-manager.service"
            ok, _, _ = mod.validate_status_record(d)
            check("status-stock-unit-fails", ok is False)
            d = synth_status()
            d["native_graphics_validated"] = True
            ok, _, _ = mod.validate_status_record(d)
            check("status-native-true-fails", ok is False)
            d = synth_status()
            d["session_active_is_not_pixel_proof"] = False
            ok, _, _ = mod.validate_status_record(d)
            check("status-pixel-proof-false-fails", ok is False)
            d = synth_status()
            d["bounded_cleanup"] = "yes"
            ok, _, _ = mod.validate_status_record(d)
            check("status-bounded-not-bool-fails", ok is False)
        except Exception as e:
            check("status-suite", False, str(e)[:200])
        try:
            ok, errs, _ = mod.validate_journal_text(synth_journal())
            check("journal-synthetic-valid", ok is True, str(errs[:3]))
            ok, _, _ = mod.validate_journal_text("")
            check("journal-empty-fails", ok is False)
            ok, _, _ = mod.validate_journal_text("KESTREL_GRAPHICS_CLEANUP_DONE_x\n")
            check("journal-missing-preflight-fails", ok is False)
            ok, _, _ = mod.validate_journal_text("KESTREL_GRAPHICS_PREFLIGHT_FAIL\n")
            check("journal-missing-cleanup-fails", ok is False)
            ok, _, _ = mod.validate_journal_text("x" * (131072 + 5000))
            check("journal-oversized-fails", ok is False)
        except Exception as e:
            check("journal-suite", False, str(e)[:200])
        # 7. QA 09-unit-chaos validation (distinct from production 09-status).
        # Reader never repairs JSON types: type(x) is int required.
        try:
            ok, errs, _ = mod.validate_09_record(synth_09(), SYN_BOOT)
            check("09-synthetic-valid", ok is True, str(errs[:3]))
            ok, errs, _ = mod.validate_09_record(synth_09(string_pids=True), SYN_BOOT)
            check("09-string-pids-rejected-no-repair", ok is False, str(errs[:3]))
            d = synth_09(string_pids=True)
            d["parent_pid_before"] = True
            ok, _, _ = mod.validate_09_record(d, SYN_BOOT)
            check("09-bool-pid-rejected", ok is False)
            d = synth_09()
            d["parent_after"] = {"ActiveState": "failed", "SubState": "failed",
                                 "MainPID": "0", "Result": "signal"}
            ok, _, _ = mod.validate_09_record(d, SYN_BOOT)
            check("09-string-mainpid-rejected", ok is False)
            d = synth_09()
            d["kill_rc"] = "0"
            ok, _, _ = mod.validate_09_record(d, SYN_BOOT)
            check("09-string-kill_rc-rejected", ok is False)
            ok, _, _ = mod.validate_09_record(synth_09(marker_left=True), SYN_BOOT)
            check("09-marker-left-fails-new-rule", ok is False)
            ok, _, _ = mod.validate_09_record(synth_09(live_child=True), SYN_BOOT)
            check("09-live-child-fails", ok is False)
            ok, _, _ = mod.validate_09_record(synth_09(malformed=True), SYN_BOOT)
            check("09-malformed-fails", ok is False)
            ok, _, _ = mod.validate_09_record(synth_09(wrong_bid=True), SYN_BOOT)
            check("09-wrong-bootid-fails", ok is False)
            ok, _, _ = mod.validate_09_record(synth_09(zero_pid=True), SYN_BOOT)
            check("09-zero-pid-fails-nonvacuous", ok is False)
            d = synth_09()
            d.pop("kill_rc")
            ok, _, _ = mod.validate_09_record(d, SYN_BOOT)
            check("09-missing-field-fails", ok is False)
        except Exception as e:
            check("09-suite", False, str(e)[:200])
        # 8. Audit validation (never repair tokens) + explicit SFS gate.
        try:
            ok, errs, drv = mod.validate_audit_dict(synth_audit())
            check("audit-synthetic-valid", ok is True, str(errs[:3]))
            check("audit-derived-hashes",
                  drv.get("uki_sha256") == "ab" * 32)
            for nm, kw in [("audit-bad-hex", {"bad_hex": True}),
                           ("audit-bad-rev", {"bad_rev": True}),
                           ("audit-bad-path", {"bad_path": True}),
                           ("audit-truncated-63", {"truncated": True}),
                           ("audit-passed-false", {})]:
                d = synth_audit(**kw) if nm != "audit-passed-false" \
                    else synth_audit(valid=False)
                ok, _, _ = mod.validate_audit_dict(d)
                check(f"{nm}-fails-closed", ok is False)
            d = synth_audit()
            d["uki_sha256"] = "AB" * 32
            ok, _, _ = mod.validate_audit_dict(d)
            check("audit-uppercase-fails", ok is False)
            d = synth_audit()
            d["revision"] = "v2-dt25b"
            ok, _, _ = mod.validate_audit_dict(d)
            check("audit-old-revision-fails", ok is False)
            ok, _ = mod.validate_explicit_sfs("ab" * 32, 200)
            check("explicit-sfs-valid", ok is True)
            ok, _ = mod.validate_explicit_sfs("ZZ" * 32, 200)
            check("explicit-sfs-bad-hex-fails", ok is False)
            ok, _ = mod.validate_explicit_sfs("ab" * 32, 0)
            check("explicit-sfs-zero-bytes-fails", ok is False)
        except Exception as e:
            check("audit-suite", False, str(e)[:200])
        # 9. Guest-send contract on the REAL harness sends (joined shell +
        # embedded Python syntax, not templates).
        try:
            h = load_harness()
            for label, send in [("a", h.A_GUEST_CMD),
                                ("phase1", h.BC_PHASE1_SEND),
                                ("journal-seen", h.BC_JOURNAL_SEEN_SEND),
                                ("b-collect", h.B_COLLECT_SEND),
                                ("c-chaos", h.C_CHAOS_SEND)]:
                ok, errs = mod.validate_guest_send(send)
                check(f"guest-{label}-send-valid", ok is True, str(errs[:2]))
            check("guest-collect-has-no-try-splice",
                  ";try:" not in h.B_COLLECT_SEND + h.C_CHAOS_SEND)
            ok, errs = mod.validate_guest_send("echo hi")
            check("guest-missing-newline-fails", ok is False)
            ok, errs = mod.validate_guest_send("echo x;try: y\n")
            check("guest-try-splice-fails", ok is False)
        except Exception as e:
            check("guest-send-suite", False, f"{type(e).__name__}: {e}"[:300])
        # 10. Shared-FAT boot selection: per-boot leaves, A/B must differ.
        try:
            with tempfile.TemporaryDirectory(prefix="dt26-bootsel-") as tmp:
                base = Path(tmp)
                for bid, leaf, body in [(SYN_BOOT_A, "07-typed-command.txt", "A-TYPED"),
                                        (SYN_BOOT, "08-graphics-preflight.json", "{}"),
                                        (SYN_BOOT, "09-graphics-status.json", "{}"),
                                        (SYN_BOOT, "10-graphics-journal.log", "J"),
                                        (SYN_BOOT, "09-unit-chaos.json", "{}")]:
                    d = base / ("boot-" + bid)
                    d.mkdir(exist_ok=True)
                    (d / leaf).write_text(body)
                ids = mod.list_boot_ids(str(base))
                check("bootsel-lists-both-ids",
                      ids == sorted([SYN_BOOT, SYN_BOOT_A]), str(ids))
                p = mod.leaf_in_boot(str(base), SYN_BOOT, "09-unit-chaos.json")
                check("bootsel-resolves-c-under-b-boot",
                      p is not None and p.read_text() == "{}")
                p = mod.leaf_in_boot(str(base), SYN_BOOT_A, "09-unit-chaos.json")
                check("bootsel-no-cross-boot-leak", p is None)
                p = mod.leaf_in_boot(str(base), "not-a-uuid", "09-unit-chaos.json")
                check("bootsel-malformed-bid-refuses", p is None)
                ok, _ = mod.validate_boot_pair(SYN_BOOT_A, SYN_BOOT)
                check("bootsel-distinct-pair-ok", ok is True)
                ok, _ = mod.validate_boot_pair(SYN_BOOT, SYN_BOOT)
                check("bootsel-same-id-refuses-collision", ok is False)
                ok, _ = mod.validate_boot_pair("bad", SYN_BOOT)
                check("bootsel-malformed-a-refuses", ok is False)
        except Exception as e:
            check("bootsel-suite", False, f"{type(e).__name__}: {e}"[:300])
        # 11. Hex/boot-id primitives (fullmatch: trailing LF never accepted).
        check("hex64-valid", mod.validate_hex64("ab" * 32) is True)
        check("hex64-truncated-fails",
              mod.validate_hex64("ab" * 31 + "a") is False)
        check("hex64-newline-fails",
              mod.validate_hex64("ab" * 32 + "\n") is False)
        check("hex64-uppercase-fails",
              mod.validate_hex64("AB" * 32) is False)
        check("bootid-valid", mod.validate_boot_id(SYN_BOOT) is True)
        check("bootid-malformed-fails",
              mod.validate_boot_id("not-a-uuid") is False)
        check("bootid-newline-fails",
              mod.validate_boot_id(SYN_BOOT + "\n") is False)
        # Forged echo-block: substring START/END without standalone lines fails.
        check("actual-forged-block-rejected",
              mod.actual_block("echo START\nforged\nEND\n", "START", "END") is None)
        check("actual-standalone-lines-accepted",
              (mod.actual_block("\nSTART\nforged\nEND\n", "START", "END") or "").strip() == "forged")
        check("revision-is-v2-dt26", mod.REVISION == "v2-dt26")
        check("helper-revision-is-v2-dt26", mod.HELPER_REVISION == "v2-dt26")

        total = PASS + FAIL
        summary = {"passed": PASS, "failed": FAIL, "skipped": SKIP,
                   "total": total, "failures": FAILURES,
                   "revision": "v2-dt26",
                   "no_vm_runs": True,
                   "notes": "actual retained v2 bytes expect RED; positives are synthetic fixtures only"}
        # Fresh exclusive output only: never unlink or overwrite an archived result.
        # _res_fd is our O_EXCL descriptor (already reserved); finalize it.
        with _os.fdopen(_res_fd, "w") as stream:
            stream.write(json.dumps(summary, indent=2))
        _res_fd = None
        print(json.dumps(summary, indent=2))
        sys.exit(0 if FAIL == 0 else 1)
    except SystemExit:
        raise
    except BaseException as _exc:
        try:
            try:
                _os.close(_res_fd)
            except Exception:
                pass
        except Exception:
            pass
        try:
            if result_path.is_file() and result_path.stat().st_size == 0:
                failure = {"passed": PASS, "failed": FAIL + 1, "skipped": SKIP,
                           "total": PASS + FAIL + 1, "failures": FAILURES + [f"exception: {type(_exc).__name__}: {_exc}"[:500]],
                           "revision": "v2-dt26", "no_vm_runs": True,
                           "notes": "exception during parser tests (own descriptor finalized)"}
                result_path.write_text(json.dumps(failure, indent=2))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
