#!/usr/bin/env python3
"""dt25b EFI parser/oracle helpers (revision-aware, import-safe).

Owns ONLY dt25b-efi-* parsing. No top-level side effects: importing this
module never touches FAT/QEMU/lock/logs. All functions are pure except
explicit file reads passed by callers.

Oracle preference (enforced by harness, implemented here as validators):
  1. Guest-generated structured JSON saved atomically to validated VM USB:
     /run/archiso/bootmnt/Logs/boot-<boot-id>/08-graphics-test.json
     /run/archiso/bootmnt/Logs/boot-<boot-id>/09-unit-chaos.json
  2. Serial fallback only with anchored records + strict JSON type/field
     validation; missing record is FAIL, never vacuous pass.
Command-echo contamination rule: a marker counts as ACTUAL only when it is
newline-delimited (\\r?\\nMARKER\\r?\\n). Occurrences inside typed-command
echoes (``echo MARKER; ...``) are ignored.
"""
import json
import re

REVISION = "v2-dt25b"

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
BOOTID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
PROMPT_RE = re.compile(r"(?:^|[\r\n])KESTREL-TEXT# ")
MULTI_RE = re.compile(r"Reached target [^\r\n]*Multi-User System")

# Exact fixed unit-contract strings for deleg_03f10f91.
PARENT_PRE = "/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed"
PARENT_POST = "/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed"
FAKE_EXEC = "/usr/bin/sleep 600"

REQUIRED_08_FIELDS = [
    "record", "boot_id", "kcmdline", "qemu", "overlay_root",
    "multi_user_active", "python_exec_ok", "python_import_ok",
    "guard_ok", "guard_errors", "journal_preflight_fail",
    "journal_cleanup_done", "unit_graphics", "unit_sddm_private",
    "marker_absent", "sddm_proc_absent", "stock_masked",
    "execstartpre_exact", "execstoppost_exact",
]
REQUIRED_09_FIELDS = [
    "record", "boot_id", "stale_marker_created",
    "parent_execstart_verified_sleep", "parent_active_before",
    "parent_pid_before", "execstartpre_cleared_marker",
    "fake_marker_created", "child_active_before", "child_pid_before",
    "kill_rc", "kill_sent", "parent_after", "child_after_auto",
    "old_child_pid_gone", "marker_absent_post",
    "cleanup_owned_fake_only", "measured_within_s",
]


def strip_ansi(data):
    """Strip ANSI CSI sequences. Accepts bytes or str, returns str."""
    if isinstance(data, (bytes, bytearray)):
        text = bytes(data).decode(errors="replace")
    else:
        text = data
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)


def actual_block(clean, start_marker, end_marker=None):
    """Return phase-scoped ACTUAL block between newline-delimited markers.

    Only ``\\nMARKER\\n`` (\\r tolerated) counts. Command echoes such as
    ``echo ===MARKER===; ...`` do not match because they lack the leading
    newline + trailing newline shape. Returns None when either marker is
    missing (fail-closed). When several actual occurrences exist, the LAST
    start is used (post-boot actual, not pre-boot echo duplication).
    """
    if not clean or not start_marker:
        return None
    pat_start = re.compile(re.escape(start_marker) + r"\r?\n")
    starts = list(pat_start.finditer(clean))
    if not starts:
        return None
    s = starts[-1].end()
    if end_marker is None:
        return clean[s:s + 8000]
    m_end = re.search(re.escape(end_marker), clean[s:s + 8000])
    if not m_end:
        return None
    return clean[s:s + m_end.start()]


def parse_show(block):
    """Parse ``systemctl show`` style KEY=VALUE lines into a dict."""
    out = {}
    if not block:
        return out
    for line in block.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k and k not in out:
            out[k] = v.strip()
    return out


def validate_hex64(s):
    return isinstance(s, str) and bool(HEX64_RE.match(s))


def validate_boot_id(s):
    return isinstance(s, str) and bool(BOOTID_RE.match(s))


