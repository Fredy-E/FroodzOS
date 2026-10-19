#!/bin/bash
# SPDX-License-Identifier: MIT
# Runs in the live overlay; writes ONLY through the initramfs-validated USB mount.
set -u
# True monotonic start BEFORE any potentially slow setup (mountpoint/readlink/cat).
# BASH_MONOSECONDS is monotonic seconds and assignment-ignored (SECONDS=0 cannot
# reset it); fallback is kernel /proc/uptime (monotonic, not wall). SECONDS is
# resettable/wall-ish and is NEVER used for the deadline.
logger_has_clock=0
logger_clock_src='none'
logger_start_s=''
if [ -n "${BASH_MONOSECONDS-}" ]; then
    case "$BASH_MONOSECONDS" in ''|*[!0-9]*) ;; *) logger_start_s=$BASH_MONOSECONDS; logger_has_clock=1; logger_clock_src='BASH_MONOSECONDS' ;; esac
fi
if [ "$logger_has_clock" = 0 ] && [ -r /proc/uptime ]; then
    # Builtin-only proc value: no fork/exec of cut on the startup path.
    _up_first=''; _up_rest=''
    IFS=' ' read -r _up_first _up_rest < /proc/uptime 2>/dev/null || true
    _up_int=${_up_first%%.*}
    case "$_up_int" in ''|*[!0-9]*) ;; *) logger_start_s=$_up_int; logger_has_clock=1; logger_clock_src='proc-uptime' ;; esac
    unset _up_first _up_rest _up_int
fi
state=${KESTREL_CAPTURE_STATE:-/run/kestrel-capture}
[ -r "$state/destination" ] && [ -r "$state/device" ] && [ -r "$state/bootmnt" ] || exit 0
read -r dest <"$state/destination"
read -r dev <"$state/device"
read -r bootmnt <"$state/bootmnt"
[ "$bootmnt" = /run/archiso/bootmnt ] || exit 1
case "$dest" in "$bootmnt"/Logs/boot-*) ;; *) exit 1 ;; esac
# Graphics outcome capture (USB logger ONLY; supervisor stays /run-only).
# Exact-token opt-in: kestrel_graphics=1 observes a ~260s monotonic wall-clock
# budget from logger start (covers a full 180s session plus 25s cleanup with
# margin). Text mode keeps the validated 120-sample behavior. All persistence
# is fail-open: logging failures never block boot and never delete the last
# good output.
#
# Timing honesty (best-effort, NOT hard realtime): the graphics bound is a fixed
# window from logger start using a true monotonic clock (BASH_MONOSECONDS, else
# kernel /proc/uptime integer seconds; 1s resolution). Remaining allowance is
# recomputed BEFORE EVERY external/interruptible operation (each journalctl,
# each systemctl, each Python persist, each copy/sync/journal) and an already
# exhausted iteration does no more work. Each userspace wait uses
# `timeout -k <kill_after>s <t>s` so a TERM-ignoring child is KILLed after a
# short grace (default 2s). Worst overshoot for a TERM-ignoring child started
# just before the deadline is ~kill_after + ~1s scheduler; responsive children
# overshoot at most ~1s scheduler. Kernel-uninterruptible (D-state) I/O or a
# wedged storage sync cannot be interrupted by userspace and may exceed any
# bound. If no safe clock or no `timeout` is available, unsafe captures are
# skipped (fail-open, exit 0), NEVER run unbounded.
#
# Whole-run bound (graphics mode only): when a safe clock and `timeout`
# are both present, the entrypoint above runs the existing body below as
# one internal child under a single outer `timeout -k 1s <remaining+2>s`
# in its own process group (never --foreground, so no shared-group kill
# can reach unrelated units). The +2s is an orderly-exit drain (1s clock
# resolution + ~1s exit/sync); a run that finishes inside its window
# keeps the normal FINISHED line, while a run still stuck after the drain
# is TERM/KILLed by the watchdog and writes only
# KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED (never FINISHED), preserves the
# last-good leaves, and still exits 0. Every external on the expired path
# is itself `timeout`-wrapped, and no unbounded sync follows expiration.
# Kernel-uninterruptible (D-state) I/O remains an honest unavoidable limit.
#
# Runtime needs (integrator): the live image must provide `timeout`
# (coreutils) and `python3` for the bounded calls and the atomic JSON persist
# below; the frozen SFS already carries both. If either is absent the logger
# degrades to fail-open (keeps last-good, still exits 0) and notes it in
# 00-status.txt. No new installed helper is used: the Python block below runs
# inline from this already-shipped file, so no hook/packaging change is
# needed for it. TESTONLY runtime: unshare/mount are used by the bounds tests
# for private-mount isolation and are NOT production dependencies.
graphics_requested=0
# Builtin-only cmdline read: no fork/exec of cat on the startup path.
_graphics_cmdline=''
IFS= read -r _graphics_cmdline <"${KESTREL_CMDLINE_FILE:-/proc/cmdline}" 2>/dev/null || true
case " $_graphics_cmdline " in *" kestrel_graphics=1 "*) graphics_requested=1 ;; esac
unset _graphics_cmdline
total_samples=${KESTREL_TEXT_SAMPLES:-120}
case "$total_samples" in ''|*[!0-9]*) total_samples=120 ;; esac
if [ "$total_samples" -lt 1 ] 2>/dev/null; then total_samples=1; fi
if [ "$total_samples" -gt 10000 ] 2>/dev/null; then total_samples=10000; fi
logger_budget_s=${KESTREL_LOGGER_BUDGET_S:-260}
case "$logger_budget_s" in ''|*[!0-9]*) logger_budget_s=260 ;; esac
if [ "$logger_budget_s" -lt 1 ] 2>/dev/null; then logger_budget_s=1; fi
if [ "$logger_budget_s" -gt 3600 ] 2>/dev/null; then logger_budget_s=3600; fi
logger_max_iter=${KESTREL_LOGGER_MAX_ITER:-4096}
case "$logger_max_iter" in ''|*[!0-9]*) logger_max_iter=4096 ;; esac
# Fixed window deadline from logger start (not per-iteration approximation).
logger_deadline=0
if [ "$logger_has_clock" = 1 ]; then
    logger_deadline=$((logger_start_s + logger_budget_s))
