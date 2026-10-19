#!/usr/bin/env python3
"""Bounded simpledrm/software-Plasma diagnostic supervisor (fail-closed).

Opt-in only via kestrel_graphics=1 staging. Never blocks normal boot:
all preflight/session failures log KESTREL_GRAPHICS_* and exit 0 after
bounded owned-only cleanup. No account/password edits, no firmware/USB writes,
no reboot/poweroff, no thermal/fan/voltage/clock/EFI changes.
A passed preflight is not proof that Plasma renders; an active
logind session is not proof of pixels or real input.

Real logind session schema (systemd 262 primary source + genuine
`loginctl show-session` output, builder systemd 262-1-arch):
- `User` is numeric UID text (e.g. `User=1001`), printed from the `(uo)`
  struct in loginctl.c; `Name` is the username string (e.g. `Name=builder`)
  from logind-session-dbus.c `property_get_name`. There is NO `UID`
  session property (requesting `-p UID` yields empty output).
- `loginctl show-session` requires repeated `-p` flags; a single
  comma-joined `-p "Id,User,..."` yields empty output with rc=0 on real
  logind. The supervisor therefore uses repeated `-p` flags.
- `Display` is the X11 display string and is normally empty for Wayland
  (and for tty/manager) sessions; Wayland ownership must NOT require a
  nonempty Display.
- Session discovery is fail-closed: unreadable listing/baseline/detail
  refuses before any owned GUI start, never assumes no foreign session.

Ownership contract (strict):
- Only the private kestrel-graphics-sddm.service unit is ever started,
  stopped, or killed. Stock display-manager/sddm are masked and never touched.
- Only the exact newly owned session (live UID 1000, seat0, Wayland,
  SDDM/PAM service, active) is ever terminated. No broad live-user kill,
  no process-name kill. Existing unrelated sessions cause refusal without
  termination.
- One absolute cleanup budget fits TimeoutStopSec=30. Success is claimed
  only after read-back verification of owned shutdown + tty2 restore.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

MAX_SECONDS = 180
STOP_MC = 80000
MINIMUM_MC = 5000
CARD_DEFAULT = "card0"

SESSION_WAIT_S = 30
START_WAIT_S = 30
POLL_S = 2
SESSION_POLL_S = 1
START_POLL_S = 1

CLEANUP_BUDGET_S = 25
PER_CMD_TIMEOUT_S = 5
VERIFY_TIMEOUT_S = 3

OWNED_UNIT = "kestrel-graphics-sddm.service"
TTY2_UNIT = "getty@tty2.service"
LIVE_USER = "live"
LIVE_UID = 1000

_STATUS_DIR_DEFAULT = Path("/run/kestrel-graphics")
_POLICY_DEFAULT = Path("/etc/kestrel-graphics-policy.json")

_cleanup_state = {
    "runner": None,
    "status_dir": None,
    "owned_session": None,
    "pending_signal": None,
    "cleaning": False,
    "reason": "signal",
}

_PREFLIGHT_MAX_BYTES = 64 * 1024

# Required non-empty detail keys for a trustworthy discovery read.
# Seat/Display/TTY/Service are intentionally NOT required non-empty:
# genuine non-GUI (tty/manager) and Wayland sessions may legitimately
# report them empty (Display is X11-only), and older fakes may omit TTY.
# Id/User/Name/Type/Class/State/Remote must all be present and non-empty,
# and Id must equal the requested session id.
_REQUIRED_DETAIL_NONEMPTY = ("Id", "User", "Name", "Type", "Class", "State", "Remote")


def _atomic_write_json(path, payload):
    """Atomically write JSON dict to path, capped at 64KiB.

    Uses tmp-file + os.replace in the same directory so an interrupted
    write leaves the last-good file intact. Returns True on success,
    False when oversized or on any IO/serialization error (last-good
    preserved, never a partial file).
    """
    try:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError):
        return False
    if len(data) > _PREFLIGHT_MAX_BYTES:
        return False
    try:
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)
        import tempfile as _tf
        fd, tmpname = _tf.mkstemp(dir=str(parent), prefix=".tmp-preflight-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                # File-data fsync errors are real persistence failures and
                # must never be swallowed: any OSError skips os.replace
                # below, cleans up the tmp file, and returns False so the
                # caller fails closed with the last-good file intact.
                os.fsync(fh.fileno())
            os.replace(tmpname, str(path))
            # Directory durability where meaningful: persist the rename
            # itself. Best-effort only: a directory that cannot be fsynced
            # must not turn an otherwise durable file write into a failure.
            try:
                _dirfd = os.open(str(parent), os.O_RDONLY)
            except OSError:
                _dirfd = None
            if _dirfd is not None:
                try:
                    os.fsync(_dirfd)
                except OSError:
                    pass
                finally:
                    os.close(_dirfd)
        finally:
            try:
                if os.path.exists(tmpname):
                    os.unlink(tmpname)
            except OSError:
                pass
        return True
    except (OSError, ValueError, TypeError):
        return False


def _save_preflight_result(status_dir, *, passed, reason, detail=None,
                           thermal=None, drm=None, drm_snapshot=None):
    """Persist structured preflight.json atomically. Returns True if saved.

    Payload is always a dict: bool passed, structured reason/detail
    including the actual thermal result and DRM snapshot, plus
    native_graphics_validated=False. Never substitutes str(detail)
    truncation. On oversize (>64KiB) writes a concise refusal instead
    and returns False so callers fail closed. On IO failure the
    last-good file is preserved (atomic replace) and False is returned.
    """
    try:
        if isinstance(detail, dict):
            detail_struct = detail
        elif detail is None:
            detail_struct = {}
        else:
            detail_struct = {"note": str(detail)[:500]}
        payload = {
            "passed": bool(passed),
            "reason": str(reason)[:200],
            "detail": detail_struct,
            "thermal": thermal,
            "drm": drm,
            "drm_snapshot": drm_snapshot,
            "native_graphics_validated": False,
        }
        try:
            raw_len = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
        except (TypeError, ValueError):
            raw_len = _PREFLIGHT_MAX_BYTES + 1
        if raw_len > _PREFLIGHT_MAX_BYTES:
            refusal = {
                "passed": False,
                "reason": "preflight-snapshot-too-large",
                "detail": {"error": "snapshot-exceeds-64kib",
                           "reason": str(reason)[:200]},
                "thermal": None,
                "drm": None,
                "drm_snapshot": None,
                "native_graphics_validated": False,
            }
            try:
                _atomic_write_json(Path(status_dir) / "preflight.json", refusal)
            except Exception:
                pass
            return False
        return bool(_atomic_write_json(Path(status_dir) / "preflight.json", payload))
    except Exception:
        return False


def _log(msg: str) -> None:
    text = msg.strip().splitlines()[0][:300] if msg.strip() else "EMPTY"
    print(f"KESTREL_GRAPHICS_{text}", flush=True)


def load_policy(path: Path):
    """Load required_sensor_types; fail closed on missing/invalid/battery."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError, UnicodeError):
        return False, {"error": "missing_or_invalid_policy"}
    types = data.get("required_sensor_types")
    if not isinstance(types, list) or not types:
        return False, {"error": "empty_or_invalid_required_sensor_policy"}
    cleaned = []
    for entry in types:
        if not isinstance(entry, str) or not entry:
            return False, {"error": "empty_or_invalid_required_sensor_policy"}
        if "batt" in entry.lower():
            return False, {"error": "battery_is_not_soc_temperature"}
        cleaned.append(entry)
    if len(set(cleaned)) != len(cleaned):
        return False, {"error": "duplicate_sensor_policy"}
    return True, set(cleaned)