def validate_audit_dict(d):
    """Validate a dt25b artifact audit dict. Returns (ok, errors, derived).

    Never repairs tokens: invalid format is reported, never replaced with a
    default hash. Requires revision v2-dt25b, passed true, 64-lower-hex
    hashes EXACTLY, positive byte counts, and private-build-root paths.
    """
    errors = []
    derived = {}
    if not isinstance(d, dict):
        return False, ["audit-not-a-dict"], {}
    if d.get("passed") is not True:
        errors.append("audit-passed-must-be-true")
    if d.get("revision") != "v2-dt25b":
        errors.append("audit-revision-must-be-v2-dt25b")
    for key in ("uki_sha256", "initramfs_sha256", "sfs_sha256"):
        v = d.get(key)
        if not validate_hex64(v):
            errors.append(f"audit-{key}-must-be-64-lower-hex")
        else:
            derived[key] = v
    for key in ("uki_bytes", "sfs_bytes"):
        v = d.get(key)
        if not isinstance(v, int) or v <= 0:
            errors.append(f"audit-{key}-must-be-positive-int")
        else:
            derived[key] = v
    for key in ("uki_path", "initramfs_path"):
        v = d.get(key)
        if not isinstance(v, str) or not v.startswith("/home/builder/"):
            errors.append(f"audit-{key}-must-be-in-private-build-root")
        elif "uki-v2-dt25b" not in v and "live" not in v.lower():
            # Enforce dt25b lineage without hardcoding a hash.
            if "dt25b" not in v:
                errors.append(f"audit-{key}-must-reference-dt25b-lineage")
        derived[key] = v
    qemu = d.get("qemu_firmware")
    if not isinstance(qemu, dict):
        errors.append("audit-qemu_firmware-missing")
    else:
        if not validate_hex64(qemu.get("sha256")):
            errors.append("audit-qemu_firmware-sha256-must-be-64-lower-hex")
        else:
            derived["qemu_sha256"] = qemu.get("sha256")
        qb = qemu.get("bytes")
        if not isinstance(qb, int) or qb <= 0:
            errors.append("audit-qemu_firmware-bytes-must-be-positive-int")
        else:
            derived["qemu_bytes"] = qb
        derived["qemu_path"] = qemu.get("path")
    gp = d.get("guard_policy")
    if isinstance(gp, dict):
        if gp.get("passed") is not True:
            errors.append("audit-guard_policy-passed-must-be-true")
        if gp.get("required_sensor_count") != 20:
            errors.append("audit-guard_policy-requires-20-sensors")
    else:
        errors.append("audit-guard_policy-missing")
    iv = d.get("initramfs_validation")
    if isinstance(iv, dict):
        if iv.get("passed") is not True:
            errors.append("audit-initramfs_validation-passed-must-be-true")
    return (len(errors) == 0, errors, derived)


def validate_08_record(obj, expected_boot_id=None):
    """Validate guest 08-graphics-test.json. Returns (ok, errors, checks)."""
    errors = []
    checks = {}
    if not isinstance(obj, dict):
        return False, ["08-not-a-dict"], {}
    if obj.get("record") != "08-graphics-test":
        errors.append("08-record-must-be-08-graphics-test")
    bid = obj.get("boot_id")
    if not validate_boot_id(bid):
        errors.append("08-boot_id-malformed")
    elif expected_boot_id and bid != expected_boot_id:
        errors.append("08-boot_id-mismatch")
    for f in REQUIRED_08_FIELDS:
        if f not in obj:
            errors.append(f"08-missing-{f}")
    kcmd = obj.get("kcmdline", "")
    checks["kcmdline_has_graphics1"] = (
        isinstance(kcmd, str) and "kestrel_graphics=1" in kcmd
    )
    checks["kcmdline_has_multiuser"] = (
        isinstance(kcmd, str) and "systemd.unit=multi-user.target" in kcmd
    )
    checks["kcmdline_has_ttyAMA0"] = (
        isinstance(kcmd, str) and "ttyAMA0" in kcmd
    )
    checks["kcmdline_no_efilog"] = (
        isinstance(kcmd, str) and "kestrel_efilog=1" not in kcmd
    )
    if not checks["kcmdline_has_graphics1"]:
        errors.append("08-kcmdline-missing-graphics1")
    ug = obj.get("unit_graphics") if isinstance(
        obj.get("unit_graphics"), dict) else {}
    us = obj.get("unit_sddm_private") if isinstance(
        obj.get("unit_sddm_private"), dict) else {}
    checks["unit_graphics_present"] = bool(ug)
    checks["unit_sddm_present"] = bool(us)
    if obj.get("python_exec_ok") is not True:
        errors.append("08-python_exec_ok-must-be-true")
    if obj.get("python_import_ok") is not True:
        errors.append("08-python_import_ok-must-be-true")
    if obj.get("guard_ok") is not False:
        # Guard must refuse (False) on QEMU without sensors/DRM.
        errors.append("08-guard_ok-must-be-false-refusal")
    errs = obj.get("guard_errors")
    if not isinstance(errs, list) or not any(
            "missing_sensor" in str(e) for e in errs):
        errors.append("08-guard_errors-must-list-missing_sensor")
    if obj.get("journal_preflight_fail") is not True:
        errors.append("08-journal_preflight_fail-must-be-true")
    if obj.get("marker_absent") is not True:
        errors.append("08-marker_absent-must-be-true")
    if obj.get("sddm_proc_absent") is not True:
        errors.append("08-sddm_proc_absent-must-be-true")
    if obj.get("execstartpre_exact") is not True:
        errors.append("08-execstartpre_exact-must-be-true")
    if obj.get("execstoppost_exact") is not True:
        errors.append("08-execstoppost_exact-must-be-true")
    # Safe-GUI-absence rule: GUI absence because ExecPre failed is NOT
    # acceptable. B must show real supervisor preflight refusal, not a unit
    # load failure. Require journal refusal + python refusal jointly.
    if not (obj.get("journal_preflight_fail") is True
            and obj.get("python_exec_ok") is True
            and obj.get("guard_ok") is False):
        errors.append("08-refusal-must-be-supervisor-preflight-not-execpre-fail")
    return (len(errors) == 0, errors, checks)


