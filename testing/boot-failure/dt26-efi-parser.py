#!/usr/bin/env python3
"""dt26 EFI parser/oracle helpers (revision-aware, import-safe).

Owns ONLY dt26-efi-* parsing. No top-level side effects: importing this
module never touches FAT/QEMU/lock/logs. All functions are pure except
explicit file reads passed by callers.

Oracle preference (enforced by harness, implemented here as validators):
  1. Guest-generated structured JSON persisted to validated VM USB:
     /run/archiso/bootmnt/Logs/boot-<boot-id>/08-graphics-preflight.json
     /run/archiso/bootmnt/Logs/boot-<boot-id>/09-graphics-status.json
     /run/archiso/bootmnt/Logs/boot-<boot-id>/10-graphics-journal.log
     (production observer; supervisor emits structured passed/detail for
     BOTH success and refusal)
  2. QA chaos record for the fake-unitgraph C sequence:
     /run/archiso/bootmnt/Logs/boot-<boot-id>/09-unit-chaos.json
     (distinct from production 09-graphics-status.json; separation kept)
  3. Serial fallback only with anchored records + strict JSON validation;
     missing record is FAIL, never vacuous pass.
Command-echo contamination rule: a marker counts as ACTUAL only when it is
newline-delimited (\\r?\\nMARKER\\r?\\n). Occurrences inside typed-command
echoes (``echo MARKER; ...``) are ignored.
Boot selection rule: one shared FAT means A and B/C extractions share a
directory with two boot-<id> leaves. Callers must resolve leaves via
leaf_in_boot(extract, boot_id, leaf) and require A/B boot_ids differ;
rglob-first / require-exactly-one across both boots is forbidden.
Guest-send rule: every send must end with a REAL newline, must not contain
';try:', and embedded ``python3 -c '...'`` bodies must compile.
"""
import ast
import json
import re

REVISION = "v2-dt26"

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
BOOTID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
PROMPT_RE = re.compile(r"(?:^|[\r\n])KESTREL-TEXT# ")
MULTI_RE = re.compile(r"Reached target [^\r\n]*Multi-User System")

# Exact fixed unit-contract strings (deleg_03f10f91, unchanged).
PARENT_PRE = "/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed"
PARENT_POST = "/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed"
FAKE_EXEC = "/usr/bin/sleep 600"
OWNED_UNIT = "kestrel-graphics-sddm.service"

# A proof helper identity (helper script, NOT UKI artifact hash).
HELPER_REVISION = "v2-dt26"

REQUIRED_09_FIELDS = [
    "record", "boot_id", "stale_marker_created",
    "parent_execstart_verified_sleep", "parent_active_before",
    "parent_pid_before", "execstartpre_cleared_marker",
    "fake_marker_created", "child_active_before", "child_pid_before",
    "kill_rc", "kill_sent", "parent_after", "child_after_auto",
    "old_child_pid_gone", "marker_absent_post",
    "cleanup_owned_fake_only", "measured_within_s",
]

PREFLIGHT_REQUIRED = [
    "passed", "reason", "detail",
    "native_graphics_validated",
]