def preflight(thermal_root, drm_root, device_root, card, required, guard):
    """Read-only DRM + SoC temperature checks; fail closed on any error."""
    try:
        rows = guard.collect_temperatures(thermal_root, required)
        thermal = guard.evaluate_temperatures(rows, required,
                                              minimum_mc=MINIMUM_MC, stop_mc=STOP_MC)
    except Exception as exc:  # noqa: BLE001 - fail closed
        return False, {"error": f"temperature_collection_failed:{type(exc).__name__}"}
    try:
        snapshot = guard.collect_drm(drm_root, device_root, card)
        drm = guard.evaluate_drm(snapshot)
    except Exception as exc:  # noqa: BLE001 - fail closed
        return False, {"error": f"drm_collection_failed:{type(exc).__name__}"}
    ok = bool(thermal.get("ok")) and bool(drm.get("ok"))
    return ok, {"thermal": thermal, "drm": drm, "drm_snapshot": snapshot}


def _run_checked(runner, cmd, timeout):
    try:
        result = runner(cmd, timeout=timeout)
        code = int(getattr(result, "returncode", 1))
        return code == 0
    except Exception:
        return False


def _parse_kv_lines(out: str):
    data = {}
    for line in (out or "").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip()
    return data


_SESSION_PROPS = ("Id", "User", "Name", "Seat", "Type", "Class",
                   "State", "Display", "Remote", "Service", "TTY")


def _session_prop_args():
    args = []
    for prop in _SESSION_PROPS:
        args += ["-p", prop]
    return args


def list_sessions(runner, timeout=5):
    """Return set of session IDs seen via loginctl, or None on any error.

    Fail-closed: callers must refuse before any owned GUI start when this
    returns None, never assume an empty set means no foreign session.
    """
    try:
        result = runner(["loginctl", "list-sessions", "--no-legend", "--no-pager"],
                        timeout=timeout)
        if int(getattr(result, "returncode", 1)) != 0:
            return None
        out = str(getattr(result, "stdout", "") or "")
        sids = set()
        for line in out.splitlines():
            parts = line.split()
            if parts:
                sids.add(parts[0].strip())
        return {s for s in sids if s}
    except Exception:
        return None