def validate_09_record(obj, expected_boot_id=None):
    """Validate guest 09-unit-chaos.json. Returns (ok, errors, checks)."""
    errors = []
    checks = {}
    if not isinstance(obj, dict):
        return False, ["09-not-a-dict"], {}
    if obj.get("record") != "09-unit-chaos":
        errors.append("09-record-must-be-09-unit-chaos")
    bid = obj.get("boot_id")
    if not validate_boot_id(bid):
        errors.append("09-boot_id-malformed")
    elif expected_boot_id and bid != expected_boot_id:
        errors.append("09-boot_id-mismatch")
    for f in REQUIRED_09_FIELDS:
        if f not in obj:
            errors.append(f"09-missing-{f}")
    # Setup conjunction.
    checks["setup_stale_created"] = obj.get("stale_marker_created") is True
    checks["setup_parent_verified_sleep"] = (
        obj.get("parent_execstart_verified_sleep") is True
    )
    checks["setup_parent_active"] = obj.get("parent_active_before") is True
    pb = obj.get("parent_pid_before")
    checks["setup_parent_pid_nonzero"] = (
        isinstance(pb, int) and pb > 0
    )
    checks["setup_pre_cleared"] = (
        obj.get("execstartpre_cleared_marker") is True
    )
    checks["setup_fake_marker"] = obj.get("fake_marker_created") is True
    checks["setup_child_active"] = obj.get("child_active_before") is True
    cb = obj.get("child_pid_before")
    checks["setup_child_pid_nonzero"] = (
        isinstance(cb, int) and cb > 0
    )
    if not all([checks["setup_stale_created"],
                checks["setup_parent_verified_sleep"],
                checks["setup_parent_active"],
                checks["setup_parent_pid_nonzero"],
                checks["setup_pre_cleared"],
                checks["setup_fake_marker"],
                checks["setup_child_active"],
                checks["setup_child_pid_nonzero"]]):
        errors.append("09-setup-incomplete")
    # Fault conjunction.
    checks["fault_kill_sent"] = (
        obj.get("kill_sent") is True and obj.get("kill_rc") == 0
    )
    if not checks["fault_kill_sent"]:
        errors.append("09-kill-must-be-rc0-sent")
    pa = obj.get("parent_after") if isinstance(
        obj.get("parent_after"), dict) else {}
    checks["fault_parent_failed"] = (
        pa.get("ActiveState") == "failed" and pa.get("MainPID") == 0
        and pa.get("Result") == "signal"
    )
    if not checks["fault_parent_failed"]:
        errors.append("09-parent_after-must-be-failed-pid0-signal")
    # After conjunction (bounded 15s, no manual stop before measurement).
    ca = obj.get("child_after_auto") if isinstance(
        obj.get("child_after_auto"), dict) else {}
    checks["after_child_inactive"] = ca.get("ActiveState") in (
        "inactive", "dead", "failed")
    checks["after_child_pid0"] = ca.get("MainPID") == 0
    checks["after_old_gone"] = obj.get("old_child_pid_gone") is True
    checks["after_marker_absent"] = obj.get("marker_absent_post") is True
    mws = obj.get("measured_within_s")
    checks["after_within_15s"] = (
        isinstance(mws, (int, float)) and 0 < mws <= 15
    )
    if obj.get("cleanup_owned_fake_only") is not True:
        errors.append("09-cleanup-owned-fake-only-required")
    if not checks["after_within_15s"]:
        errors.append("09-measurement-must-be-within-15s")
    if not (checks["after_child_inactive"] and checks["after_child_pid0"]
            and checks["after_old_gone"]
            and checks["after_marker_absent"]):
        # RED preserved: child stays active is a real RED, not a pass.
        errors.append("09-child-must-be-auto-inactive-pid0-gone-marker-absent")
    # New rule: marker left is FAIL (old expectation changed).
    if obj.get("marker_absent_post") is not True:
        errors.append("09-marker-left-is-fail-requires-absent-post-stop")
    return (len(errors) == 0, errors, checks)