STATUS_REQUIRED = [
    "reason", "bounded_cleanup", "owned_unit", "owned_session",
    "owned_stopped", "owned_gone", "tty2_restored", "steps",
    "restart_text", "native_graphics_validated",
    "session_active_is_not_pixel_proof",
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

    Both markers must appear as full standalone executed lines:
    ``(?:^|\\\\r?\\\\n)MARKER\\\\r?\\\\n``. Command echoes such as
    ``echo MARKER; ...`` or ``echo START`` fragments do not match because
    they lack the leading newline + trailing newline shape. Returns None
    when either marker is missing (fail-closed). When several actual
    occurrences exist, the LAST start is used (post-boot actual, not
    pre-boot echo duplication).
    """
    if not clean or not start_marker:
        return None
    pat_start = re.compile(r"(?:^|\r?\n)" + re.escape(start_marker) + r"\r?\n")
    starts = list(pat_start.finditer(clean))
    if not starts:
        return None
    s = starts[-1].end()
    if end_marker is None:
        return clean[s:s + 8000]
    pat_end = re.compile(r"(?:^|\r?\n)" + re.escape(end_marker) + r"\r?\n")
    window = clean[s:s + 8000 + len(end_marker) + 8]
    m_end = pat_end.search(window)
    if not m_end:
        return None
    # Include the line ending that terminates the last content line: the
    # end marker's leading \r?\n IS that line ending, so keep it in the
    # returned block (callers match \nMARKER\n shapes inside the block).
    g0 = m_end.group(0)
    if g0.startswith("\r\n"):
        cut = m_end.start() + 2
    elif g0.startswith("\n") or g0.startswith("\r"):
        cut = m_end.start() + 1
    else:
        cut = m_end.start()
    return window[:cut]


def is_anchored_marker(clean, marker):
    """True only when MARKER appears as an executed \\n-delimited line."""
    if not clean or not marker:
        return False
    return bool(re.search(r"\r?\n" + re.escape(marker) + r"\r?\n", clean))


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
    return isinstance(s, str) and HEX64_RE.fullmatch(s) is not None


def validate_boot_id(s):
    return isinstance(s, str) and BOOTID_RE.fullmatch(s) is not None


def _as_int(x):
    """Legacy tolerant coercion (serial/cli contexts only, NOT JSON reports).

    JSON 09-unit-chaos validation must NOT use this: report PIDs/counts
    require ``type(x) is int`` (bools/strings/floats rejected, never
    repaired). Kept for CLI ``systemctl show`` string parsing helpers.
    """
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        t = x.strip()
        if re.fullmatch(r"[0-9]+", t):
            try:
                return int(t, 10)
            except (ValueError, TypeError):
                return None
    return None


def _strict_pid_nonzero(x):
    """True only when type(x) is int (not bool) and x > 0."""
    return type(x) is int and x > 0


def _strict_pid_zero(x):
    """True only when type(x) is int (not bool) and x == 0."""
    return type(x) is int and x == 0


def validate_audit_dict(d):
    """Validate a dt26 artifact audit dict. Returns (ok, errors, derived).

    Never repairs tokens: invalid format is reported, never replaced with a
    default hash. Requires revision v2-dt26, passed true, 64-lower-hex
    hashes EXACTLY, positive byte counts, and private-build-root paths with
    dt26 lineage. SFS hash/size are required from the audit (or gated
    explicitly by the harness via validate_explicit_sfs).
    """
    errors = []
    derived = {}
    if not isinstance(d, dict):
        return False, ["audit-not-a-dict"], {}
    if d.get("passed") is not True:
        errors.append("audit-passed-must-be-true")
    if d.get("revision") != "v2-dt26":
        errors.append("audit-revision-must-be-v2-dt26")
    for key in ("uki_sha256", "initramfs_sha256", "sfs_sha256"):
        v = d.get(key)
        if not validate_hex64(v):
            errors.append(f"audit-{key}-must-be-64-lower-hex")
        else:
            derived[key] = v
    for key in ("uki_bytes", "sfs_bytes"):
        v = d.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            errors.append(f"audit-{key}-must-be-positive-int")
        else:
            derived[key] = v
    for key in ("uki_path", "initramfs_path"):
        v = d.get(key)
        if not isinstance(v, str) or not v.startswith("/home/builder/"):
            errors.append(f"audit-{key}-must-be-in-private-build-root")
        elif "uki-v2-dt26" not in v and "live" not in v.lower():
            if "dt26" not in v:
                errors.append(f"audit-{key}-must-reference-dt26-lineage")
        derived[key] = v
    if isinstance(d.get("sfs_path"), str) and d["sfs_path"]:
        if not d["sfs_path"].startswith("/home/builder/"):
            errors.append("audit-sfs_path-must-be-in-private-build-root")
        else:
            derived["sfs_path"] = d["sfs_path"]
    qemu = d.get("qemu_firmware")
    if not isinstance(qemu, dict):
        errors.append("audit-qemu_firmware-missing")
    else:
        if not validate_hex64(qemu.get("sha256")):
            errors.append("audit-qemu_firmware-sha256-must-be-64-lower-hex")
        else:
            derived["qemu_sha256"] = qemu.get("sha256")
        qb = qemu.get("bytes")
        if not isinstance(qb, int) or isinstance(qb, bool) or qb <= 0:
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


def validate_explicit_sfs(sha256, nbytes):
    """Gate explicit --sfs-* CLI tokens. Returns (ok, errors)."""
    errors = []
    if not validate_hex64(sha256):
        errors.append("explicit-sfs-sha256-must-be-64-lower-hex")
    if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes <= 0:
        errors.append("explicit-sfs-bytes-must-be-positive-int")
    return (len(errors) == 0, errors)


def validate_preflight_record(obj):
    """Validate production 08-graphics-preflight.json. Returns (ok, errors, checks).

    Stable supervisor contract: top-level ``passed`` bool, ``reason``
    nonempty str, structured ``detail`` dict containing the actual
    thermal+DRM guard outcome, ``native_graphics_validated`` False.
    BOTH success and refusal schemas accepted here; refusal-vs-pass is
    decided by the harness (B requires passed is False).
    Early unknown-baseline failures legitimately carry a reason with an
    empty/minimal detail (no evaluated hardware yet) and are schema-valid.
    Top-level duplicate thermal/drm/drm_snapshot are legacy and NOT
    required; when present they are type-checked only, never fabricated.
    Generic snapshot shape checks live here; specific B missing-hardware
    refusal assertions live in the harness.
    """
    errors = []
    checks = {}
    if not isinstance(obj, dict):
        return False, ["preflight-not-a-dict"], {}
    for f in PREFLIGHT_REQUIRED:
        if f not in obj:
            errors.append(f"preflight-missing-{f}")
    checks["passed_is_bool"] = isinstance(obj.get("passed"), bool)
    if not checks["passed_is_bool"]:
        errors.append("preflight-passed-must-be-bool")
    reason = obj.get("reason")
    checks["reason_nonempty"] = isinstance(reason, str) and len(reason) > 0
    if not checks["reason_nonempty"]:
        errors.append("preflight-reason-must-be-nonempty-str")
    checks["detail_is_dict"] = isinstance(obj.get("detail"), dict)
    if not checks["detail_is_dict"]:
        errors.append("preflight-detail-must-be-dict")
    if obj.get("native_graphics_validated") is not False:
        errors.append("preflight-native_graphics_validated-must-be-false")
    detail = obj.get("detail") if isinstance(obj.get("detail"), dict) else {}
    for k in ("thermal", "drm", "drm_snapshot"):
        if k in detail and detail[k] is not None and not isinstance(detail[k], dict):
            errors.append(f"preflight-detail-{k}-must-be-dict-or-null")
    # Legacy top-level duplicates: type-check only, never require.
    for k in ("thermal", "drm", "drm_snapshot"):
        if k in obj and obj[k] is not None and not isinstance(obj[k], dict):
            errors.append(f"preflight-{k}-must-be-dict-or-null")
    checks["detail_has_thermal"] = isinstance(detail.get("thermal"), dict)
    checks["detail_has_drm"] = isinstance(detail.get("drm"), dict)
    checks["thermal_present"] = "thermal" in obj or "thermal" in detail
    checks["drm_present"] = "drm" in obj or "drm" in detail
    checks["snapshot_present"] = "drm_snapshot" in obj or "drm_snapshot" in detail
    return (len(errors) == 0, errors, checks)


def validate_status_record(obj):
    """Validate production 09-graphics-status.json. Returns (ok, errors, checks)."""
    errors = []
    checks = {}
    if not isinstance(obj, dict):
        return False, ["status-not-a-dict"], {}
    for f in STATUS_REQUIRED:
        if f not in obj:
            errors.append(f"status-missing-{f}")
    if not isinstance(obj.get("reason"), str) or not obj.get("reason"):
        errors.append("status-reason-must-be-nonempty-str")
    if not isinstance(obj.get("bounded_cleanup"), bool):
        errors.append("status-bounded_cleanup-must-be-bool")
    if obj.get("owned_unit") != OWNED_UNIT:
        errors.append("status-owned_unit-must-be-private-sddm-only")
    if not isinstance(obj.get("owned_stopped"), bool):
        errors.append("status-owned_stopped-must-be-bool")
    if not isinstance(obj.get("owned_gone"), bool):
        errors.append("status-owned_gone-must-be-bool")
    if not isinstance(obj.get("tty2_restored"), bool):
        errors.append("status-tty2_restored-must-be-bool")
    if not isinstance(obj.get("steps"), list):
        errors.append("status-steps-must-be-list")
    if obj.get("native_graphics_validated") is not False:
        errors.append("status-native_graphics_validated-must-be-false")
    if obj.get("session_active_is_not_pixel_proof") is not True:
        errors.append("status-session_active_is_not_pixel_proof-must-be-true")
    checks["bounded_cleanup"] = obj.get("bounded_cleanup") is True
    checks["owned_unit_private_only"] = obj.get("owned_unit") == OWNED_UNIT
    return (len(errors) == 0, errors, checks)


def validate_journal_text(text):
    """Validate production 10-graphics-journal.log text. Returns (ok, errors, checks)."""
    errors = []
    checks = {}
    if not isinstance(text, str):
        return False, ["journal-not-str"], {}
    checks["nonempty"] = len(text.strip()) > 0
    if not checks["nonempty"]:
        errors.append("journal-empty")
        return False, errors, checks
    checks["preflight_logged"] = "KESTREL_GRAPHICS_PREFLIGHT_FAIL" in text or "PREFLIGHT_FAIL" in text
    if not checks["preflight_logged"]:
        errors.append("journal-must-show-preflight-fail")
    checks["cleanup_done"] = "KESTREL_GRAPHICS_CLEANUP_DONE" in text or "CLEANUP_DONE" in text
    if not checks["cleanup_done"]:
        errors.append("journal-must-show-cleanup-done")
    checks["no_pixel_claim"] = "pixel proof" not in text.lower() or "not pixel proof" in text.lower() or "not proof" in text.lower()
    if len(text) > 131072 + 4096:
        errors.append("journal-exceeds-observer-cap")
    return (len(errors) == 0, errors, checks)


def validate_09_record(obj, expected_boot_id=None):
    """Validate QA 09-unit-chaos.json. Returns (ok, errors, checks).

    Reader never repairs JSON types: PIDs/counts require ``type(x) is int``
    (bool is rejected despite subclassing int); numeric strings, floats,
    hex and bools fail. The guest collector normalizes PIDs to real ints
    before persisting; ``systemctl show`` CLI strings are parsed separately
    via parse_show/serial checks, never via tolerant report normalization.
    """
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
    # Strict JSON number types: type(x) is int, never bool/str.
    pb_raw = obj.get("parent_pid_before")
    if "parent_pid_before" in obj and type(pb_raw) is not int:
        errors.append("09-parent_pid_before-must-be-int-not-bool-or-str")
    cb_raw = obj.get("child_pid_before")
    if "child_pid_before" in obj and type(cb_raw) is not int:
        errors.append("09-child_pid_before-must-be-int-not-bool-or-str")
    kill_rc_raw = obj.get("kill_rc")
    if "kill_rc" in obj and type(kill_rc_raw) is not int:
        errors.append("09-kill_rc-must-be-int-not-bool-or-str")
    checks["setup_stale_created"] = obj.get("stale_marker_created") is True
    checks["setup_parent_verified_sleep"] = (
        obj.get("parent_execstart_verified_sleep") is True
    )
    checks["setup_parent_active"] = obj.get("parent_active_before") is True
    checks["setup_parent_pid_nonzero"] = _strict_pid_nonzero(pb_raw)
    checks["setup_pre_cleared"] = (
        obj.get("execstartpre_cleared_marker") is True
    )
    checks["setup_fake_marker"] = obj.get("fake_marker_created") is True
    checks["setup_child_active"] = obj.get("child_active_before") is True
    checks["setup_child_pid_nonzero"] = _strict_pid_nonzero(cb_raw)
    if not all([checks["setup_stale_created"],
                checks["setup_parent_verified_sleep"],
                checks["setup_parent_active"],
                checks["setup_parent_pid_nonzero"],
                checks["setup_pre_cleared"],
                checks["setup_fake_marker"],
                checks["setup_child_active"],
                checks["setup_child_pid_nonzero"]]):
        errors.append("09-setup-incomplete")
    checks["fault_kill_sent"] = (
        obj.get("kill_sent") is True and type(kill_rc_raw) is int and kill_rc_raw == 0
    )
    if not checks["fault_kill_sent"]:
        errors.append("09-kill-must-be-rc0-sent")
    pa = obj.get("parent_after") if isinstance(
        obj.get("parent_after"), dict) else {}
    if "MainPID" in pa and type(pa.get("MainPID")) is not int:
        errors.append("09-parent_after-MainPID-must-be-int-not-bool-or-str")
    pa_pid_is_zero = _strict_pid_zero(pa.get("MainPID")) if "MainPID" in pa else False
    checks["fault_parent_failed"] = (
        pa.get("ActiveState") == "failed" and pa_pid_is_zero
        and pa.get("Result") == "signal"
    )
    if not checks["fault_parent_failed"]:
        errors.append("09-parent_after-must-be-failed-pid0-signal")
    ca = obj.get("child_after_auto") if isinstance(
        obj.get("child_after_auto"), dict) else {}
    if "MainPID" in ca and type(ca.get("MainPID")) is not int:
        errors.append("09-child_after_auto-MainPID-must-be-int-not-bool-or-str")
    checks["after_child_inactive"] = ca.get("ActiveState") in (
        "inactive", "dead", "failed")
    checks["after_child_pid0"] = (
        _strict_pid_zero(ca.get("MainPID")) if "MainPID" in ca else False
    )
    checks["after_old_gone"] = obj.get("old_child_pid_gone") is True
    checks["after_marker_absent"] = obj.get("marker_absent_post") is True
    mws = obj.get("measured_within_s")
    checks["after_within_15s"] = (
        isinstance(mws, (int, float)) and not isinstance(mws, bool)
        and 0 < mws <= 15
    )
    if obj.get("cleanup_owned_fake_only") is not True:
        errors.append("09-cleanup-owned-fake-only-required")
    if not checks["after_within_15s"]:
        errors.append("09-measurement-must-be-within-15s")
    if not (checks["after_child_inactive"] and checks["after_child_pid0"]
            and checks["after_old_gone"]
            and checks["after_marker_absent"]):
        errors.append("09-child-must-be-auto-inactive-pid0-gone-marker-absent")
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
    checks["c_stale_marker_setup"] = bool(
        re.search(r"\r?\nSTALE_MARKER_CREATED\r?\n", clean)
        or "STALE_MARKER_CREATED" in clean)
    checks["c_pre_cleared_marker"] = bool(
        re.search(r"\r?\nPRE_CLEARED_MARKER\r?\n", clean)
        or "PRE_CLEARED_MARKER" in clean)
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


def validate_guest_send(send):
    """Validate one guest send string. Returns (ok, errors).

    Every send must end with a REAL newline, must not contain ';try:'
    (shell/python splice error), must not contain NUL, and every embedded
    ``python3 -c '...'`` body must compile as Python. Only double quotes
    may appear inside embedded bodies so the shell single-quote span is
    unambiguous.
    """
    errors = []
    if not isinstance(send, str):
        return False, ["send-not-str"]
    if "\x00" in send:
        errors.append("send-contains-NUL")
    if not send.endswith("\n"):
        errors.append("send-must-end-with-real-newline")
    if ";try:" in send:
        errors.append("send-contains-forbidden-;try:")
    for m in re.finditer(r"python3 -c '(.*?)' 2>&1", send, re.S):
        body = m.group(1)
        try:
            ast.parse(body)
        except SyntaxError as e:
            errors.append(f"embedded-python-syntax-error: {e}"[:200])
    return (len(errors) == 0, errors)


def list_boot_ids(extract_path):
    """List valid boot-ids present as Logs/boot-<id> dirs (sorted)."""
    from pathlib import Path
    ids = []
    try:
        base = Path(extract_path)
        if not base.is_dir():
            return []
        for q in base.iterdir():
            name = q.name
            if q.is_dir() and name.startswith("boot-"):
                bid = name[len("boot-"):]
                if validate_boot_id(bid):
                    ids.append(bid)
    except (OSError, ValueError):
        return []
    return sorted(ids)


def leaf_in_boot(extract_path, boot_id, leaf):
    """Resolve exactly one leaf file strictly inside boot-<boot_id>/.

    Never searches across boots. Returns the Path, or None when the boot
    id is malformed, the boot dir is absent, or the leaf count inside that
    boot dir is not exactly one (missing or ambiguous both fail closed).
    """
    from pathlib import Path
    if not validate_boot_id(boot_id):
        return None
    try:
        d = Path(extract_path) / ("boot-" + boot_id)
        if not d.is_dir():
            return None
        cands = [q for q in d.rglob(leaf) if q.is_file()]
        if len(cands) != 1:
            return None
        return cands[0]
    except (OSError, ValueError):
        return None


def validate_boot_pair(a_bid, b_bid):
    """Require two distinct valid boot ids (A vs B/C). Returns (ok, errors)."""
    errors = []
    if not validate_boot_id(a_bid):
        errors.append("a-boot_id-malformed")
    if not validate_boot_id(b_bid):
        errors.append("b-boot_id-malformed")
    if errors:
        return False, errors
    if a_bid == b_bid:
        errors.append("a-b-boot_id-must-differ-shared-fat")
    return (len(errors) == 0, errors)