def get_session_detail(runner, sid, timeout=5):
    """Return dict of loginctl show-session properties, or None on error.

    Uses repeated `-p` flags (genuine logind 262 requires them; a single
    comma-joined `-p` yields empty output). Requests real properties
    Id,User(numeric),Name,Seat,Type,Class,State,Display,Remote,Service,TTY.
    There is no UID session property. Returns None when the session is
    unreadable/missing/empty/partial/inconsistent so callers refuse
    fail-closed instead of skipping: rc0 empty stdout, any missing
    required Id/User/Name/Type/Class/State/Remote, any empty required
    value, or Id mismatch with the requested sid all yield None.
    Seat/Display/Service/TTY may legitimately be empty (Wayland Display
    is X11-only; non-seat sessions have empty Seat) and do not
    invalidate the read.
    """
    try:
        result = runner(["loginctl", "show-session", str(sid)] + _session_prop_args(),
                        timeout=timeout)
        if int(getattr(result, "returncode", 1)) != 0:
            return None
        raw = str(getattr(result, "stdout", "") or "")
        if not raw.strip():
            # rc0 but empty (e.g. comma-joined -p pitfall): unknown, refuse.
            return None
        data = _parse_kv_lines(raw)
        if not data:
            return None
        want = str(sid).strip()
        if not want or str(data.get("Id", "") or "").strip() != want:
            return None
        for key in _REQUIRED_DETAIL_NONEMPTY:
            val = data.get(key)
            if val is None or not str(val).strip():
                return None
        return data
    except Exception:
        return None


def is_owned_session_detail(detail, baseline):
    """Strict owned-session predicate: newly owned live seat0 Wayland SDDM.

    Real-schema identity (systemd 262): numeric User==1000 AND Name==live,
    new (not in baseline), seat0, Type wayland, Class user, State active,
    SDDM Service prefix, explicit non-remote (Remote must be no/false;
    missing or empty Remote is rejected, never defaulted to local).
    Display is NOT required: genuine
    Wayland (and tty/manager) sessions normally have an empty Display
    (X11-only property), verified on builder logind 262 output.
    Missing User/Name or any mismatch returns False (never claim foreign).
    A None/unreadable detail never reaches here; discovery callers refuse
    fail-closed on None before consulting this predicate.
    """
    try:
        if detail is None:
            return False
        sid = str(detail.get("Id", "") or "")
        if not sid or sid in baseline:
            return False
        # Real schema: User is numeric UID text, Name is username.
        try:
            uid = int(str(detail.get("User", "")).strip())
        except (ValueError, TypeError):
            return False
        if uid != LIVE_UID or uid == 0:
            return False
        if str(detail.get("Name", "") or "") != LIVE_USER:
            return False
        if str(detail.get("Seat", "")) != "seat0":
            return False
        if str(detail.get("Type", "")) != "wayland":
            return False
        if str(detail.get("Class", "")) != "user":
            return False
        if str(detail.get("State", "")) != "active":
            return False
        svc = str(detail.get("Service", "") or "")
        if not svc.startswith("sddm"):
            return False
        remote_raw = detail.get("Remote")
        if remote_raw is None:
            return False
        if str(remote_raw).strip().lower() not in ("no", "false"):
            return False
        # Display intentionally unchecked: empty is normal for Wayland.
        return True
    except Exception:
        return False


def existing_gui_present(runner, timeout=5):
    """True if any active Class=user graphical session already exists.

    Used before owning a GUI: if True the supervisor must refuse without
    terminating anything. Fail-closed: unreadable listing or any unreadable
    session detail returns True (assume present), never False.
    """
    try:
        sids = list_sessions(runner, timeout=timeout)
        if sids is None:
            # Unknown listing: refuse rather than assume no foreign session.
            return True
        for sid in sids:
            d = get_session_detail(runner, sid, timeout=timeout)
            if d is None:
                # Unknown detail: refuse rather than skip a foreign session.
                return True
            if not d:
                # Empty dict must never be skipped: unknown, refuse.
                return True
            want_sid = str(sid).strip()
            if str(d.get("Id", "") or "").strip() != want_sid:
                return True
            for _k in _REQUIRED_DETAIL_NONEMPTY:
                _v = d.get(_k)
                if _v is None or not str(_v).strip():
                    return True
            if d.get("Class") == "user" and d.get("State") == "active":
                typ = d.get("Type", "")
                if typ in ("wayland", "x11", "mir"):
                    return True
                # Any active user session for live blocks owned start.
                if d.get("Name") == LIVE_USER:
                    return True
                try:
                    if int(str(d.get("User", "")).strip()) == LIVE_UID:
                        return True
                except (ValueError, TypeError):
                    return True
        return False
    except Exception:
        # Fail closed: assume present on collection error.
        return True