def evaluate_c_serial(clean):
    """Coupled C evaluation from serial clean text (fallback oracle).

    Returns (passed: bool, checks: dict, detail: str). Requires ALL of
    setup + fault + after conjunctively; inactive-child vacuous pass is
    impossible because after requires before-active + kill-rc0 + parent-dead.
    """
    checks = {}
    parent_before = actual_block(
        clean, "===C-START-FAKE-PARENT===", "===C-START-FAKE-CHILD===")
    child_before = actual_block(
        clean, "===C-START-FAKE-CHILD===",
        "===C-KILL-PARENT-MAIN-SIGKILL===")
    kill_block = actual_block(
        clean, "===C-KILL-PARENT-MAIN-SIGKILL===",
        "===C-PARENT-AFTER===")
    parent_after = actual_block(
        clean, "===C-PARENT-AFTER===", "===C-CHILD-AFTER===")
    child_after = actual_block(
        clean, "===C-CHILD-AFTER===",
        "===C-CLEANUP-OWNED-FAKE-ONLY===")

    def has(block, pat):
        return bool(block and re.search(pat, block))

    checks["c_fake_parent_active_before"] = bool(
        parent_before
        and has(parent_before, r"ActiveState=active")
        and has(parent_before, r"MainPID=[1-9][0-9]*")
        and re.search(r"C_PARENT_PID_BEFORE=[1-9][0-9]*", clean))
    checks["c_fake_child_active_before"] = bool(
        child_before
        and has(child_before, r"ActiveState=active")
        and has(child_before, r"MainPID=[1-9][0-9]*")
        and re.search(r"C_CHILD_PID_BEFORE=[1-9][0-9]*", clean))
    checks["c_execstart_overridden_to_sleep"] = (
        FAKE_EXEC in clean
        and "===C-EXECSTART-VERIFY===" in clean
    )
    checks["c_kill_sent"] = bool(
        kill_block
        and re.search(r"\r?\nKILL_SENT\r?\n", kill_block)
        and re.search(r"C_KILL_RC=0", kill_block)
        and not re.search(r"\r?\nKILL_CMD_FAIL\r?\n", kill_block))
    checks["c_parent_failed_after_sigkill"] = bool(
        parent_after
        and has(parent_after, r"ActiveState=failed")
        and has(parent_after, r"MainPID=0")
        and has(parent_after, r"Result=signal"))
    checks["c_parent_pid_before_nonzero"] = bool(
        re.search(r"C_PARENT_PID_BEFORE=[1-9][0-9]*", clean))
    checks["c_child_pid_before_nonzero"] = bool(
        re.search(r"C_CHILD_PID_BEFORE=[1-9][0-9]*", clean))
    checks["c_parent_pid_after_zero"] = bool(
        re.search(r"C_PARENT_PID_AFTER=0", clean))
    checks["c_child_pid_after_captured"] = bool(
        re.search(r"C_CHILD_PID_AFTER=(\d+)", clean))
    # New stale-marker + ExecStartPre-cleared + fake-marker ordering is
    # asserted by the harness guest JSON; serial fallback requires at least
    # the stale/faithful markers to be present as actual lines.
    checks["c_stale_marker_setup"] = bool(
        re.search(r"\r?\nSTALE_MARKER_CREATED\r?\n", clean)
        or "STALE_MARKER_CREATED" in clean)
    checks["c_pre_cleared_marker"] = bool(
        re.search(r"\r?\nPRE_CLEARED_MARKER\r?\n", clean)
        or "PRE_CLEARED_MARKER" in clean)
    # After: conjunctive, no vacuous pass.
    setup_ok = bool(
        checks["c_fake_parent_active_before"]
        and checks["c_fake_child_active_before"]
        and checks["c_kill_sent"]
        and checks["c_parent_failed_after_sigkill"])
    if not setup_ok:
        checks["c_child_inactive_gone_after_parent_sigkill"] = False
        return False, checks, "precondition-failed"
    if child_after is None:
        checks["c_child_inactive_gone_after_parent_sigkill"] = False
        return False, checks, "missing-child-after-block"
    inactive = bool(
        re.search(r"ActiveState=(inactive|dead|failed)", child_after)
        and re.search(r"MainPID=0", child_after))
    stays_active = bool(
        re.search(r"ActiveState=active", child_after)
        and re.search(r"MainPID=[1-9][0-9]*", child_after))
    marker_absent_post = bool(
        re.search(r"MARKER_ABSENT_POST", child_after)
        or re.search(r"MARKER_ABSENT_POST", clean))
    if stays_active:
        checks["c_child_inactive_gone_after_parent_sigkill"] = False
        return False, checks, "RED-child-stays-active"
    if inactive and marker_absent_post:
        checks["c_child_inactive_gone_after_parent_sigkill"] = True
        return True, checks, "child-inactive-gone-marker-absent"
    checks["c_child_inactive_gone_after_parent_sigkill"] = False
    return False, checks, "ambiguous-child-state-or-marker-left"