fi
graphics_src_dir=${KESTREL_GRAPHICS_STATUS_DIR:-/run/kestrel-graphics}
graphics_json_max=65536
graphics_journal_max=131072
graphics_journal_lines=200
per_call_cap=${KESTREL_LOGGER_CALL_TIMEOUT_S:-15}
case "$per_call_cap" in ''|*[!0-9]*) per_call_cap=15 ;; esac
if [ "$per_call_cap" -lt 1 ] 2>/dev/null; then per_call_cap=1; fi
if [ "$per_call_cap" -gt 120 ] 2>/dev/null; then per_call_cap=120; fi
kill_after_s=${KESTREL_LOGGER_KILL_AFTER_S:-2}
case "$kill_after_s" in ''|*[!0-9]*) kill_after_s=2 ;; esac
if [ "$kill_after_s" -lt 1 ] 2>/dev/null; then kill_after_s=1; fi
if [ "$kill_after_s" -gt 10 ] 2>/dev/null; then kill_after_s=10; fi
HAVE_TIMEOUT=0
HAVE_PYTHON3=0
if command -v timeout >/dev/null 2>&1; then HAVE_TIMEOUT=1; fi
if command -v python3 >/dev/null 2>&1; then HAVE_PYTHON3=1; fi
# Outer whole-run process-group watchdog (graphics mode only, single instance).
# Everything above is builtins only (clock/cmdline/validation), so the first
# external setup (mountpoint/readlink/sync below) already runs inside the
# internal child, bounded by this watchdog. Outer runs the existing body as
# one child under `timeout -k 1s <remaining+2>s` in its own process group
# (default mode, never --foreground, so the kill can never reach unrelated
# units). The +2s is an orderly-exit drain: runs that finish inside their
# window keep the normal FINISHED line; a run still stuck after the drain is
# TERM/KILLed and records only KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED
# (never FINISHED), preserves last-good leaves, and still exits 0.
if [ "${KESTREL_LOGGER_INNER-}" != 1 ] && [ "$graphics_requested" = 1 ] && [ "$logger_has_clock" = 1 ] && [ "$HAVE_TIMEOUT" = 1 ]; then
    _outer_now=''
    if [ "$logger_clock_src" = BASH_MONOSECONDS ]; then
        case "${BASH_MONOSECONDS-}" in ''|*[!0-9]*) _outer_now='' ;; *) _outer_now=$BASH_MONOSECONDS ;; esac
    elif [ "$logger_clock_src" = proc-uptime ] && [ -r /proc/uptime ]; then
        _outer_first=''; _outer_rest=''
        IFS=' ' read -r _outer_first _outer_rest < /proc/uptime 2>/dev/null || true
        _outer_int=${_outer_first%%.*}
        case "$_outer_int" in ''|*[!0-9]*) _outer_now='' ;; *) _outer_now=$_outer_int ;; esac
        unset _outer_first _outer_rest _outer_int
    fi
    _outer_rem=0
    case "$_outer_now" in ''|*[!0-9]*) ;; *) _outer_rem=$((logger_deadline - _outer_now)) ;; esac
    unset _outer_now
    case "$_outer_rem" in ''|*[!0-9]*) _outer_rem=0 ;; esac
    if [ "$_outer_rem" -ge 1 ] 2>/dev/null; then
        _outer_timeout_s=$((_outer_rem + 2))
        unset _outer_rem
        export KESTREL_LOGGER_INNER=1
        _outer_self="${BASH_SOURCE[0]:-$0}"
        timeout -k 1s "${_outer_timeout_s}s" bash -- "$_outer_self" ${1+"$@"}
        _outer_rc=$?
        unset _outer_timeout_s _outer_self
        if [ "$_outer_rc" = 124 ] || [ "$_outer_rc" = 137 ]; then
            # Watchdog-forced termination: bounded best-effort EXPIRED marker.
            # Re-validates the USB destination (every external is itself
            # `timeout`-wrapped); no unbounded sync follows expiration.
            _exp_state=${KESTREL_CAPTURE_STATE:-/run/kestrel-capture}
            _exp_dest=''; _exp_dev=''; _exp_boot=''
            [ -r "$_exp_state/destination" ] && IFS= read -r _exp_dest <"$_exp_state/destination" 2>/dev/null || true
            [ -r "$_exp_state/device" ] && IFS= read -r _exp_dev <"$_exp_state/device" 2>/dev/null || true
            [ -r "$_exp_state/bootmnt" ] && IFS= read -r _exp_boot <"$_exp_state/bootmnt" 2>/dev/null || true
            if [ "$_exp_boot" = /run/archiso/bootmnt ]; then
                case "$_exp_dest" in "$_exp_boot"/Logs/boot-*)
                    if timeout -k 1s 2s mountpoint -q "$_exp_boot" 2>/dev/null; then
                        _exp_target=$(timeout -k 1s 2s cat "$_exp_boot/KESTREL-LOG-TARGET" 2>/dev/null || printf '')
                        if [ "$_exp_target" = KESTREL_A64_USB_CAPTURE_V1 ]; then
                            _exp_name=${_exp_dev##*/}
                            _exp_link=$(timeout -k 1s 2s readlink -f "/sys/class/block/$_exp_name" 2>/dev/null || printf '')
                            case "$_exp_link" in */usb[0-9]*/*)
                                printf '%s\n' "KESTREL_USERSPACE_CAPTURE_WINDOW_EXPIRED (graphics_requested=1 budget_s=$logger_budget_s text_samples=$total_samples iterations=unknown clock=$logger_clock_src outer_drain_s=2 outer_kill_s=1)" >>"$_exp_dest/00-status.txt" 2>/dev/null || true
                                timeout -k 1s 2s sync -f "$_exp_dest/00-status.txt" 2>/dev/null || true
                                ;;
                            esac
                            unset _exp_name _exp_link
                        fi
                        unset _exp_target
                    fi
                    ;;
                esac
            fi
            unset _exp_state _exp_dest _exp_dev _exp_boot
            exit 0
        fi
        exit "$_outer_rc"
    fi
    unset _outer_rem
fi
mountpoint -q "$bootmnt" || exit 1
[ "$(cat "$bootmnt/KESTREL-LOG-TARGET" 2>/dev/null)" = KESTREL_A64_USB_CAPTURE_V1 ] || exit 1
name=${dev##*/}
case "$(readlink -f "/sys/class/block/$name")" in */usb[0-9]*/*) ;; *) exit 1 ;; esac
printf '%s\n' 'KESTREL_USERSPACE_LOGGER_STARTED' >>"$dest/00-status.txt"
sync -f "$dest/00-status.txt" 2>/dev/null || true
if [ "$HAVE_TIMEOUT" = 0 ]; then
    printf '%s\n' 'KESTREL_LOGGER_NO_TIMEOUT_FAIL_OPEN' >>"$dest/00-status.txt" 2>/dev/null || true
fi
if [ "$HAVE_PYTHON3" = 0 ]; then
    printf '%s\n' 'KESTREL_LOGGER_NO_PYTHON3_FAIL_OPEN' >>"$dest/00-status.txt" 2>/dev/null || true
fi
if [ "$graphics_requested" = 1 ] && [ "$logger_has_clock" = 0 ]; then
    printf '%s\n' 'KESTREL_LOGGER_NO_MONOTONIC_FAIL_OPEN' >>"$dest/00-status.txt" 2>/dev/null || true
    printf '%s\n' "KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED (graphics_requested=1 budget_s=$logger_budget_s text_samples=$total_samples iterations=0 clock=$logger_clock_src)" >>"$dest/00-status.txt"
    sync -f "$dest/00-status.txt" 2>/dev/null || true
    exit 0
fi
# Current monotonic seconds (BASH_MONOSECONDS else /proc/uptime int); empty when unavailable.
logger_now_s() {
    if [ "$logger_clock_src" = BASH_MONOSECONDS ]; then
        case "${BASH_MONOSECONDS-}" in ''|*[!0-9]*) printf ''; return 1 ;; *) printf '%s' "$BASH_MONOSECONDS"; return 0 ;; esac
    elif [ "$logger_clock_src" = proc-uptime ]; then
        # Builtin-only proc value: no fork/exec of cut on the per-op path.
        _now_first=''; _now_rest=''
        IFS=' ' read -r _now_first _now_rest < /proc/uptime 2>/dev/null || true
        _now_int=${_now_first%%.*}
        unset _now_first _now_rest
        case "$_now_int" in ''|*[!0-9]*) unset _now_int; printf ''; return 1 ;; *) printf '%s' "$_now_int"; _rc=0; unset _now_int; return $_rc ;; esac
    else
        printf ''; return 1
    fi
}
# Remaining allowance for graphics mode (floored at 0); 0 when clock unavailable.
logger_remaining_s() {
    if [ "$logger_has_clock" = 0 ]; then printf '0'; return 0; fi
    _now=$(logger_now_s 2>/dev/null || printf '')
    case "$_now" in ''|*[!0-9]*) unset _now; printf '0'; return 0 ;; esac
    _rem=$((logger_deadline - _now))
    unset _now
    case "$_rem" in ''|*[!0-9]*) _rem=0 ;; esac
    if [ "$_rem" -lt 0 ] 2>/dev/null; then _rem=0; fi
    printf '%s' "$_rem"
    return 0
}
# Timeout allowance for one external call: min(remaining, per_call_cap) in
# graphics mode (0 means exhausted: caller must skip), per_call_cap in text
# mode; always numeric.
logger_call_timeout_s() {
    t=$per_call_cap
    if [ "$graphics_requested" = 1 ]; then
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) rem=0 ;; esac
        if [ "$rem" -le 0 ] 2>/dev/null; then printf '0'; return 0; fi
        if [ "$rem" -lt "$t" ] 2>/dev/null; then t=$rem; fi
    fi
    if [ "$t" -lt 1 ] 2>/dev/null; then t=1; fi
    printf '%s' "$t"
    return 0
}
# Atomic last-good persist for the two whitelisted graphics JSON leaves only.
# Exact source names are enforced; symlinks, FIFOs, dirs and non-regular files
# are rejected without blocking; at most cap+1 bytes are EVER read from either
# side (single fd each, so growth after open is detected, not copied, and the
# destination compare never allocates huge memory); the payload must parse as
# complete standard JSON (NaN/Infinity rejected) and match the minimal leaf
# schema (preflight: passed bool + detail dict; status: reason string +
# bounded_cleanup bool; no duplication of hardware validation here).
# Valid-and-changed payloads are written via tempfile + checked file fsync +
# atomic replace + dir fsync; file-fsync failure preserves the old leaf.
# Anything else (missing/invalid/oversized/unchanged) keeps the previous good
# leaf with no sync churn. Every failure path returns 0: boot is never blocked.
persist_whitelisted_file() {
    src=$1
    leaf=$2
    cap=$3
    kind=''
    if [ "$leaf" = 08-graphics-preflight.json ] && [ "$src" = "$graphics_src_dir/preflight.json" ]; then
        kind=preflight
    elif [ "$leaf" = 09-graphics-status.json ] && [ "$src" = "$graphics_src_dir/status.json" ]; then
        kind=status
    else
        return 0
    fi
    case "$cap" in ''|*[!0-9]*) return 0 ;; esac
    _have_py=1
    if [ -n "${HAVE_PYTHON3-}" ]; then
        case "$HAVE_PYTHON3" in 0) _have_py=0 ;; *) _have_py=1 ;; esac
    else
        command -v python3 >/dev/null 2>&1 || _have_py=0
    fi
    if [ "$_have_py" = 0 ]; then return 0; fi
    _have_to=1
    if [ -n "${HAVE_TIMEOUT-}" ]; then
        case "$HAVE_TIMEOUT" in 0) _have_to=0 ;; *) _have_to=1 ;; esac
    else
        command -v timeout >/dev/null 2>&1 || _have_to=0
    fi
    _g_req=1
    if [ -n "${graphics_requested-}" ]; then
        case "$graphics_requested" in 1) _g_req=1 ;; *) _g_req=0 ;; esac
    fi
    _ka=${kill_after_s:-2}
    case "$_ka" in ''|*[!0-9]*) _ka=2 ;; esac
    # Fresh remaining before Python persist when helpers exist (new logger);
    # old extracted-function harness lacks logger_remaining_s and skips this.
    if [ "$_g_req" = 1 ] && command -v logger_remaining_s >/dev/null 2>&1; then
        _rem=$(logger_remaining_s 2>/dev/null || printf '0')
        case "$_rem" in ''|*[!0-9]*) return 0 ;; esac
        if [ "$_rem" -le 0 ] 2>/dev/null; then return 0; fi
        if command -v logger_call_timeout_s >/dev/null 2>&1; then
            _t=$(logger_call_timeout_s 2>/dev/null || printf '0')
            case "$_t" in ''|*[!0-9]*|0) return 0 ;; esac
        fi
        if [ "$_have_to" = 1 ]; then
            timeout -k "${_ka}s" "${_t}s" python3 - "$src" "$dest/$leaf" "$cap" "$kind" <<'PYEOF' 2>/dev/null || true
import os
import sys
import json
import stat
import tempfile
def _fail_open():
    return 0
def main():
    if len(sys.argv) != 5:
        return _fail_open()
    _, src, dst, cap_s, kind = sys.argv
    try:
        cap = int(cap_s)
    except (ValueError, TypeError):
        return _fail_open()
    if cap < 1 or cap > 131072:
        return _fail_open()
    if kind not in ("preflight", "status"):
        return _fail_open()
    try:
        fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return _fail_open()
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return _fail_open()
        need = cap + 1
        chunks = []
        got = 0
        while got < need:
            try:
                chunk = os.read(fd, min(8192, need - got))
            except OSError:
                return _fail_open()
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
        data = b"".join(chunks)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if not data or len(data) > cap:
        return _fail_open()
    try:
        text = data.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return _fail_open()
    try:
        def _reject_const(val):
            raise ValueError("non-standard JSON constant: %s" % val)
        obj = json.loads(text, parse_constant=_reject_const)
    except (ValueError, TypeError):
        return _fail_open()
    if not isinstance(obj, dict):
        return _fail_open()
    if kind == "preflight":
        if "passed" not in obj or type(obj["passed"]) is not bool:
            return _fail_open()
        if "detail" not in obj or not isinstance(obj["detail"], dict):
            return _fail_open()
    else:
        if "reason" not in obj or not isinstance(obj["reason"], str):
            return _fail_open()
        if "bounded_cleanup" not in obj or type(obj["bounded_cleanup"]) is not bool:
            return _fail_open()
    try:
        dfd = None
        try:
            dfd = os.open(dst, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            dfd = None
        except OSError:
            dfd = None
        if dfd is not None:
            try:
                dst_st = os.fstat(dfd)
                if stat.S_ISREG(dst_st.st_mode):
                    dneed = cap + 1
                    dchunks = []
                    dgot = 0
                    while dgot < dneed:
                        try:
                            dchunk = os.read(dfd, min(8192, dneed - dgot))
                        except OSError:
                            break
                        if not dchunk:
                            break
                        dchunks.append(dchunk)
                        dgot += len(dchunk)
                    ddata = b"".join(dchunks)
                    if ddata == data:
                        return _fail_open()
            finally:
                try:
                    os.close(dfd)
                except OSError:
                    pass
    except OSError:
        return _fail_open()
    dest_dir = os.path.dirname(os.path.abspath(dst))
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".graphics-", dir=dest_dir)
    except OSError:
        return _fail_open()
    try:
        try:
            with os.fdopen(tmp_fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return _fail_open()
        try:
            os.replace(tmp_path, dst)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return _fail_open()
        try:
            dir_fd = os.open(dest_dir, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return _fail_open()
        try:
            try:
                os.fsync(dir_fd)
            except OSError:
                pass
        finally:
            try:
                os.close(dir_fd)
            except OSError:
                pass
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return _fail_open()
    return _fail_open()
main()
PYEOF
            return 0
        fi
    fi
    # Fallback for old extracted-function harness (no logger_remaining_s) or
    # text mode: run the same secure persist without timeout wrapper. New
    # logger with timing helpers and missing timeout already returned above
    # (skip, never unbounded); this path is only for compat.
    if command -v logger_remaining_s >/dev/null 2>&1; then
        if [ "${_g_req}" = 1 ] && [ "${_have_to}" = 0 ]; then return 0; fi
    fi
    python3 - "$src" "$dest/$leaf" "$cap" "$kind" <<'PYEOF2' 2>/dev/null || true
import os
import sys
import json
import stat
import tempfile
def _fail_open():
    return 0
def main():
    if len(sys.argv) != 5:
        return _fail_open()
    _, src, dst, cap_s, kind = sys.argv
    try:
        cap = int(cap_s)
    except (ValueError, TypeError):
        return _fail_open()
    if cap < 1 or cap > 131072:
        return _fail_open()
    if kind not in ("preflight", "status"):
        return _fail_open()
    try:
        fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return _fail_open()
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return _fail_open()
        need = cap + 1
        chunks = []
        got = 0
        while got < need:
            try:
                chunk = os.read(fd, min(8192, need - got))
            except OSError:
                return _fail_open()
            if not chunk:
                break
            chunks.append(chunk)
            got += len(chunk)
        data = b"".join(chunks)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if not data or len(data) > cap:
        return _fail_open()
    try:
        text = data.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return _fail_open()
    def _reject_const2(val):
        raise ValueError("non-standard JSON constant: %s" % val)
    try:
        obj = json.loads(text, parse_constant=_reject_const2)
    except (ValueError, TypeError):
        return _fail_open()
    if not isinstance(obj, dict):
        return _fail_open()
    if kind == "preflight":
        if "passed" not in obj or type(obj["passed"]) is not bool:
            return _fail_open()
        if "detail" not in obj or not isinstance(obj["detail"], dict):
            return _fail_open()
    else:
        if "reason" not in obj or not isinstance(obj["reason"], str):
            return _fail_open()
        if "bounded_cleanup" not in obj or type(obj["bounded_cleanup"]) is not bool:
            return _fail_open()
    try:
        dfd = None
        try:
            dfd = os.open(dst, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            dfd = None
        except OSError:
            dfd = None
        if dfd is not None:
            try:
                dst_st = os.fstat(dfd)
                if stat.S_ISREG(dst_st.st_mode):
                    dneed = cap + 1
                    dchunks = []
                    dgot = 0
                    while dgot < dneed:
                        try:
                            dchunk = os.read(dfd, min(8192, dneed - dgot))
                        except OSError:
                            break
                        if not dchunk:
                            break
                        dchunks.append(dchunk)
                        dgot += len(dchunk)
                    ddata = b"".join(dchunks)
                    if ddata == data:
                        return _fail_open()
            finally:
                try:
                    os.close(dfd)
                except OSError:
                    pass
    except OSError:
        return _fail_open()
    dest_dir = os.path.dirname(os.path.abspath(dst))
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".graphics-", dir=dest_dir)
    except OSError:
        return _fail_open()
    try:
        try:
            with os.fdopen(tmp_fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return _fail_open()
        try:
            os.replace(tmp_path, dst)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return _fail_open()
        try:
            dir_fd = os.open(dest_dir, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return _fail_open()
        try:
            try:
                os.fsync(dir_fd)
            except OSError:
                pass
        finally:
            try:
                os.close(dir_fd)
            except OSError:
                pass
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return _fail_open()
    return _fail_open()
main()
PYEOF2
    return 0
}
persist_graphics_journal() {
    [ "$graphics_requested" = 1 ] || return 0
    _hto=1
    if [ -n "${HAVE_TIMEOUT-}" ]; then case "$HAVE_TIMEOUT" in 0) _hto=0 ;; *) _hto=1 ;; esac; else command -v timeout >/dev/null 2>&1 || _hto=0; fi
    if [ "$_hto" = 0 ]; then return 0; fi
    if [ "${logger_has_clock:-0}" = 0 ]; then return 0; fi
    if ! command -v logger_remaining_s >/dev/null 2>&1; then return 0; fi
    rem=$(logger_remaining_s)
    case "$rem" in ''|*[!0-9]*) return 0 ;; esac
    if [ "$rem" -le 0 ] 2>/dev/null; then return 0; fi
    if ! command -v logger_call_timeout_s >/dev/null 2>&1; then return 0; fi
    t=$(logger_call_timeout_s)
    case "$t" in ''|*[!0-9]*|0) return 0 ;; esac
    _ka2=${kill_after_s:-2}
    case "$_ka2" in ''|*[!0-9]*) _ka2=2 ;; esac
    tmp=$(mktemp "$dest/.graphics-journal-XXXXXX" 2>/dev/null) || return 0
    timeout -k "${_ka2}s" "${t}s" journalctl --boot --no-pager -u kestrel-graphics.service -n "$graphics_journal_lines" >"$tmp" 2>&1 || true
    size=$(wc -c <"$tmp" 2>/dev/null || printf '') || size=''
    case "$size" in ''|*[!0-9]*) rm -f -- "$tmp" 2>/dev/null || true; return 0 ;; esac
    if [ "$size" -gt 0 ] && [ "$size" -le "$graphics_journal_max" ]; then
        if [ -f "$dest/10-graphics-journal.log" ] && cmp -s -- "$tmp" "$dest/10-graphics-journal.log" 2>/dev/null; then
            rm -f -- "$tmp" 2>/dev/null || true; return 0
        fi
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) rm -f -- "$tmp" 2>/dev/null || true; return 0 ;; esac
        if [ "$rem" -le 0 ] 2>/dev/null; then rm -f -- "$tmp" 2>/dev/null || true; return 0; fi
        mv -f -- "$tmp" "$dest/10-graphics-journal.log" 2>/dev/null || { rm -f -- "$tmp" 2>/dev/null || true; return 0; }
        sync -f "$dest/10-graphics-journal.log" 2>/dev/null || true
    else
        rm -f -- "$tmp" 2>/dev/null || true
    fi
    return 0
}
count=0
while :; do
    if [ "$graphics_requested" = 1 ]; then
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) break ;; esac
        if [ "$rem" -le 0 ] 2>/dev/null; then break; fi
        if [ "$count" -ge "$logger_max_iter" ] 2>/dev/null; then break; fi
    else
        if [ "$count" -ge "$total_samples" ] 2>/dev/null; then break; fi
    fi
    # Bounded read-only log/status collection; never copy keys, shadow or env.
    # Atomic update: a crash/poweroff mid-write must keep the previous good
    # copy, never a truncated file. Unchanged outputs skip the rename and the
    # sync so idle iterations cause no storage churn. No bare `sync` here.
    t=$(logger_call_timeout_s)
    case "$t" in ''|*[!0-9]*) t=$per_call_cap ;; esac
    if [ "$graphics_requested" = 1 ]; then
        case "$t" in 0) break ;; esac
    fi
    if [ "$HAVE_TIMEOUT" = 1 ]; then
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) rem=0 ;; esac
        if [ "$graphics_requested" = 1 ] && [ "$rem" -le 0 ] 2>/dev/null; then break; fi
        t=$(logger_call_timeout_s)
        case "$t" in ''|*[!0-9]*|0)
            if [ "$graphics_requested" = 1 ]; then break; else t=$per_call_cap; fi
            ;;
        esac
        timeout -k "${kill_after_s}s" "${t}s" journalctl --boot --no-pager -n 2000 >"$dest/03-userspace-journal.tmp" 2>&1 || true
    else
        rm -f -- "$dest/03-userspace-journal.tmp" 2>/dev/null || true
    fi
    if [ -s "$dest/03-userspace-journal.tmp" ]; then
        if [ -f "$dest/03-userspace-journal.log" ] && cmp -s -- "$dest/03-userspace-journal.tmp" "$dest/03-userspace-journal.log" 2>/dev/null; then
            rm -f -- "$dest/03-userspace-journal.tmp" 2>/dev/null || true
        else
            if [ "$graphics_requested" = 1 ]; then
                rem=$(logger_remaining_s)
                case "$rem" in ''|*[!0-9]*) rm -f -- "$dest/03-userspace-journal.tmp" 2>/dev/null || true; break ;; esac
                if [ "$rem" -le 0 ] 2>/dev/null; then rm -f -- "$dest/03-userspace-journal.tmp" 2>/dev/null || true; break; fi
            fi
            mv -f "$dest/03-userspace-journal.tmp" "$dest/03-userspace-journal.log" 2>/dev/null || rm -f -- "$dest/03-userspace-journal.tmp" 2>/dev/null || true
            sync -f "$dest/03-userspace-journal.log" 2>/dev/null || true
        fi
    fi
    {
        echo "sample=$count"
        cat /proc/uptime
        if [ "$HAVE_TIMEOUT" = 1 ]; then
            if [ "$graphics_requested" = 1 ]; then
                rem=$(logger_remaining_s)
                case "$rem" in ''|*[!0-9]*) rem=0 ;; esac
                if [ "$rem" -le 0 ] 2>/dev/null; then echo "systemctl skipped (budget exhausted)"; else
                    t2=$(logger_call_timeout_s)
                    case "$t2" in ''|*[!0-9]*|0) echo "systemctl skipped (budget exhausted)" ;; *) timeout -k "${kill_after_s}s" "${t2}s" systemctl is-system-running 2>/dev/null || true ;; esac
                fi
            else
                timeout -k "${kill_after_s}s" "${t}s" systemctl is-system-running 2>/dev/null || true
            fi
        else
            echo "systemctl skipped (no timeout)"
        fi
        for z in /sys/class/thermal/thermal_zone*; do
            [ -r "$z/temp" ] || continue
            printf '%s ' "$z"
            cat "$z/type" "$z/temp" 2>/dev/null
        done
    } >>"$dest/04-userspace-status.txt"
    if [ "$graphics_requested" = 1 ]; then
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) break ;; esac
        if [ "$rem" -le 0 ] 2>/dev/null; then break; fi
    fi
    sync -f "$dest/04-userspace-status.txt" 2>/dev/null || true
    if [ -r /run/initramfs/init.log ]; then
        if [ "$graphics_requested" = 1 ]; then
            rem=$(logger_remaining_s)
            case "$rem" in ''|*[!0-9]*) rem=0 ;; esac
            if [ "$rem" -le 0 ] 2>/dev/null; then :; else
                cp /run/initramfs/init.log "$dest/02-initramfs-console.tmp" 2>/dev/null || true
                if [ -s "$dest/02-initramfs-console.tmp" ]; then
                    if [ -f "$dest/02-initramfs-console.log" ] && cmp -s -- "$dest/02-initramfs-console.tmp" "$dest/02-initramfs-console.log" 2>/dev/null; then
                        rm -f -- "$dest/02-initramfs-console.tmp" 2>/dev/null || true
                    else
                        mv -f "$dest/02-initramfs-console.tmp" "$dest/02-initramfs-console.log" 2>/dev/null || rm -f -- "$dest/02-initramfs-console.tmp" 2>/dev/null || true
                        sync -f "$dest/02-initramfs-console.log" 2>/dev/null || true
                    fi
                fi
            fi
        else
            cp /run/initramfs/init.log "$dest/02-initramfs-console.tmp" 2>/dev/null || true
            if [ -s "$dest/02-initramfs-console.tmp" ]; then
                if [ -f "$dest/02-initramfs-console.log" ] && cmp -s -- "$dest/02-initramfs-console.tmp" "$dest/02-initramfs-console.log" 2>/dev/null; then
                    rm -f -- "$dest/02-initramfs-console.tmp" 2>/dev/null || true
                else
                    mv -f "$dest/02-initramfs-console.tmp" "$dest/02-initramfs-console.log" 2>/dev/null || rm -f -- "$dest/02-initramfs-console.tmp" 2>/dev/null || true
                    sync -f "$dest/02-initramfs-console.log" 2>/dev/null || true
                fi
            fi
        fi
    fi
    # Whitelisted graphics outcome only: exact preflight.json + status.json
    # plus bounded diagnostic-unit journal. Never env/secret dumps. Fail-open.
    if [ "$graphics_requested" = 1 ]; then
        persist_whitelisted_file "$graphics_src_dir/preflight.json" 08-graphics-preflight.json "$graphics_json_max" || true
        persist_whitelisted_file "$graphics_src_dir/status.json" 09-graphics-status.json "$graphics_json_max" || true
        persist_graphics_journal || true
    fi
    count=$((count + 1))
    if [ "$graphics_requested" = 1 ]; then
        rem=$(logger_remaining_s)
        case "$rem" in ''|*[!0-9]*) break ;; esac
        if [ "$rem" -le 0 ] 2>/dev/null; then break; fi
        sleep 1 2>/dev/null || true
    else
        sleep 1
    fi
done
printf '%s\n' "KESTREL_USERSPACE_CAPTURE_WINDOW_FINISHED (graphics_requested=$graphics_requested budget_s=$logger_budget_s text_samples=$total_samples iterations=$count clock=$logger_clock_src)" >>"$dest/00-status.txt"
sync -f "$dest/00-status.txt" 2>/dev/null || true
exit 0