def _check_signalled(monotonic=None):
    return _cleanup_state.get("pending_signal") is not None


def start_owned_gui(*, runner, status_dir, thermal_root, drm_root, device_root,
                    card, required, guard, baseline, overall_deadline,
                    timeout_s=START_WAIT_S, _monotonic=None, _sleep=None):
    """Start private unit with temp/DRM polling throughout. Returns (ok, reason)."""
    mono = _monotonic or time.monotonic
    slp = _sleep or time.sleep
    start = mono()
    startup_deadline = min(start + max(1, timeout_s), overall_deadline)
    # Baseline already captured by caller; re-verify no foreign GUI.
    if existing_gui_present(runner):
        return False, "existing-session"
    # Guarded launch marker for ConditionPathExists in the private unit.
    try:
        Path(status_dir).mkdir(parents=True, exist_ok=True)
        (Path(status_dir) / "launch-allowed").write_text("allowed\n")
    except (OSError, ValueError):
        return False, "marker-fail"
    if _check_signalled():
        return False, "signal-before-start"
    # Initial gate already passed by caller; re-check once before start.
    ok, _ = preflight(thermal_root, drm_root, device_root, card, required, guard)
    if not ok:
        return False, "preflight-fail"
    if _check_signalled():
        return False, "signal-before-start"
    # Async start: --no-block then poll ActiveState + temps (no 30s block).
    try:
        runner(["systemctl", "start", "--no-block", OWNED_UNIT],
               timeout=PER_CMD_TIMEOUT_S)
    except Exception:
        return False, "start-fail"
    while mono() < startup_deadline:
        if _check_signalled():
            return False, "signal-during-start"
        # Thermal/DRM observation during startup (fail-closed).
        try:
            ok, _ = preflight(thermal_root, drm_root, device_root, card, required, guard)
            if not ok:
                return False, "temp-fail-during-start"
        except Exception:
            return False, "temp-fail-during-start"
        try:
            result = runner(["systemctl", "show", OWNED_UNIT,
                             "-p", "ActiveState,SubState,Result"],
                            timeout=VERIFY_TIMEOUT_S)
            out = str(getattr(result, "stdout", "") or "")
            kv = _parse_kv_lines(out)
            if kv.get("ActiveState") == "active":
                return True, "started"
            if kv.get("ActiveState") == "failed":
                return False, "start-fail"
        except Exception:
            pass
        if mono() >= startup_deadline:
            break
        slp(min(START_POLL_S, max(0.05, startup_deadline - mono())))
    return False, "start-timeout"


def wait_for_owned_session(*, runner, baseline, thermal_root, drm_root,
                           device_root, card, required, guard,
                           overall_deadline, timeout_s=SESSION_WAIT_S,
                           _monotonic=None, _sleep=None):
    """Wait for exact newly owned active seat0 Wayland SDDM session.

    Polls temps/DRM each sample; hot/loss aborts. Returns sid or None.
    Fail-closed: unreadable listing or any unreadable non-baseline detail
    returns None (unknown identity refuses) instead of skipping.
    """
    mono = _monotonic or time.monotonic
    slp = _sleep or time.sleep
    deadline = min(mono() + max(0.5, timeout_s), overall_deadline)
    while mono() < deadline:
        if _check_signalled():
            return None
        try:
            ok, _ = preflight(thermal_root, drm_root, device_root, card, required, guard)
            if not ok:
                return None
        except Exception:
            return None
        try:
            sids = list_sessions(runner, timeout=VERIFY_TIMEOUT_S)
        except Exception:
            return None
        if sids is None:
            return None
        try:
            for sid in sids:
                if sid in baseline:
                    continue
                d = get_session_detail(runner, sid, timeout=VERIFY_TIMEOUT_S)
                if d is None:
                    # Unknown identity for a new session: refuse fail-closed.
                    return None
                if d and is_owned_session_detail(d, baseline):
                    return sid
        except Exception:
            return None
        if mono() >= deadline:
            break
        slp(min(SESSION_POLL_S, max(0.05, deadline - mono())))
    return None


