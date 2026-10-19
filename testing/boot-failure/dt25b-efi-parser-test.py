#!/usr/bin/env python3
"""dt25b parser regression tests (pure TDD, no QEMU/VM/image).

Uses ACTUAL old v2 captured bytes for the expected C RED case, plus
clearly SYNTHETIC fixtures (PIDs 5001/5002, boot-id 11111111-...) for
positives and negatives. No VM boot, no FAT, no lock, no secrets.
Writes fresh dt25b-efi-parser-test-result.json only.
"""
import ast
import importlib.util
import json
import py_compile
import re
import sys
from pathlib import Path

T = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure")
if not T.exists():
    T = Path("D:/CachyOS-ARM64/testing/boot-failure")
PARSER_PATH = T / "dt25b-efi-parser.py"
HARNESS_PATH = T / "dt25b-efi-harness.py"
RESULT_PATH = T / "dt25b-efi-parser-test-result.json"
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
        "dt25b_efi_parser", str(PARSER_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SYN_BOOT = "11111111-2222-3333-4444-555555555555"
SYN_BOOT2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


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


def synth_08(valid=True, malformed=False, wrong_bid=False):
    if malformed:
        return {"record": "08-graphics-test", "boot_id": "not-a-uuid"}
    d = {
        "record": "08-graphics-test", "boot_id": SYN_BOOT,
        "kcmdline": "BOOT_IMAGE=/EFI/Linux/kestrel-live.efi kestrel_graphics=1 "
                    "systemd.unit=multi-user.target console=ttyAMA0,115200",
        "qemu": True, "virt": "qemu", "overlay_root": True,
        "fstype": "overlay", "multi_user_active": True,
        "python_exec_ok": True, "python_import_ok": True,
        "guard_ok": False, "guard_errors": ["missing_sensor:cpu0-0-btm-thermal"],
        "journal_preflight_fail": True, "journal_cleanup_done": True,
        "unit_graphics": {"LoadState": "loaded", "ActiveState": "failed"},
        "unit_sddm_private": {"LoadState": "loaded", "ActiveState": "inactive",
                              "MainPID": "0"},
        "marker_absent": True, "sddm_proc_absent": True,
        "stock_masked": True, "execstartpre_exact": True,
        "execstoppost_exact": True,
    }
    if wrong_bid:
        d["boot_id"] = SYN_BOOT2
    if not valid:
        d.pop("guard_errors")
    return d


def synth_09(valid=True, malformed=False, wrong_bid=False,
             marker_left=False, live_child=False):
    if malformed:
        return "not-a-dict"
    d = {
        "record": "09-unit-chaos", "boot_id": SYN_BOOT,
        "stale_marker_created": True,
        "parent_execstart_verified_sleep": True,
        "parent_active_before": True, "parent_pid_before": 5001,
        "execstartpre_cleared_marker": True,
        "fake_marker_created": True,
        "child_active_before": True, "child_pid_before": 5002,
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
        d["boot_id"] = SYN_BOOT2
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
        "passed": True, "revision": "v2-dt25b" if not bad_rev else "v2-dt25",
        "uki_sha256": h, "initramfs_sha256": "cd" * 32,
        "sfs_sha256": "ef" * 32, "uki_bytes": 100, "sfs_bytes": 200,
        "uki_path": "/home/builder/uki-v2-dt25b/vmlinuz-live.efi"
        if not bad_path else "/tmp/evil.efi",
        "initramfs_path": "/home/builder/uki-v2-dt25b/live-initramfs.img",
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


def main():
    mod = load_parser()
    # 1. Compile-only (no NameErrors by py_compile).
    for p, label in [(str(PARSER_PATH), "parser"),
                     (str(HARNESS_PATH), "harness"),
                     (str(Path(__file__)), "test")]:
        try:
            py_compile.compile(p, doraise=True)
            check(f"compile-{label}", True)
        except Exception as e:
            check(f"compile-{label}", False, str(e)[:200])
    # 2. Undefined-name scan on new files (available checker, no install).
    for p, label in [(str(PARSER_PATH), "parser"),
                     (str(HARNESS_PATH), "harness")]:
        bad = undefined_names(p)
        critical = [b for b in bad if b[1] in (
            "child_block", "parent_block", "undefined_helper")]
        check(f"undefined-scan-{label}-no-critical", len(critical) == 0,
              str(critical[:5]))
    # 3. Actual old v2 bytes => expected C RED.
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
        # Actual PIDs from old capture (1147/1169) present.
        check("v2-actual-pids-1147-1169",
              "1147" in clean and "1169" in clean)
        # Command-echo markers must not count as actual without newlines.
        echo_frag = ("KESTREL-TEXT# echo ===C-START-FAKE-PARENT===; "
                     "systemctl start x")
        check("v2-echo-marker-not-actual",
              mod.actual_block(echo_frag, "===C-START-FAKE-PARENT===",
                               "===C-START-FAKE-CHILD===") is None)
    except Exception as e:
        check("v2-actual-RED-suite", False, f"{type(e).__name__}: {e}"[:300])
    # 4. Synthetic PASS (clearly synthetic PIDs/boot-id).
    try:
        c = synth_clean(pass_mode=True)
        passed, checks, detail = mod.evaluate_c_serial(c)
        check("synthetic-pass", passed is True, detail)
        check("synthetic-pass-detail",
              detail == "child-inactive-gone-marker-absent", detail)
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
    # 6. JSON 08/09 validation.
    try:
        ok, errs, _ = mod.validate_08_record(synth_08(), SYN_BOOT)
        check("08-synthetic-valid", ok is True, str(errs[:3]))
        ok, _, _ = mod.validate_08_record(synth_08(malformed=True), SYN_BOOT)
        check("08-malformed-fails", ok is False)
        ok, _, _ = mod.validate_08_record(
            synth_08(wrong_bid=True), SYN_BOOT)
        check("08-wrong-bootid-fails", ok is False)
        ok, _, _ = mod.validate_08_record(synth_08(valid=False), SYN_BOOT)
        check("08-missing-field-fails", ok is False)
    except Exception as e:
        check("08-suite", False, str(e)[:200])
    try:
        ok, errs, _ = mod.validate_09_record(synth_09(), SYN_BOOT)
        check("09-synthetic-valid", ok is True, str(errs[:3]))
        ok, _, _ = mod.validate_09_record(synth_09(marker_left=True), SYN_BOOT)
        check("09-marker-left-fails-new-rule", ok is False)
        ok, _, _ = mod.validate_09_record(synth_09(live_child=True), SYN_BOOT)
        check("09-live-child-fails", ok is False)
        ok, _, _ = mod.validate_09_record(
            synth_09(malformed=True), SYN_BOOT)
        check("09-malformed-fails", ok is False)
        ok, _, _ = mod.validate_09_record(
            synth_09(wrong_bid=True), SYN_BOOT)
        check("09-wrong-bootid-fails", ok is False)
    except Exception as e:
        check("09-suite", False, str(e)[:200])
    # 7. Audit validation (never repair tokens).
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
        # Uppercase hex must fail (EXACTLY lower).
        d = synth_audit()
        d["uki_sha256"] = "AB" * 32
        ok, _, _ = mod.validate_audit_dict(d)
        check("audit-uppercase-fails", ok is False)
    except Exception as e:
        check("audit-suite", False, str(e)[:200])
    # 8. Hex/boot-id primitives.
    check("hex64-valid", mod.validate_hex64("ab" * 32) is True)
    check("hex64-truncated-fails",
          mod.validate_hex64("ab" * 31 + "a") is False)
    check("bootid-valid", mod.validate_boot_id(SYN_BOOT) is True)
    check("bootid-malformed-fails",
          mod.validate_boot_id("not-a-uuid") is False)

    total = PASS + FAIL
    summary = {"passed": PASS, "failed": FAIL, "skipped": SKIP,
               "total": total, "failures": FAILURES,
               "revision": "v2-dt25b",
               "no_vm_runs": True,
               "notes": "actual v2 bytes expect RED; positives are synthetic fixtures only"}
    # Fresh exclusive output only: never unlink or overwrite an archived result.
    with RESULT_PATH.open("x") as stream:
        stream.write(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