def bounded_cleanup(runner, status_dir, reason="unknown", owned=None,
                    _monotonic=None, _sleep=None,
                    budget_s=CLEANUP_BUDGET_S):
    """Stop ONLY owned unit/session; verify; restore tty2. Fits 30s stop budget."""
    mono = _monotonic or time.monotonic
    slp = _sleep or time.sleep
    _log(f"CLEANUP_{reason}"[:300])
    start = mono()
    deadline = start + max(5, budget_s)
    steps = []

    def remaining():
        return max(0.0, deadline - mono())

    def run_rec(cmd, timeout):
        nonlocal steps
        tout = min(timeout, max(0.5, remaining()))
        if remaining() <= 0:
            steps.append({"cmd": list(cmd), "ok": False, "note": "budget-exhausted"})
            return False
        try:
            result = runner(list(cmd), timeout=tout)
            code = int(getattr(result, "returncode", 1))
            ok = code == 0
            steps.append({"cmd": list(cmd), "ok": ok, "code": code})
            return ok
        except Exception as exc:
            steps.append({"cmd": list(cmd), "ok": False,
                          "error": str(type(exc).__name__)[:80]})
            return False

    # 1. Stop owned diagnostic unit only (never stock display-manager/sddm,
    #    never broad user kill, never process-name kill).
    run_rec(["systemctl", "stop", OWNED_UNIT], PER_CMD_TIMEOUT_S)
    # Verify owned unit stopped; escalate narrowly via owned unit/cgroup.
    owned_stopped = False
    try:
        result = runner(["systemctl", "is-active", OWNED_UNIT],
                        timeout=min(VERIFY_TIMEOUT_S, max(0.5, remaining())))
        out = str(getattr(result, "stdout", "") or "").strip().lower()
        code = int(getattr(result, "returncode", 1))
        # is-active returns 0 only when active; non-zero means inactive/unknown.
        owned_stopped = (code != 0 and out in ("inactive", "unknown", "failed", ""))
        if not owned_stopped and out not in ("inactive", "unknown", "failed", ""):
            owned_stopped = False
        steps.append({"cmd": ["systemctl", "is-active", OWNED_UNIT],
                      "ok": owned_stopped, "code": code, "state": out[:40]})
    except Exception as exc:
        steps.append({"cmd": ["systemctl", "is-active", OWNED_UNIT],
                      "ok": False, "error": str(type(exc).__name__)[:80]})
    if not owned_stopped and remaining() > 3:
        run_rec(["systemctl", "kill", "--signal=SIGKILL", OWNED_UNIT],
                PER_CMD_TIMEOUT_S)
        try:
            result = runner(["systemctl", "is-active", OWNED_UNIT],
                            timeout=min(VERIFY_TIMEOUT_S, max(0.5, remaining())))
            out = str(getattr(result, "stdout", "") or "").strip().lower()
            code = int(getattr(result, "returncode", 1))
            owned_stopped = (code != 0 and out in ("inactive", "unknown", "failed", ""))
            steps.append({"cmd": ["systemctl", "is-active", OWNED_UNIT, "retry"],
                          "ok": owned_stopped, "code": code, "state": out[:40]})
        except Exception as exc:
            steps.append({"cmd": ["systemctl", "is-active", OWNED_UNIT, "retry"],
                          "ok": False, "error": str(type(exc).__name__)[:80]})

    # 2. Terminate ONLY the owned session (never terminate user, never global).
    owned_gone = True
    if owned:
        run_rec(["loginctl", "terminate-session", str(owned)], PER_CMD_TIMEOUT_S)
        try:
            result = runner(["loginctl", "show-session", str(owned)],
                            timeout=min(VERIFY_TIMEOUT_S, max(0.5, remaining())))
            code = int(getattr(result, "returncode", 1))
            owned_gone = code != 0
            steps.append({"cmd": ["loginctl", "show-session", str(owned)],
                          "ok": owned_gone, "code": code})
        except Exception as exc:
            steps.append({"cmd": ["loginctl", "show-session", str(owned)],
                          "ok": False, "error": str(type(exc).__name__)[:80]})
            owned_gone = False
        if not owned_gone and remaining() > 3:
            run_rec(["loginctl", "kill-session", str(owned), "-s", "SIGKILL"],
                    PER_CMD_TIMEOUT_S)
            try:
                result = runner(["loginctl", "show-session", str(owned)],
                                timeout=min(VERIFY_TIMEOUT_S, max(0.5, remaining())))
                code = int(getattr(result, "returncode", 1))
                owned_gone = code != 0
                steps.append({"cmd": ["loginctl", "show-session", str(owned), "retry"],
                              "ok": owned_gone, "code": code})
            except Exception as exc:
                steps.append({"cmd": ["loginctl", "show-session", str(owned), "retry"],
                              "ok": False, "error": str(type(exc).__name__)[:80]})
    else:
        owned_gone = True

    # 3. Remove launch marker so the private unit cannot restart.
    try:
        (Path(status_dir) / "launch-allowed").unlink(missing_ok=True)
    except (OSError, ValueError, TypeError):
        try:
            p = Path(status_dir) / "launch-allowed"
            if p.exists():
                p.unlink()
        except (OSError, ValueError):
            pass

    # 4. Restore/activate local text access on tty2 (safe, bounded).
    # No chvt VT switch: kbd/chvt presence in the live image is unverified
    # (present on builder via kbd 2.10.0-1, no live-rootfs reference found),
    # and a switch must never target a foreign/unknown session nor exceed
    # the 25s cleanup budget. An active getty is not proof of a visible VT.
    tty_ok = run_rec(["systemctl", "start", TTY2_UNIT], PER_CMD_TIMEOUT_S)
    try:
        result = runner(["systemctl", "is-active", TTY2_UNIT],
                        timeout=min(VERIFY_TIMEOUT_S, max(0.5, remaining())))
        code = int(getattr(result, "returncode", 1))
        out = str(getattr(result, "stdout", "") or "").strip().lower()
        tty_active = code == 0 and out == "active"
        steps.append({"cmd": ["systemctl", "is-active", TTY2_UNIT],
                      "ok": tty_active, "code": code, "state": out[:40]})
    except Exception as exc:
        tty_active = False
        steps.append({"cmd": ["systemctl", "is-active", TTY2_UNIT],
                      "ok": False, "error": str(type(exc).__name__)[:80]})
    # tty restore is best-effort but required for full success.
    complete = bool(owned_stopped and owned_gone and tty_active and remaining() > 0)
    # 5. Bounded status to /run only (no USB/firmware writes).
    try:
        Path(status_dir).mkdir(parents=True, exist_ok=True)
        payload = {"reason": str(reason)[:100], "bounded_cleanup": bool(complete),
                   "owned_unit": OWNED_UNIT, "owned_session": str(owned) if owned else None,
                   "owned_stopped": bool(owned_stopped), "owned_gone": bool(owned_gone),
                   "tty2_restored": bool(tty_active),
                   "steps": steps[-12:],
                   "restart_text": TTY2_UNIT,
                   "native_graphics_validated": False,
                   "session_active_is_not_pixel_proof": True}
        (Path(status_dir) / "status.json").write_text(json.dumps(payload, sort_keys=True))
    except (OSError, ValueError):
        complete = False
    if complete:
        _log(f"CLEANUP_DONE_{reason}"[:300])
        return 0
    _log(f"CLEANUP_INCOMPLETE_{reason}"[:300])
    return 1


def _handle_signal(signum, frame):
    # Idempotent: record only, never nested cleanup inside the handler.
    # Main loops observe pending_signal and perform a single bounded cleanup.
    try:
        if _cleanup_state.get("cleaning"):
            _log(f"SIGNAL_{signum}_IGNORED_CLEANING")
            return
        if _cleanup_state.get("pending_signal") is None:
            _cleanup_state["pending_signal"] = signum
        _log(f"SIGNAL_{signum}")
    except Exception:
        pass


def run_bounded_session(*, thermal_root, drm_root, device_root, card,
                        required, guard, runner, status_dir,
                        timeout_s=MAX_SECONDS, poll_s=POLL_S,
                        session_wait_s=SESSION_WAIT_S,
                        start_wait_s=START_WAIT_S,
                        _monotonic=None, _sleep=None):
    """Single bounded attempt; no auto fallback/retry loops. Fixed 180s budget."""
    mono = _monotonic or time.monotonic
    slp = _sleep or time.sleep
    timeout_s = min(int(timeout_s), MAX_SECONDS) if int(timeout_s) > 0 else MAX_SECONDS
    session_wait_s = min(int(session_wait_s), SESSION_WAIT_S) if int(session_wait_s) > 0 else SESSION_WAIT_S
    start_wait_s = min(int(start_wait_s), START_WAIT_S) if int(start_wait_s) > 0 else START_WAIT_S
    poll_s = min(float(poll_s), float(POLL_S)) if float(poll_s) > 0 else POLL_S
    start = mono()
    deadline = start + timeout_s
    _cleanup_state["pending_signal"] = None
    _cleanup_state["cleaning"] = False

    def signalled():
        return _cleanup_state.get("pending_signal") is not None

    # Baseline sessions before owning anything. Fail-closed: unreadable
    # baseline refuses before any owned GUI start, never empty-assumes.
    try:
        baseline_raw = list_sessions(runner)
    except Exception:
        baseline_raw = None
    if baseline_raw is None:
        _log("REFUSE_UNKNOWN_BASELINE")
        _save_preflight_result(status_dir, passed=False,
                               reason="unknown-baseline-refused-no-termination",
                               detail={"error": "unknown-baseline-refused-no-termination"})
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="unknown-baseline-refused",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2
    baseline = set(baseline_raw)
    if signalled():
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason=f"signal-{_cleanup_state.get('pending_signal')}",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2
    # Refuse if an unrelated GUI/live session already exists (no termination).
    try:
        if existing_gui_present(runner):
            _log("REFUSE_EXISTING_SESSION")
            _save_preflight_result(status_dir, passed=False,
                                   reason="existing-session-refused-no-termination",
                                   detail={"error": "existing-session-refused-no-termination"})
            # No owned GUI: cleanup only ensures tty2, never touches foreign.
            _cleanup_state["cleaning"] = True
            bounded_cleanup(runner, status_dir, reason="existing-session-refused",
                            owned=None, _monotonic=mono, _sleep=slp)
            _cleanup_state["cleaning"] = False
            return 2
    except Exception:
        _save_preflight_result(status_dir, passed=False,
                               reason="existing-session-unknown-refused",
                               detail={"error": "existing-session-unknown-refused"})
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="preflight-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    ok, detail = preflight(thermal_root, drm_root, device_root, card, required, guard)
    if not ok:
        _log("PREFLIGHT_FAIL")
        _thermal = detail.get("thermal") if isinstance(detail, dict) else None
        _drm = detail.get("drm") if isinstance(detail, dict) else None
        _snap = detail.get("drm_snapshot") if isinstance(detail, dict) else None
        _save_preflight_result(status_dir, passed=False, reason="preflight-fail",
                               detail=detail if isinstance(detail, dict) else {"error": "preflight-fail"},
                               thermal=_thermal, drm=_drm, drm_snapshot=_snap)
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="preflight-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    # Durable structured pass snapshot BEFORE any launch marker or private
    # SDDM start. If it cannot be persisted, fail closed with no GUI start.
    _thermal = detail.get("thermal") if isinstance(detail, dict) else None
    _drm = detail.get("drm") if isinstance(detail, dict) else None
    _snap = detail.get("drm_snapshot") if isinstance(detail, dict) else None
    if not _save_preflight_result(status_dir, passed=True, reason="preflight-pass",
                                  detail=detail if isinstance(detail, dict) else {},
                                  thermal=_thermal, drm=_drm, drm_snapshot=_snap):
        _log("PREFLIGHT_SAVE_FAIL")
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="preflight-save-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    _log("PREFLIGHT_PASS_STARTING_SDDM")
    try:
        started, why = start_owned_gui(
            runner=runner, status_dir=status_dir,
            thermal_root=thermal_root, drm_root=drm_root, device_root=device_root,
            card=card, required=required, guard=guard, baseline=baseline,
            overall_deadline=deadline, timeout_s=start_wait_s,
            _monotonic=mono, _sleep=slp)
    except Exception as exc:
        _log(f"START_EXCEPTION_{type(exc).__name__}"[:300])
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="start-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2
    if not started:
        if why == "existing-session":
            _log("REFUSE_EXISTING_SESSION")
        elif why in ("temp-fail-during-start",):
            _log("START_TEMP_FAIL")
        elif why in ("signal-before-start", "signal-during-start"):
            _log(f"SIGNAL_CLEANUP_{why}"[:300])
        else:
            _log("START_DISPLAY_MANAGER_FAIL")
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="start-fail" if "signal" not in why else f"signal-{_cleanup_state.get('pending_signal')}",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    if signalled():
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason=f"signal-{_cleanup_state.get('pending_signal')}",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    try:
        owned_sid = wait_for_owned_session(
            runner=runner, baseline=baseline,
            thermal_root=thermal_root, drm_root=drm_root, device_root=device_root,
            card=card, required=required, guard=guard,
            overall_deadline=deadline, timeout_s=session_wait_s,
            _monotonic=mono, _sleep=slp)
    except Exception as exc:
        _log(f"SESSION_EXCEPTION_{type(exc).__name__}"[:300])
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="session-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2
    if not owned_sid:
        if signalled():
            _log(f"SIGNAL_CLEANUP_SESSION")
            _cleanup_state["cleaning"] = True
            bounded_cleanup(runner, status_dir, reason=f"signal-{_cleanup_state.get('pending_signal')}",
                            owned=None, _monotonic=mono, _sleep=slp)
            _cleanup_state["cleaning"] = False
            return 2
        # Distinguish temp loss during wait vs plain timeout via fresh preflight.
        try:
            ok2, _ = preflight(thermal_root, drm_root, device_root, card, required, guard)
            _log("SESSION_TEMP_FAIL" if not ok2 else "SESSION_ACCEPTANCE_FAIL")
        except Exception:
            _log("SESSION_ACCEPTANCE_FAIL")
        _cleanup_state["cleaning"] = True
        bounded_cleanup(runner, status_dir, reason="session-fail",
                        owned=None, _monotonic=mono, _sleep=slp)
        _cleanup_state["cleaning"] = False
        return 2

    _log("SESSION_ACCEPTED_MONITORING")
    _cleanup_state["owned_session"] = owned_sid
    while mono() < deadline:
        if signalled():
            _log(f"SIGNAL_CLEANUP_MONITOR")
            _cleanup_state["cleaning"] = True
            bounded_cleanup(runner, status_dir, reason=f"signal-{_cleanup_state.get('pending_signal')}",
                            owned=owned_sid, _monotonic=mono, _sleep=slp)
            _cleanup_state["cleaning"] = False
            return 2
        ok, detail = preflight(thermal_root, drm_root, device_root, card, required, guard)
        if not ok:
            _log("MONITOR_FAIL")
            _cleanup_state["cleaning"] = True
            bounded_cleanup(runner, status_dir, reason="monitor-fail",
                            owned=owned_sid, _monotonic=mono, _sleep=slp)
            _cleanup_state["cleaning"] = False
            return 2
        # Verify owned session still the same active owned session.
        # Fail-closed: unreadable detail ends the attempt via cleanup.
        # No chvt/fgconsole VT switch is performed here: live-image kbd/chvt
        # presence is unverified, and a VT switch must never target a
        # foreign/unknown session nor exceed the 25s cleanup budget. An
        # active getty is not proof of a visible VT, and an active session
        # is not proof of pixels.
        try:
            d = get_session_detail(runner, owned_sid, timeout=VERIFY_TIMEOUT_S)
            if d is None or not d or not is_owned_session_detail(d, baseline):
                _log("MONITOR_SESSION_LOST")
                _cleanup_state["cleaning"] = True
                bounded_cleanup(runner, status_dir, reason="monitor-fail",
                                owned=owned_sid, _monotonic=mono, _sleep=slp)
                _cleanup_state["cleaning"] = False
                return 2
        except Exception:
            _log("MONITOR_FAIL")
            _cleanup_state["cleaning"] = True
            bounded_cleanup(runner, status_dir, reason="monitor-fail",
                            owned=owned_sid, _monotonic=mono, _sleep=slp)
            _cleanup_state["cleaning"] = False
            return 2
        remaining = deadline - mono()
        if remaining <= 0:
            break
        slp(min(poll_s, max(0.05, remaining)))
        if mono() >= deadline:
            break

    _log("DEADLINE_REACHED")
    _cleanup_state["cleaning"] = True
    bounded_cleanup(runner, status_dir, reason="deadline",
                    owned=owned_sid, _monotonic=mono, _sleep=slp)
    _cleanup_state["cleaning"] = False
    _cleanup_state["owned_session"] = None
    return 0


def _default_runner(cmd, timeout=None):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return SimpleNamespaceLike(returncode=1, stdout="", stderr=str(exc)[:300])


class SimpleNamespaceLike:
    def __init__(self, returncode=1, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=_POLICY_DEFAULT)
    parser.add_argument("--thermal-root", type=Path, default=Path("/sys/class/thermal"))
    parser.add_argument("--drm-root", type=Path, default=Path("/sys/class/drm"))
    parser.add_argument("--device-root", type=Path, default=Path("/dev/dri"))
    parser.add_argument("--card", default=CARD_DEFAULT)
    parser.add_argument("--timeout-s", type=int, default=MAX_SECONDS)
    parser.add_argument("--session-wait-s", type=int, default=SESSION_WAIT_S)
    parser.add_argument("--status-dir", type=Path, default=_STATUS_DIR_DEFAULT)
    args = parser.parse_args(argv)

    ok, required_or_detail = load_policy(args.policy)
    if not ok:
        _log("POLICY_FAIL")
        bounded_cleanup(_default_runner, args.status_dir, reason="policy-fail")
        return 0

    try:
        import importlib.util as _ilu
        guard_path = Path("/usr/local/lib/kestrel_graphics_guard.py")
        if not guard_path.is_file():
            guard_path = Path(__file__).with_name("kestrel_graphics_guard.py")
        _spec = _ilu.spec_from_file_location("kestrel_graphics_guard", guard_path)
        _guard = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_guard)
    except Exception:
        _log("GUARD_LOAD_FAIL")
        bounded_cleanup(_default_runner, args.status_dir, reason="guard-fail")
        return 0

    _cleanup_state["runner"] = _default_runner
    _cleanup_state["status_dir"] = args.status_dir
    _cleanup_state["pending_signal"] = None
    _cleanup_state["cleaning"] = False
    try:
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
    except (OSError, ValueError):
        pass

    rc = run_bounded_session(
        thermal_root=args.thermal_root, drm_root=args.drm_root,
        device_root=args.device_root, card=args.card,
        required=required_or_detail, guard=_guard,
        runner=_default_runner, status_dir=args.status_dir,
        timeout_s=min(int(args.timeout_s), MAX_SECONDS),
        session_wait_s=min(int(args.session_wait_s), SESSION_WAIT_S))
    # Never block normal boot: service exit is always 0 after bounded cleanup.
    _log(f"EXIT_{rc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
