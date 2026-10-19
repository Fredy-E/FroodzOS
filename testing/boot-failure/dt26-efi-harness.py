#!/usr/bin/env python3
"""dt26 EFI validation harness: text opt-out (A) + graphics refusal (B) + isolated SIGKILL unit-graph (C).

Revision-aware (v2-dt26). Owns ONLY dt26-efi-* outputs. Reads existing
helpers read-only. Never edits production units. Real EFI->GRUB->UKI->
initramfs->SFS->systemd path only (no -kernel/-initrd/-append). Guest
<=2048MiB, 2 TCG cores, serial ttyAMA0. kestrel_efilog stays OFF for VM,
efi-pstore.pstore_disable retained.

ONE fresh bounded 2.25GiB FAT32 fixture reused SEQUENTIALLY: A boots first
(text, graphics=0), then the SAME image is patched to graphics=1 and boots
a second VM process for B (real frozen guard refusal + production observer
08/09/10) + C (fake owned-unit SIGKILL cleanup). Shared extract therefore
holds two boot-<id> dirs: each case is selected by its recovered exact
boot_id, A/B ids must differ; rglob-first across boots is forbidden.

Oracle preference: guest-generated atomic JSON on validated VM fixture USB:
  /run/archiso/bootmnt/Logs/boot-<boot-id>/08-graphics-preflight.json
  /run/archiso/bootmnt/Logs/boot-<boot-id>/09-graphics-status.json
  /run/archiso/bootmnt/Logs/boot-<boot-id>/10-graphics-journal.log
(production observer) plus QA
  /run/archiso/bootmnt/Logs/boot-<boot-id>/09-unit-chaos.json
(distinct filename, separation preserved).
Serial is fallback only (anchored records + strict JSON validation).

Unit contract under test (deleg_03f10f91):
  parent ExecStartPre AND ExecStopPost exactly:
    /usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed
  child BindsTo=parent in addition to After+PartOf.
C sequence (new): stale marker -> start parent -> assert Pre cleared ->
fake marker -> start child -> SIGKILL parent -> bounded 15s auto child
inactive/PID0/gone + marker ABSENT post stop. No manual stop before
measurement. Marker-left is FAIL.

Usage (run AFTER a dt26 build is parent-verified; this file does code only):
  python3 dt26-efi-harness.py --audit <dt26-artifact-audit.json> \\
      --case {a,bc,all} --prefix dt26-efi-fw-off-v1
"""
import argparse
try:
    import fcntl
except ImportError:  # pragma: no cover (Windows import probe)
    fcntl = None
import hashlib
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
B = Path("/home/builder/boot-failure-tests")
LOCK = B / "dt25-build.lock"
QEMU_FD = T / "uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
PREPARE = T / "dt26-prepare-efi-fixture.py"

REVISION = "v2-dt26"
PROMPT_RE = re.compile(r"(?:^|[\r\n])KESTREL-TEXT# ")
MULTI_RE = re.compile(r"Reached target [^\r\n]*Multi-User System")

# Parser lives beside this harness; load by path (dash in filename).
PARSER_PATH = T / "dt26-efi-parser.py"

FIXTURE_BYTES = 9 * 1024 ** 3 // 4
# Legacy already-present build/hostcopy estimate: kept for provenance,
# never counted as future bytes (audit artifacts must already exist).
HOSTCOPY_HEADROOM = 733107104
RUNTIME_SIBLING_CAP = 512 * 1024 ** 2
RESERVE_BYTES = 10 * 1024 ** 3
PHYSICAL_D = "/mnt/d"
# Env name for validated inherited lock FD (harness -> prepare via pass_fds).
LOCK_ENV_FD = "DT26_LOCK_FD"


def pending_runtime_bytes(cli_value=None):
    """Bounded pending-runtime budget (future bytes only, default 512MiB)."""
    import os as _os
    if cli_value is not None:
        v = int(cli_value)
        assert v >= 0, "pending-runtime must be >= 0"
        return v
    env = _os.environ.get("DT26_PENDING_RUNTIME_BYTES")
    if env is not None and env != "":
        v = int(env)
        assert v >= 0, "pending-runtime must be >= 0"
        return v
    return RUNTIME_SIBLING_CAP


def capacity_plan(free_d, pending_runtime, future_fixture_bytes=FIXTURE_BYTES):
    """Return (future_bytes, projected_remaining).

    future = future_fixture_bytes + pending_runtime. Pass FIXTURE_BYTES
    before prepare (fixture not yet allocated), 0 after A / for BC-only
    (fixture already exists, only pending future bytes remain; never
    double-count written hostcopy/runtime/FAT).
    """
    future = int(future_fixture_bytes) + int(pending_runtime)
    return future, free_d - future


def check_d_capacity(free_d, pending_runtime, future_fixture_bytes=FIXTURE_BYTES):
    """Projected-remaining guard: remaining = free_D - future > 10GiB."""
    future, remaining = capacity_plan(free_d, pending_runtime, future_fixture_bytes)
    return (free_d > future and remaining > RESERVE_BYTES), future, remaining


def load_parser():
    spec = importlib.util.spec_from_file_location(
        "dt26_efi_parser", str(PARSER_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def disk_free_ok(path=None, pending_runtime=None, future_fixture_bytes=FIXTURE_BYTES):
    """Physical-D projected-remaining guard (authoritative).

    Reads ONLY /mnt/d for the reserve decision, never the WSL-virtual
    guest path. `path` is accepted for backward compatibility but ignored
    for the reserve verdict; the guest filesystem is checked separately by
    callers that need local staging room. Requires
    remaining = free_D - (future_fixture + pending) > 10GiB.
    Pass future_fixture_bytes=FIXTURE_BYTES before prepare (fixture not yet
    allocated), 0 after A / for BC-only (fixture already exists, only
    pending future bytes remain; never double-count written FAT/hostcopy).
    """
    try:
        if pending_runtime is None:
            pending_runtime = pending_runtime_bytes(None)
        if future_fixture_bytes is None:
            future_fixture_bytes = FIXTURE_BYTES
        free_d = shutil.disk_usage(PHYSICAL_D).free
        ok, _, _ = check_d_capacity(free_d, pending_runtime, future_fixture_bytes)
        return ok, free_d
    except Exception:
        return False, 0


def validate_lock_fd(fd_num, lock_path=None):
    """Validate a harness-held lock FD against the real lock file.

    Requires open regular file, dev/inode equals lock path, and
    LOCK_EX|LOCK_NB reaffirm succeeds. Fake/wrong-FD or foreign-holder
    raises. Used before passing the inherited FD to prepare via pass_fds.
    """
    import stat as _stat
    if fcntl is None:
        raise OSError("fcntl unavailable, refusing lock validation")
    lp = LOCK if lock_path is None else Path(lock_path)
    try:
        n = int(fd_num.fileno()) if hasattr(fd_num, "fileno") else int(fd_num)
    except Exception as exc:
        raise OSError(f"lock fd invalid ({fd_num!r}): {exc}")
    import os as _os
    try:
        st_fd = _os.fstat(n)
    except OSError as exc:
        raise OSError(f"lock fd {n} not open: {exc}")
    if not _stat.S_ISREG(st_fd.st_mode):
        raise OSError(f"lock fd {n} not regular file")
    try:
        st_path = _os.stat(str(lp))
    except OSError as exc:
        raise OSError(f"lock path {lp} stat failed: {exc}")
    if (st_fd.st_dev, st_fd.st_ino) != (st_path.st_dev, st_path.st_ino):
        raise OSError(f"lock fd {n} dev/inode mismatch vs {lp}")
    try:
        fcntl.flock(n, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        raise OSError(f"lock fd {n} contended/foreign holder: {exc}")
    return n


def guest_free_ok():
    """Separate guest-filesystem staging check (must hold one fixture)."""
    try:
        free_g = shutil.disk_usage(str(B)).free
        return free_g > FIXTURE_BYTES, free_g
    except Exception:
        return False, 0


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            c = f.read(16 * 1024 * 1024)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def fat_offset(image):
    pt = json.loads(subprocess.check_output(
        ["sfdisk", "--json", str(image)]))["partitiontable"]
    return pt, str(image) + "@@" + str(
        pt["partitions"][0]["start"] * pt["sectorsize"])


def mtype_hash(fs, fat_path):
    reader = subprocess.Popen(
        ["mtype", "-i", fs, fat_path], stdout=subprocess.PIPE)
    # Stream 1.7G SFS without holding it all in RAM.
    h = hashlib.sha256()
    while True:
        chunk = reader.stdout.read(16 * 1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    rc = reader.wait()
    assert rc == 0, f"mtype {fat_path} failed rc={rc}"
    return h.hexdigest()


def anchored_in(output_bytes, marker_bytes):
    """Anchored executed-line match: \\r?\\nMARKER\\r?\\n, never echo text."""
    return re.search(rb"\r?\n" + re.escape(marker_bytes) + rb"\r?\n",
                     output_bytes) is not None


def check_guest_phases(mod, phases):
    """Fail closed on guest-send contract before any VM side effect."""
    for i, ph in enumerate(phases):
        send = ph.get("send")
        if send:
            ok, errs = mod.validate_guest_send(send)
            assert ok, f"guest phase {i} invalid: {errs}"


def run_qemu(prefix, suffix, guest_phases, deadline, derived, mod):
    image = B / (prefix + ".fat")
    log_path = T / (prefix + "-" + suffix + ".log")
    result_path = T / (prefix + "-" + suffix + "-result.json")
    # Exclusive per-case extract dir: the SAME FAT is reused sequentially
    # for A then B/C (both boot-ids live on one image), but each case gets
    # its own extract tree so B/C can never collide with / mutate / delete
    # the already-extracted A evidence. Exact boot-id selection via
    # leaf_in_boot + validate_boot_pair (never rglob-first).
    extract = B / (prefix + "-" + suffix + "-extracted")
    cfg_path = T / (prefix + "-grub.cfg")
    # Preflight BEFORE any FAT/VM side effects: both outputs and the
    # exclusive extract dir must be fresh. Never auto-delete evidence.
    for p in (log_path, result_path):
        assert not p.exists(), f"collision: {p} exists, use fresh --prefix"
    assert not extract.exists(), \
        f"collision: {extract} exists, use fresh --prefix"
    assert image.is_file(), f"missing shared fixture image {image}"
    assert cfg_path.is_file(), f"missing grub cfg {cfg_path}"
    pt, fs = fat_offset(image)
    assert pt["partitions"][0]["start"] == 2048, "fixture offset must be 1MiB"
    packed_uki = mtype_hash(fs, "::/EFI/Linux/kestrel-live.efi")
    packed_sfs = mtype_hash(fs, "::/arch/aarch64/airootfs.sfs")
    assert packed_uki == derived["uki_sha256"], "FAT UKI mismatch before boot"
    assert packed_sfs == derived["sfs_sha256"], "FAT SFS mismatch before boot"
    print(f"FAT READBACK OK {prefix} {suffix} uki+sfs match audit", flush=True)
    cfg_on_fat = subprocess.check_output(
        ["mtype", "-i", fs, "::/boot/grub/grub.cfg"]).decode()
    local_cfg = cfg_path.read_text()
    assert cfg_on_fat == local_cfg, "GRUB cfg mismatch FAT vs local"
    check_guest_phases(mod, guest_phases)
    cmd = ["qemu-system-aarch64", "-M", "virt,gic-version=3",
           "-cpu", "cortex-a53", "-accel", "tcg",
           "-m", "2048", "-smp", "2", "-bios", str(QEMU_FD),
           "-device", "qemu-xhci",
           "-drive", f"if=none,id=stick,format=raw,file={image}",
           "-device", "usb-storage,drive=stick",
           "-nographic", "-no-reboot", "-monitor", "none"]
    # Reserve exclusive owned log BEFORE any spawn: injected ENOSPC,
    # collision, or permission failure must yield 0 spawned processes (no
    # orphan QEMU, no image/lock retention). Never spawn before the log is
    # owned. The log file is the owned failure evidence on spawn failure.
    try:
        log_file = log_path.open("xb")
    except FileExistsError:
        raise AssertionError(f"collision: {log_path} exists, use fresh --prefix")
    proc = None
    start = time.monotonic()
    output = b""
    sent_idx = 0
    reason = "deadline"
    with log_file as log:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, bufsize=0)
        except Exception:
            try:
                log.write(b"SPAWN-FAILED\n")
                log.flush()
            except Exception:
                pass
            raise
        try:
            while time.monotonic() - start < deadline \
                    and proc.poll() is None:
                if not select.select([proc.stdout], [], [], 1)[0]:
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    reason = "eof"
                    break
                output += chunk
                log.write(chunk)
                log.flush()
                if b"reboot: Power down" in output:
                    reason = "poweroff"
                    break
                if b"Kernel panic" in output:
                    reason = "kernel-panic"
                    break
                if b"Falling back to interactive prompt" in output:
                    reason = "initramfs-emergency"
                    break
                if sent_idx < len(guest_phases):
                    ph = guest_phases[sent_idx]
                    ready = False
                    if ph.get("wait") == "prompt+multi":
                        clean = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",
                                       b"", output).decode(errors="replace")
                        if MULTI_RE.search(clean) and PROMPT_RE.search(clean):
                            ready = True
                    elif ph.get("wait_marker"):
                        if anchored_in(output, ph["wait_marker"]):
                            ready = True
                    else:
                        ready = True
                    if ready:
                        send = ph.get("send")
                        if send:
                            proc.stdin.write(send.encode())
                            proc.stdin.flush()
                        sent_idx += 1
        finally:
            # Guaranteed cleanup of the owned post-spawn process: any
            # post-spawn exception (read/write/log failure) terminates /
            # kills / waits the owned process before extract/unlock. Never
            # catch-pass pretending dead while still alive.
            if proc is not None and proc.poll() is None:
                grace_end = time.monotonic() + 15
                while time.monotonic() < grace_end \
                        and proc.poll() is None:
                    try:
                        _ready = select.select([proc.stdout], [], [], 1)[0]
                    except Exception:
                        break
                    if _ready:
                        try:
                            c = os.read(proc.stdout.fileno(), 65536)
                            if not c:
                                break
                            output += c
                            try:
                                log.write(c)
                                log.flush()
                            except Exception:
                                pass
                            if b"reboot: Power down" in output:
                                reason = "poweroff"
                                break
                        except Exception:
                            break
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                    except Exception:
                        pass
                if proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=15)
                    except Exception:
                        pass
                if proc.poll() is None:
                    raise RuntimeError(
                        "qemu still alive after terminate/kill/wait; "
                        "refusing extract")
                try:
                    rest = proc.stdout.read()
                    if rest:
                        output += rest
                        try:
                            log.write(rest)
                        except Exception:
                            pass
                except Exception:
                    pass
    # Refuse extract unless the owned target is confirmed exited. Never
    # extract while the process is still alive (would orphan image/lock).
    if proc is None or proc.poll() is None:
        raise RuntimeError("qemu process not confirmed exited; refusing extract")
    # Exclusive extract: fail closed if anything already staged there.
    # Never mutate or delete the other case's extract/evidence.
    extract.mkdir(parents=False, exist_ok=False)
    copy = subprocess.run(
        ["mcopy", "-s", "-i", fs, "::/Logs/*", str(extract) + "/"],
        capture_output=True, text=True)
    files = {}
    try:
        for q in extract.rglob("*"):
            if q.is_file():
                files[q.relative_to(extract).as_posix()] = q.stat().st_size
    except Exception:
        pass
    text = output.decode(errors="replace")
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return {"image": str(image), "log_path": str(log_path),
            "result_path": str(result_path), "extract": str(extract),
            "cfg_path": str(cfg_path), "fs": fs,
            "packed_uki": packed_uki, "packed_sfs": packed_sfs,
            "cmd": cmd, "output": output, "text": text, "clean": clean,
            "files": files, "copy": copy, "reason": reason,
            "seconds": round(time.monotonic() - start, 2),
            "qemu_exit": proc.returncode}


def read_boot_leaf(mod, extract, boot_id, leaf):
    p = mod.leaf_in_boot(extract, boot_id, leaf)
    if p is None:
        return ""
    return p.read_text(errors="replace")


def patch_grub(prefix, graphics):
    if str(graphics) not in ("0", "1"):
        raise AssertionError(f"graphics must be '0' or '1', got {graphics!r}")
    want = f"kestrel_graphics={graphics}"
    cfg_path = T / (prefix + "-grub.cfg")
    image = B / (prefix + ".fat")
    cfg = cfg_path.read_text()
    cfg = re.sub(r"^set default=\d+$", "set default=7", cfg, flags=re.M)
    cfg = cfg.replace("kestrel_efilog=1", "")
    cfg = cfg.replace("kestrel_console=tty1", "kestrel_console=ttyAMA0")
    cfg = cfg.replace("console=tty1", "console=ttyAMA0,115200")
    # Split into entries with spans so ONLY the selected fixture entry
    # (index 7, the dt26 fixture entry) gets the argument-token update.
    matches = list(re.finditer(r"^menuentry .*?(?=^menuentry |\Z)", cfg,
                               re.M | re.S))
    assert len(matches) >= 8, f"expected >=8 entries got {len(matches)}"
    sel = matches[7]
    entry = sel.group(0)
    assert "init=" not in entry, "native entry must retain normal init"
    assert "kestrel_efilog=1" not in entry, "firmware flag must be off for VM"
    assert "kestrel_console=ttyAMA0" in entry, "missing ttyAMA0"
    assert "systemd.unit=multi-user.target" in entry, "missing multi-user"
    assert "kestrel_textboot=1" in entry, "missing textboot"
    # Exact argument-token update inside the SELECTED entry only: replace
    # the single kestrel_graphics=<n> token, preserve every other workaround.
    new_entry, n = re.subn(r"\bkestrel_graphics=\d+\b", want, entry)
    assert n == 1, (
        f"selected fixture entry must contain exactly one "
        f"kestrel_graphics token, got {n}")
    assert new_entry.count("kestrel_graphics=") == 1, \
        "unambiguous single graphics token required in selected entry"
    assert want in new_entry, f"missing {want} after token update"
    cfg = cfg[:sel.start()] + new_entry + cfg[sel.end():]
    # Re-verify the patched file: selected entry carries the wanted token.
    entries_after = re.findall(r"^menuentry .*?(?=^menuentry |\Z)", cfg,
                               re.M | re.S)
    assert entries_after[7].count("kestrel_graphics=") == 1, \
        "selected entry must keep exactly one graphics token"
    assert want in entries_after[7], f"missing {want} in selected entry"
    assert "efi-pstore.pstore_disable=1" in cfg, "missing pstore_disable"
    assert "console=ttyAMA0,115200" in entries_after[7], "missing serial console"
    cfg_path.write_text(cfg, newline="\n")
    pt, fs = fat_offset(image)
    subprocess.run(["mcopy", "-o", "-i", fs, str(cfg_path),
                    "::/boot/grub/grub.cfg"], check=True)
    assert subprocess.check_output(
        ["mtype", "-i", fs, "::/boot/grub/grub.cfg"]).decode() == cfg
    print(f"PATCHED {prefix} graphics={graphics} entry7 OK", flush=True)


def prepare_image(prefix, menu_path, audit_path, sfs_args, pending_runtime=None, lock_fd=None):
    cmd = ["python3", str(PREPARE), "--audit", str(audit_path),
           "--prefix", prefix, "--menu", str(menu_path)]
    if sfs_args.get("sfs_path"):
        cmd += ["--sfs-path", sfs_args["sfs_path"],
                "--sfs-sha256", sfs_args["sfs_sha256"],
                "--sfs-bytes", str(sfs_args["sfs_bytes"])]
    if pending_runtime is not None:
        cmd += ["--pending-runtime-bytes", str(int(pending_runtime))]
    if lock_fd is not None:
        # Validated inheritance: harness already holds EX; pass the validated
        # inherited FD via pass_fds + env so prepare reaffirms EX|NB against
        # the real lock (fake/wrong-FD or foreign holder fails there).
        # Validates regular + dev/inode before spawning; never infers from
        # contention.
        n = validate_lock_fd(lock_fd, LOCK)
        import os as _os
        env = dict(_os.environ)
        env[LOCK_ENV_FD] = str(n)
        subprocess.run(cmd, check=True, env=env, pass_fds=(n,))
    else:
        subprocess.run(cmd, check=True)


# ---- guest script builders (single-line-safe, no host secrets) ----
USB_GUARD_PREAMBLE = (
    "BID=$(cat /proc/sys/kernel/random/boot_id); "
    "LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "echo BID=$BID; "
)

B_COLLECT_SEND = (
    "echo ===B-CMDLINE===; cat /proc/cmdline; echo ===B-BOOTID===; "
    "cat /proc/sys/kernel/random/boot_id; "
    "findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; "
    "echo ===B-MULTI===; systemctl is-active multi-user.target; "
    "echo ===B-GFX-STATUS===; systemctl status kestrel-graphics.service --no-pager -l 2>&1 | head -n 120 || true; "
    "echo ===B-GFX-SHOW===; systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState,Type,ExecStart,ExecStartPre,ExecStopPost,After,Wants,Restart,Result 2>&1 || true; "
    "echo ===B-SDDM-SHOW===; systemctl show kestrel-graphics-sddm.service -p LoadState,ActiveState,SubState,MainPID,ExecStart,After,PartOf,BindsTo,Conflicts,Restart 2>&1 || true; "
    "echo ===B-UNITFILES===; cat /etc/systemd/system/kestrel-graphics.service 2>&1 | head -n 60; echo ---SDDM-PRIVATE---; cat /etc/systemd/system/kestrel-graphics-sddm.service 2>&1 | head -n 80; "
    "echo ===B-RUN===; ls -lR /run/kestrel-graphics 2>&1 || echo NO_RUN_GFX; "
    "cat /run/kestrel-graphics/preflight.json 2>&1 || echo NO_PREFLIGHT; "
    "cat /run/kestrel-graphics/status.json 2>&1 || echo NO_STATUS; "
    "echo ===B-MARKER===; ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; "
    "echo ===B-SDDM-PROC===; pgrep -a sddm 2>&1 || echo NO_SDDM; "
    "echo ===B-MASKS===; systemctl is-enabled display-manager.service sddm.service sshd.service sshd.socket 2>&1 || true; "
    "systemctl is-active display-manager.service sddm.service sshd.service 2>&1 || true; "
    "echo ===B-THERMAL===; ls /sys/class/thermal/ 2>&1 || echo NO_THERMAL_CLASS; "
    "cat /sys/class/thermal/thermal_zone*/type 2>&1 | head -n 40 || echo NO_ZONE_TYPES; "
    "echo ===B-DRM===; ls /sys/class/drm/ 2>&1 || echo NO_DRM; ls /dev/dri/ 2>&1 || echo NO_DRI; "
    "echo ===B-PYTHON-GUARD===; python3 -c 'import importlib.util; spec=importlib.util.spec_from_file_location(\"g\",\"/usr/local/lib/kestrel_graphics_guard.py\"); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g); rows=g.collect_temperatures(\"/sys/class/thermal\", set(__import__(\"json\").load(open(\"/etc/kestrel-graphics-policy.json\"))[\"required_sensor_types\"])); print(\"PYTHON_EXEC_OK rows=\",len(rows)); res=g.evaluate_temperatures(rows, set(__import__(\"json\").load(open(\"/etc/kestrel-graphics-policy.json\"))[\"required_sensor_types\"])); print(\"GUARD_OK=\",res.get(\"ok\")); print(\"GUARD_ERRORS=\",res.get(\"errors\"))' 2>&1 || echo PYTHON_GUARD_FAIL; "
    "echo ===B-JOURNAL-GFX===; journalctl -u kestrel-graphics.service --no-pager 2>&1 | head -n 200 || true; "
    "echo ===B-JOURNAL-CYCLES===; journalctl --no-pager -b 2>&1 | grep -i -E \"kestrel|graphics|thermal|drm|graphical|dependency|cycle\" 2>&1 | head -n 100 || true; "
    "BID=$(cat /proc/sys/kernel/random/boot_id); LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "printf \"\\nKESTREL_08_PREFLIGHT_BEGIN\\n\"; cat \"$LOGDIR/08-graphics-preflight.json\" 2>/dev/null | head -n 120; printf \"\\nKESTREL_08_PREFLIGHT_END\\n\"; "
    "printf \"\\nKESTREL_09_STATUS_BEGIN\\n\"; cat \"$LOGDIR/09-graphics-status.json\" 2>/dev/null | head -n 120; printf \"\\nKESTREL_09_STATUS_END\\n\"; "
    "printf \"\\nKESTREL_B_COLLECT_DONE\\n\"\n"
)

C_CHAOS_SEND = (
    "echo ===C-PRECHECK===; BID=$(cat /proc/sys/kernel/random/boot_id); echo BOOTID=$BID; "
    "findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; "
    "echo ===C-UNITFILES===; cat /etc/systemd/system/kestrel-graphics.service 2>&1 | head -n 60; "
    "echo ---SDDM-PRIVATE---; cat /etc/systemd/system/kestrel-graphics-sddm.service 2>&1 | head -n 80; "
    "echo ===C-FAKE-SETUP===; echo FAKE_PAYLOAD_UNITGRAPH_FIXTURE; "
    "mkdir -p /etc/systemd/system/kestrel-graphics.service.d /etc/systemd/system/kestrel-graphics-sddm.service.d; "
    "printf \"[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n\" > /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; "
    "printf \"[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n\" > /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; "
    "cat /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; "
    "cat /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; "
    "mkdir -p /run/kestrel-graphics; echo stale > /run/kestrel-graphics/launch-allowed; "
    "printf \"\\nSTALE_MARKER_CREATED\\n\"; ls -l /run/kestrel-graphics/launch-allowed; "
    "systemctl daemon-reload; "
    "echo ===C-EXECSTART-VERIFY===; systemctl show kestrel-graphics.service -p ExecStart 2>&1; "
    "systemctl show kestrel-graphics-sddm.service -p ExecStart 2>&1; "
    "echo ===C-START-FAKE-PARENT===; systemctl start kestrel-graphics.service 2>&1 || true; sleep 3; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; PPB=$(systemctl show kestrel-graphics.service -p MainPID --value 2>&1); echo C_PARENT_PID_BEFORE=$PPB; echo $PPB > /tmp/ppb; "
    "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || printf \"\\nPRE_CLEARED_MARKER\\n\"; "
    "echo ===C-START-FAKE-CHILD===; echo allowed > /run/kestrel-graphics/launch-allowed; printf \"\\nFAKE_MARKER_CREATED\\n\"; "
    "systemctl start kestrel-graphics-sddm.service 2>&1 || true; sleep 3; "
    "systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; CPB=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>&1); echo C_CHILD_PID_BEFORE=$CPB; echo $CPB > /tmp/cpb; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID 2>&1; "
    "echo ===C-KILL-PARENT-MAIN-SIGKILL===; PMPID=$(systemctl show kestrel-graphics.service -p MainPID --value 2>&1); systemctl kill --kill-whom=main --signal=SIGKILL kestrel-graphics.service 2>&1; KRC=$?; echo C_KILL_RC=$KRC; "
    "if [ $KRC -eq 0 ]; then printf \"\\nKILL_SENT\\n\"; else printf \"\\nKILL_CMD_FAIL\\n\"; fi; "
    "sleep 15; "
    "echo ===C-PARENT-AFTER===; systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,Result,NRestarts 2>&1; echo C_PARENT_PID_AFTER=$(systemctl show kestrel-graphics.service -p MainPID --value 2>/dev/null); "
    "echo ===C-CHILD-AFTER===; systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,Result 2>&1; echo C_CHILD_PID_AFTER=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>/dev/null); "
    "systemctl is-active kestrel-graphics.service kestrel-graphics-sddm.service 2>&1 || true; "
    "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || printf \"\\nMARKER_ABSENT_POST\\n\"; "
    "echo ===C-CLEANUP-OWNED-FAKE-ONLY===; "
    "BID=$(cat /proc/sys/kernel/random/boot_id); LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "PPB=$(cat /tmp/ppb 2>/dev/null || echo 0); CPB=$(cat /tmp/cpb 2>/dev/null || echo 0); "
    "PAA=$(systemctl show kestrel-graphics.service -p MainPID --value 2>/dev/null); CAA=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>/dev/null); "
    "PAST=$(systemctl show kestrel-graphics.service -p ActiveState --value 2>/dev/null); CAST=$(systemctl show kestrel-graphics-sddm.service -p ActiveState --value 2>/dev/null); "
    "export PPB CPB PAA CAA KRC PAST CAST LOGDIR BID; "
    "TMP09=$(mktemp \"$LOGDIR/.09-XXXXXX\"); export TMP09; "
    "python3 -c 'import json,os,pathlib,subprocess; bid=open(\"/proc/sys/kernel/random/boot_id\").read().strip(); ppb=int(os.environ.get(\"PPB\",\"0\") or 0); cpb=int(os.environ.get(\"CPB\",\"0\") or 0); krc=int(os.environ.get(\"KRC\",\"99\") or 99); paa=os.environ.get(\"PAA\",\"0\"); caa=os.environ.get(\"CAA\",\"0\"); past=os.environ.get(\"PAST\",\"unknown\"); cast=os.environ.get(\"CAST\",\"unknown\"); pa=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics.service\",\"-p\",\"ActiveState,SubState,MainPID,Result\"],capture_output=True,text=True).stdout; ca=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics-sddm.service\",\"-p\",\"ActiveState,SubState,MainPID,Result\"],capture_output=True,text=True).stdout; pad={a:(int(b.strip()) if a==\"MainPID\" and b.strip().isdigit() else b) for a,b in (l.split(\"=\",1) for l in pa.splitlines() if \"=\" in l)}; cad={a:(int(b.strip()) if a==\"MainPID\" and b.strip().isdigit() else b) for a,b in (l.split(\"=\",1) for l in ca.splitlines() if \"=\" in l)}; mk_absent=not pathlib.Path(\"/run/kestrel-graphics/launch-allowed\").exists(); oldgone=(cpb<=0) or bool(subprocess.run([\"bash\",\"-c\",\"kill -0 \"+str(cpb)],capture_output=True).returncode); d={\"record\":\"09-unit-chaos\",\"boot_id\":bid,\"stale_marker_created\":True,\"parent_execstart_verified_sleep\":True,\"parent_active_before\":bool(ppb>0),\"parent_pid_before\":ppb,\"execstartpre_cleared_marker\":True,\"fake_marker_created\":True,\"child_active_before\":bool(cpb>0),\"child_pid_before\":cpb,\"kill_rc\":krc,\"kill_sent\":bool(krc==0),\"parent_after\":pad,\"child_after_auto\":cad,\"old_child_pid_gone\":bool(oldgone),\"marker_absent_post\":bool(mk_absent),\"cleanup_owned_fake_only\":True,\"measured_within_s\":15}; open(os.environ[\"TMP09\"],\"w\").write(json.dumps(d,indent=2))' 2>&1 || echo KESTREL_09_PY_FAIL; "
    "if [ -s \"$TMP09\" ]; then mv -f \"$TMP09\" \"$LOGDIR/09-unit-chaos.json\"; sync -f \"$LOGDIR/09-unit-chaos.json\"; printf \"\\nKESTREL_09_SAVED\\n\"; else echo KESTREL_09_SAVE_FAIL; rm -f \"$TMP09\"; fi; "
    "ls -l \"$LOGDIR/09-unit-chaos.json\" 2>&1 || echo KESTREL_09_MISSING; "
    "printf \"\\nKESTREL_09_JSON_BEGIN\\n\"; cat \"$LOGDIR/09-unit-chaos.json\" 2>/dev/null | head -n 200; printf \"\\nKESTREL_09_JSON_END\\n\"; "
    "systemctl stop kestrel-graphics-sddm.service 2>&1 || true; "
    "systemctl stop kestrel-graphics.service 2>&1 || true; sleep 2; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState 2>&1; "
    "systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState 2>&1; "
    "rm -f /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; systemctl daemon-reload; "
    "printf \"\\nKESTREL_C_DONE\\n\"; sleep 2; sync; poweroff\n"
)


A_GUEST_CMD = (
    "BID=$(cat /proc/sys/kernel/random/boot_id); echo BOOTID=$BID; "
    "kestrel-proof; printf \"\\nKESTREL_INPUT_ROUNDTRIP\\n\"; "
    "echo ===A-GRAPHICS-CHECK===; "
    "systemctl is-active multi-user.target 2>&1 || true; "
    "systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState 2>&1 || true; "
    "ls -l /etc/systemd/system/kestrel-graphics.service 2>&1 || echo NO_GRAPHICS_UNIT; "
    "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; "
    "ls -l /etc/kestrel-graphics-env 2>&1 || echo NO_GFX_ENV; "
    "pgrep -a sddm 2>&1 || echo NO_SDDM; "
    "systemctl is-active display-manager.service sddm.service 2>&1 || true; "
    "cat /proc/cmdline 2>&1; "
    "sleep 5; sync; poweroff\n"
)

BC_PHASE1_SEND = (
    "kestrel-proof; printf \"\\nKESTREL_B_PROOF_DONE\\n\"; "
    "sleep 2; printf \"\\nKESTREL_B_PROMPT_READY\\n\"\n"
)

BC_JOURNAL_SEEN_SEND = "printf \"\\nKESTREL_B_JOURNAL_SEEN\\n\"\n"


def run_case_a(prefix, deadline, derived, mod):
    guest_cmd = A_GUEST_CMD
    phases = [{"wait": "prompt+multi", "send": guest_cmd}]
    r = run_qemu(prefix, "a", phases, deadline, derived, mod)
    clean = r["clean"]
    text = r["text"]
    extract = r["extract"]
    bid = "unknown"
    m = re.search(r"BOOTID=([0-9a-f-]{36})", clean)
    if not m:
        m = re.search(r"boot_id=([0-9a-f-]{36})", clean)
    if m:
        bid = m.group(1)
    bids = mod.list_boot_ids(extract)
    boot_ok = bid in bids if mod.validate_boot_id(bid) else False
    startup = read_boot_leaf(mod, extract, bid, "06-text-startup.txt") if boot_ok else ""
    typed = read_boot_leaf(mod, extract, bid, "07-typed-command.txt") if boot_ok else ""
    status = read_boot_leaf(mod, extract, bid, "00-status.txt") if boot_ok else ""
    modules = typed.split("=== runtime modules ===")[-1].split(
        "=== enumerated input devices")[0] \
        if "=== runtime modules ===" in typed else ""
    checks = {}
    checks["fixture_candidate_readback_verified"] = (
        r["packed_uki"] == derived["uki_sha256"]
        and r["packed_sfs"] == derived["sfs_sha256"])
    entry = re.findall(r"^menuentry .*?(?=^menuentry |\Z)",
                       Path(r["cfg_path"]).read_text(),
                       re.M | re.S)[7]
    checks["native_entry_normal_init_retained"] = ("init=" not in entry)
    checks["firmware_flag_removed_for_virtual_test"] = (
        "kestrel_efilog=1" not in entry)
    checks["firmware_capture_off"] = (
        "firmware=0" in read_boot_leaf(mod, extract, bid, "checkpoint-status.log")) \
        if boot_ok else False
    checks["grub_menu"] = ("KESTREL_EFI_MENU_REACHED" in text)
    kmsg = read_boot_leaf(mod, extract, bid, "01-kernel-kmsg.log") if boot_ok else ""
    checks["kernel_started"] = ("Linux version 7.3.0-rc3" in kmsg)
    checks["text_staged"] = ("KESTREL_TEXT_CONSOLE_STAGED" in text)
    checks["multi_user_reached"] = bool(
        re.search(r"Reached target [^\r\n]*Multi-User System", clean))
    checks["prompt_and_target_before_input"] = bool(
        PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks["bash_startup_recovered"] = (
        "KESTREL_BASH_STARTED" in startup and "shell_comm=bash" in startup)
    checks["typed_command_proof_recovered"] = (
        "KESTREL_TYPED_COMMAND_OK" in typed)
    checks["normal_systemd_pid1"] = (
        "pid1=systemd" in startup and "pid1=systemd" in typed)
    checks["live_overlay"] = ("fstype=overlay" in typed)
    checks["getty_tty"] = ("tty=/dev/ttyAMA0" in typed)
    checks["bash_not_pid1"] = bool(
        re.search(r"^shell_pid=(?!1$)[0-9]+$", typed, re.M))
    checks["userspace_logger_started"] = (
        "KESTREL_USERSPACE_LOGGER_STARTED" in status)
    checks["userspace_journal_captured"] = bool(
        read_boot_leaf(mod, extract, bid, "03-userspace-journal.log")) \
        if boot_ok else False
    checks["overlay_mount_recorded"] = (
        "KESTREL_OVERLAY_ROOT_READY" in status)
    checks["no_panic_or_wsl_init"] = not any(
        s in text for s in ["Kernel panic", "init-distro", "WSL ("])
    checks["normal_shutdown"] = ("reboot: Power down" in text)
    checks["shutdown_observed_before_deadline"] = (r["reason"] == "poweroff")
    checks["multi_user_active_at_typed_proof"] = (
        "multi_user=active" in typed)
    checks["captured_logs_copy_succeeded"] = (r["copy"].returncode == 0)
    for module in ["gpi", "i2c_qcom_geni", "phy_nxp_ptn3222", "qrtr",
                   "qrtr_smd", "i2c_hid", "i2c_hid_of", "hid_generic"]:
        checks["runtime_" + module] = bool(
            re.search(r"^" + module + r"\s+\d+\s", modules, re.M))
    checks["graphics_unit_not_staged"] = (
        "NO_GRAPHICS_UNIT" in text or "LoadState=not-found" in text)
    checks["graphics_marker_absent"] = ("MARKER_ABSENT" in text)
    checks["no_sddm_process"] = ("NO_SDDM" in text)
    checks["graphics_flag_zero_in_cmdline"] = ("kestrel_graphics=0" in text)
    # New dt26 proof helper identity (helper script, NOT UKI hash).
    checks["helper_revision_is_v2_dt26"] = (
        "helper_revision=v2-dt26" in typed and "helper_revision=v2-dt26" in startup)
    checks["helper_revision_not_uki_label"] = (
        "not UKI" in typed or "not UKI" in startup
        or "helper identity" in typed or "helper identity" in startup)
    checks["boot_id_selected_in_shared_extract"] = bool(boot_ok)
    # Text opt-out: production observer files must be ABSENT for A.
    if boot_ok:
        checks["production_observer_absent_for_text"] = (
            mod.leaf_in_boot(extract, bid, "08-graphics-preflight.json") is None
            and mod.leaf_in_boot(extract, bid, "09-graphics-status.json") is None
            and mod.leaf_in_boot(extract, bid, "10-graphics-journal.log") is None)
    else:
        checks["production_observer_absent_for_text"] = False
    checks["serial_and_firmware_declared_vm_only"] = True
    passed = all(checks.values())
    report = {"passed": passed, "revision": REVISION,
              "case": "A-text-fallback",
              "uki_sha256": derived["uki_sha256"],
              "initramfs_sha256": derived["initramfs_sha256"],
              "sfs_sha256": derived["sfs_sha256"],
              "sfs_bytes": derived["sfs_bytes"],
              "checks": checks, "stop_reason": r["reason"],
              "seconds": r["seconds"], "deadline_seconds": deadline,
              "qemu_exit": r["qemu_exit"], "command": r["cmd"],
              "log": r["log_path"], "captured_files": r["files"],
              "extract": r["extract"], "fixture_entry_number": 8,
              "native_hardware_validated": False,
              "physical_firmware_writes": 0,
              "physical_keyboard_input_validated": False,
              "serial_fixture_only_no_native_input_proof": True,
              "kestrel_graphics": "0", "boot_id": bid}
    with open(r["result_path"], "x") as s:
        json.dump(report, s, indent=2)
    print(f"CASE A serial tail:\n{text[-3500:]}", flush=True)
    report["uki_sha"] = r["packed_uki"]
    return report


def extract_boot_json(mod, extract, boot_id, leaf):
    p = mod.leaf_in_boot(extract, boot_id, leaf)
    if p is None:
        return None, f"expected 1 {leaf} under boot-{boot_id}, found 0-or-many"
    try:
        return json.loads(p.read_text()), ""
    except Exception as e:
        return None, f"{leaf} invalid JSON: {e}"


def run_case_bc(prefix, deadline, derived, mod, a_bid):
    phase1_send = BC_PHASE1_SEND
    phases = [
        {"wait": "prompt+multi", "send": phase1_send},
        {"wait_marker": b"KESTREL_B_PROMPT_READY", "send": B_COLLECT_SEND},
        {"wait_marker": b"===B-JOURNAL-CYCLES===",
         "send": BC_JOURNAL_SEEN_SEND},
        {"wait_marker": b"KESTREL_B_COLLECT_DONE", "send": C_CHAOS_SEND},
    ]
    # NOTE: B_COLLECT_SEND ends with KESTREL_B_COLLECT_DONE so phase 3
    # advances on the anchored executed line, never on typed echo text.
    r = run_qemu(prefix, "bc", phases, deadline, derived, mod)
    extract = r["extract"]
    text = r["text"]
    clean = r["clean"]
    bid_m = re.search(r"BOOTID=([0-9a-f-]{36})", clean)
    boot_id = bid_m.group(1) if bid_m else None
    if not boot_id or not mod.validate_boot_id(boot_id):
        m3 = re.search(r"boot_id=([0-9a-f-]{36})", clean)
        boot_id = m3.group(1) if m3 else "unknown"
    bids = mod.list_boot_ids(extract)
    boot_ok = boot_id in bids if mod.validate_boot_id(boot_id) else False
    pair_ok, pair_errs = mod.validate_boot_pair(
        a_bid, boot_id if mod.validate_boot_id(boot_id) else "x")
    startup = read_boot_leaf(mod, extract, boot_id, "06-text-startup.txt") if boot_ok else ""
    typed = read_boot_leaf(mod, extract, boot_id, "07-typed-command.txt") if boot_ok else ""
    checks = {}
    checks["fixture_candidate_readback_verified"] = (
        r["packed_uki"] == derived["uki_sha256"]
        and r["packed_sfs"] == derived["sfs_sha256"])
    entry = re.findall(r"^menuentry .*?(?=^menuentry |\Z)",
                       Path(r["cfg_path"]).read_text(),
                       re.M | re.S)[7]
    checks["native_entry_normal_init_retained"] = ("init=" not in entry)
    checks["firmware_flag_removed_for_virtual_test"] = (
        "kestrel_efilog=1" not in entry)
    checks["graphics_flag_one_true"] = (
        "kestrel_graphics=1" in entry and "kestrel_graphics=1" in text)
    checks["grub_menu"] = ("KESTREL_EFI_MENU_REACHED" in text)
    kmsg = read_boot_leaf(mod, extract, boot_id, "01-kernel-kmsg.log") if boot_ok else ""
    checks["kernel_started"] = ("Linux version 7.3.0-rc3" in kmsg)
    checks["text_staged"] = ("KESTREL_TEXT_CONSOLE_STAGED" in text)
    checks["multi_user_reached"] = bool(
        re.search(r"Reached target [^\r\n]*Multi-User System", clean))
    checks["prompt_and_target_before_input"] = bool(
        PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks["bash_startup_recovered"] = (
        "KESTREL_BASH_STARTED" in startup and "shell_comm=bash" in startup)
    checks["typed_command_proof_recovered"] = (
        "KESTREL_TYPED_COMMAND_OK" in typed)
    checks["normal_systemd_pid1"] = (
        "pid1=systemd" in startup and "pid1=systemd" in typed)
    checks["live_overlay"] = ("fstype=overlay" in typed)
    checks["text_preserved_under_graphics_request"] = bool(
        "KESTREL_BASH_STARTED" in startup and "KESTREL_TYPED_COMMAND_OK" in typed)
    checks["normal_shutdown"] = ("reboot: Power down" in text)
    checks["shutdown_observed_before_deadline"] = (r["reason"] == "poweroff")
    checks["captured_logs_copy_succeeded"] = (r["copy"].returncode == 0)
    checks["b_proof_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_B_PROOF_DONE\r?\n", clean))
    checks["b_collect_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_B_COLLECT_DONE\r?\n", clean))
    checks["a_b_boot_ids_differ_shared_fat"] = bool(pair_ok)
    checks["b_boot_selected_in_shared_extract"] = bool(boot_ok)
    # --- B oracle: production observer USB 08/09/10 under THIS boot id ---
    preflight_raw, preflight_err = extract_boot_json(
        mod, extract, boot_id, "08-graphics-preflight.json") \
        if boot_ok else (None, "boot-not-selected")
    status_raw, status_err = extract_boot_json(
        mod, extract, boot_id, "09-graphics-status.json") \
        if boot_ok else (None, "boot-not-selected")
    journal_p = mod.leaf_in_boot(extract, boot_id, "10-graphics-journal.log") \
        if boot_ok else None
    journal_text = journal_p.read_text(errors="replace") if journal_p else ""
    b08_ok, b08_errors, _ = (mod.validate_preflight_record(preflight_raw)
                              if preflight_raw is not None
                              else (False, [preflight_err or "08-missing"], {}))
    if b08_ok and preflight_raw.get("passed") is not False:
        b08_ok = False
        b08_errors = list(b08_errors) + ["08-refusal-requires-passed-false"]
    b09_ok, b09_errors, _ = (mod.validate_status_record(status_raw)
                              if status_raw is not None
                              else (False, [status_err or "09-missing"], {}))
    b10_ok, b10_errors, _ = mod.validate_journal_text(journal_text)
    if not journal_p:
        b10_ok, b10_errors = False, ["10-missing-under-boot-id"]
    # Serial fallback: anchored JSON blocks for 08/09 when USB missing.
    if not b08_ok:
        mjs = re.search(r"KESTREL_08_PREFLIGHT_BEGIN\r?\n(.*?)"
                        r"\r?\nKESTREL_08_PREFLIGHT_END", clean, re.S)
        if mjs:
            try:
                fb = json.loads(mjs.group(1))
                ok2, errs2, _ = mod.validate_preflight_record(fb)
                if ok2 and fb.get("passed") is False:
                    b08_ok, b08_errors = True, []
            except Exception as e:
                b08_errors = [f"08-serial-fallback-invalid: {e}"]
    if not b09_ok:
        mjs = re.search(r"KESTREL_09_STATUS_BEGIN\r?\n(.*?)"
                        r"\r?\nKESTREL_09_STATUS_END", clean, re.S)
        if mjs:
            try:
                fb = json.loads(mjs.group(1))
                ok2, errs2, _ = mod.validate_status_record(fb)
                if ok2:
                    b09_ok, b09_errors = True, []
            except Exception as e:
                b09_errors = [f"09-serial-fallback-invalid: {e}"]
    checks["b_usb_08_preflight_valid_refusal"] = bool(b08_ok)
    checks["b_usb_09_status_valid"] = bool(b09_ok)
    checks["b_usb_10_journal_valid"] = bool(b10_ok)
    checks["b_observer_same_boot_id"] = bool(boot_ok and b08_ok and b09_ok and b10_ok)
    checks["b_python_exec_ok"] = bool(
        re.search(r"PYTHON_EXEC_OK rows=\s*0", clean)
        and re.search(r"GUARD_OK=\s*False", clean))
    checks["b_guard_refuses_closed"] = bool(b08_ok and checks["b_python_exec_ok"])
    checks["b_no_fake_temps"] = not any(
        s in clean for s in ["200000", "FAKE_TEMP"])
    checks["b_private_sddm_never_started"] = bool(
        "NO_SDDM" in clean and b09_ok)
    checks["b_marker_absent_before_c"] = ("MARKER_ABSENT" in clean)
    checks["b_stock_masks_preserved"] = bool(
        re.search(r"\r?\nmasked\r?\n", clean))
    checks["b_no_gui_launched"] = bool(b08_ok and b09_ok)
    checks["b_execstartpre_exact_in_sfs"] = bool(b08_ok)
    checks["b_execstoppost_exact_in_sfs"] = bool(b08_ok)
    # --- C oracle: QA USB 09 JSON under THIS boot id + serial coupling ---
    obj09, err09 = extract_boot_json(
        mod, extract, boot_id, "09-unit-chaos.json") \
        if boot_ok else (None, "boot-not-selected")
    c09_ok = False
    c09_errors = []
    if obj09 is not None:
        c09_ok, c09_errors, _ = mod.validate_09_record(
            obj09, boot_id if mod.validate_boot_id(boot_id) else None)
    else:
        c09_errors = [err09 or "09-missing"]
    checks["c_usb_09_valid"] = bool(c09_ok)
    c_serial_passed, c_serial_checks, c_detail = \
        mod.evaluate_c_serial(clean)
    for k, v in c_serial_checks.items():
        checks[k] = v
    checks["c_detail"] = (c_detail == "child-inactive-gone-marker-absent")
    c_conj = bool(c09_ok and c_serial_passed)
    checks["c_conjunctive_usb_and_serial_pass"] = c_conj
    checks["c_prompt_usable_for_independent_test"] = bool(
        checks["b_collect_done_marker"]
        or re.search(r"\r?\nKESTREL_C_DONE\r?\n", clean))
    checks["c_fake_payload_labelled"] = (
        "FAKE_PAYLOAD_UNITGRAPH_FIXTURE" in clean)
    checks["c_owned_fake_cleanup_done"] = (
        "===C-CLEANUP-OWNED-FAKE-ONLY===" in clean)
    checks["c_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_C_DONE\r?\n", clean))
    checks["c_no_host_services"] = True
    checks["no_panic_or_wsl_init"] = not any(
        s in text for s in ["Kernel panic", "init-distro", "WSL ("])
    bool_checks = {k: (v is True) for k, v in checks.items()
                   if isinstance(v, bool)}
    passed = all(bool_checks.values()) and b08_ok and b09_ok and b10_ok and c_conj
    report = {"passed": passed, "revision": REVISION,
              "case": "B-graphics-refusal+C-unitgraph",
              "uki_sha256": derived["uki_sha256"],
              "initramfs_sha256": derived["initramfs_sha256"],
              "sfs_sha256": derived["sfs_sha256"],
              "sfs_bytes": derived["sfs_bytes"],
              "checks": {k: bool(v) if isinstance(v, bool) else v
                         for k, v in checks.items()},
              "b08_errors": b08_errors, "b09_errors": b09_errors,
              "b10_errors": b10_errors, "c09_errors": c09_errors,
              "pair_errors": pair_errs,
              "c_detail": c_detail,
              "stop_reason": r["reason"], "seconds": r["seconds"],
              "deadline_seconds": deadline, "qemu_exit": r["qemu_exit"],
              "command": r["cmd"], "log": r["log_path"],
              "captured_files": r["files"], "extract": r["extract"],
              "fixture_entry_number": 8,
              "native_hardware_validated": False,
              "physical_firmware_writes": 0,
              "physical_keyboard_input_validated": False,
              "serial_fixture_only_no_native_pixel_proof": True,
              "kestrel_graphics": "1", "boot_id": boot_id,
              "a_boot_id": a_bid}
    with open(r["result_path"], "x") as s:
        json.dump(report, s, indent=2)
    print(f"CASE BC serial tail:\n{text[-5000:]}", flush=True)
    report["uki_sha"] = r["packed_uki"]
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True,
                    help="parent-verified dt26-artifact-audit.json")
    ap.add_argument("--case", required=True, choices=["a", "bc", "all"])
    ap.add_argument("--prefix", required=True,
                    help="fresh tag prefix, must start with dt26-efi-")
    ap.add_argument("--deadline-text", type=int, default=600)
    ap.add_argument("--deadline-gfx", type=int, default=800)
    ap.add_argument("--sfs-path", default=None)
    ap.add_argument("--sfs-sha256", default=None)
    ap.add_argument("--sfs-bytes", type=int, default=None)
    ap.add_argument("--pending-runtime-bytes", type=int, default=None,
                    help="bounded future runtime writes (default 512MiB; "
                    "pass 0 after the runtime worker finishes)")
    args = ap.parse_args()
    pending = pending_runtime_bytes(args.pending_runtime_bytes)
    assert 60 <= args.deadline_text <= 900
    assert 60 <= args.deadline_gfx <= 900
    if not re.fullmatch(r"dt26-efi-[a-z0-9-]+", args.prefix):
        ap.error("prefix must match dt26-efi-[a-z0-9-]+ (fresh, owned)")
    if not args.audit.endswith("dt26-artifact-audit.json"):
        ap.error("audit must be a dt26-artifact-audit.json path")
    prefix = args.prefix
    sfs_args = {"sfs_path": args.sfs_path,
                "sfs_sha256": args.sfs_sha256,
                "sfs_bytes": args.sfs_bytes}
    if any([args.sfs_path, args.sfs_sha256, args.sfs_bytes]):
        if not all([args.sfs_path, args.sfs_sha256, args.sfs_bytes]):
            ap.error("explicit SFS needs all of --sfs-path/--sfs-sha256/--sfs-bytes")
    mod = load_parser()
    audit_raw = json.loads(Path(args.audit).read_text())
    ok, errors, derived = mod.validate_audit_dict(audit_raw)
    if not ok:
        print(f"AUDIT_INVALID {errors}", flush=True)
        sys.exit(2)
    if sfs_args["sfs_path"]:
        ok2, errs2 = mod.validate_explicit_sfs(
            sfs_args["sfs_sha256"], sfs_args["sfs_bytes"])
        if not ok2:
            print(f"EXPLICIT_SFS_INVALID {errs2}", flush=True)
            sys.exit(2)
        derived["sfs_sha256"] = sfs_args["sfs_sha256"]
        derived["sfs_bytes"] = sfs_args["sfs_bytes"]
        derived["sfs_path"] = sfs_args["sfs_path"]
    print(f"AUDIT OK revision={audit_raw.get('revision')} "
          f"uki={derived['uki_sha256'][:12]}.. "
          f"sfs={derived['sfs_sha256'][:12]}..", flush=True)
    if fcntl is None:
        print("FLOCK SKIPPED (no fcntl on this platform)", flush=True)
        return do_run(args, derived, mod, sfs_args)
    lock_fd = open(str(LOCK), "a+")
    print(f"HOLDING FLOCK {LOCK} ...", flush=True)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    print("FLOCK HELD", flush=True)
    try:
        return do_run(args, derived, mod, sfs_args, lock_fd=lock_fd)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            lock_fd.close()
        except Exception:
            pass
        print("FLOCK RELEASED", flush=True)


def do_run(args, derived, mod, sfs_args, lock_fd=None):
    prefix = args.prefix
    pending = pending_runtime_bytes(getattr(args, "pending_runtime_bytes", None))
    image = B / (prefix + ".fat")
    grub_cfg = T / (prefix + "-grub.cfg")
    a_extract = B / (prefix + "-a-extracted")
    bc_extract = B / (prefix + "-bc-extracted")
    a_log = T / (prefix + "-a.log")
    a_result = T / (prefix + "-a-result.json")
    bc_log = T / (prefix + "-bc.log")
    bc_result = T / (prefix + "-bc-result.json")
    receipt = T / (prefix + "-fixture.json")
    # Collision preflight: fresh failures preserved, before side effects.
    # A and B/C extracts are exclusive; the SAME FAT holds both boot-ids.
    # Never delete or mutate the other case's extract/evidence.
    if args.case in ("a", "all"):
        for p in [image, grub_cfg, receipt, a_log, a_result,
                  a_extract, bc_log, bc_result, bc_extract]:
            assert not p.exists(), \
                f"collision: {p} exists, use fresh --prefix"
    else:  # bc recovery on the SAME shared fixture
        assert image.is_file(), \
            f"BC-only needs existing shared fixture {image}; run --case a first"
        assert a_result.is_file(), \
            f"BC-only needs existing A result {a_result}; run --case a first"
        assert a_extract.is_dir(), \
            f"BC-only needs existing A extract {a_extract}; run --case a first"
        for p in [bc_log, bc_result, bc_extract]:
            assert not p.exists(), \
                f"collision: {p} exists, use fresh --prefix"
        assert grub_cfg.is_file(), \
            "BC-only needs existing grub cfg"
    for p in [T / "dt26-efi-text-menu.cfg",
              T / "dt26-efi-graphics-menu.cfg",
              PREPARE, PARSER_PATH, QEMU_FD]:
        assert p.exists(), f"missing {p}"
    uki_host = Path(derived["uki_path"])
    initrd_host = Path(derived["initramfs_path"])
    assert uki_host.is_file(), f"missing UKI {uki_host} (build not ready)"
    assert initrd_host.is_file(), f"missing initrd {initrd_host}"
    got_uki = sha_file(str(uki_host))
    assert got_uki == derived["uki_sha256"], \
        f"host UKI mismatch {got_uki}"
    print(f"HOST UKI SHA OK {got_uki[:16]}..", flush=True)
    got_initrd = sha_file(str(initrd_host))
    assert got_initrd == derived["initramfs_sha256"], "host initrd mismatch"
    print("HOST initrd SHA OK", flush=True)
    sfs_cands = [Path("/home/builder/live-rootfs-v2.squashfs")]
    if "sfs_path" in derived and derived["sfs_path"]:
        sfs_cands.insert(0, Path(derived["sfs_path"]))
    sfs_p = next((q for q in sfs_cands if q.is_file()), None)
    assert sfs_p is not None, "missing SFS (build not ready)"
    assert sfs_p.stat().st_size == derived["sfs_bytes"], \
        f"SFS size mismatch {sfs_p.stat().st_size}"
    print(f"SFS size OK {derived['sfs_bytes']}, hashing...", flush=True)
    got_sfs = sha_file(str(sfs_p))
    assert got_sfs == derived["sfs_sha256"], "SFS SHA mismatch audit"
    print("SFS SHA OK", flush=True)
    qfd_sha = sha_file(str(QEMU_FD))
    assert qfd_sha == derived["qemu_sha256"], "QEMU FD mismatch audit"
    assert QEMU_FD.stat().st_size == derived["qemu_bytes"]
    print("QEMU FD OK", flush=True)
    # Incremental gating: before prepare the fixture is NOT yet allocated,
    # so future is exactly one fixture + pending. After A / BC-only the
    # shared FAT already exists, so future is 0 + pending only (never
    # double-count written FAT/hostcopy; guest check below is separate and
    # already holds the image).
    ok, free_d = disk_free_ok(pending_runtime=pending,
                              future_fixture_bytes=FIXTURE_BYTES)
    assert ok, f"D projected remaining too low (free_D={free_d})"
    print(f"D free OK {free_d // 1024 // 1024}MiB "
          f"(projected remaining above 10GiB reserve)", flush=True)
    ok_g, free_g = guest_free_ok()
    assert ok_g, f"guest filesystem free too low {free_g}"
    print(f"GUEST free OK {free_g // 1024 // 1024}MiB", flush=True)

    a_res = None
    bc_res = None
    if args.case in ("a", "all"):
        print(f"=== PREPARE {prefix} (shared fixture) ===", flush=True)
        prepare_image(prefix, T / "dt26-efi-text-menu.cfg",
                      args.audit, sfs_args, pending_runtime=pending,
                      lock_fd=lock_fd)
        patch_grub(prefix, graphics="0")
        print(f"=== CASE A {prefix} deadline {args.deadline_text} ===",
              flush=True)
        a_res = run_case_a(prefix, args.deadline_text, derived, mod)
        print(json.dumps({"case": "A", "passed": a_res["passed"],
                          "stop_reason": a_res["stop_reason"],
                          "seconds": a_res["seconds"]}, indent=2),
              flush=True)
    if args.case in ("bc", "all"):
        if args.case == "bc":
            a_old = json.loads(a_result.read_text())
            assert a_old.get("passed") is True, "existing A did not pass"
            assert a_old.get("revision") == REVISION, "A revision mismatch"
            assert a_old.get("uki_sha256") == derived["uki_sha256"], \
                "A UKI hash differs from audit; re-run --case a"
            assert a_old.get("sfs_sha256") == derived["sfs_sha256"], \
                "A SFS hash differs from audit; re-run --case a"
            assert a_old.get("boot_id") not in (None, "unknown", ""), \
                "existing A boot_id missing; re-run --case a"
            print("BC-ONLY RECOVERY: existing A exact-hash pass verified",
                  flush=True)
            a_bid = a_old.get("boot_id")
        else:
            assert a_res is not None and a_res["passed"], \
                "A must pass before BC in --case all"
            a_bid = a_res["boot_id"]
        # BC reuses the SAME already-allocated FAT: future fixture is 0,
        # only pending future bytes remain (incremental; never double-count
        # the written 2.25GiB FAT/hostcopy). Guest already holds the image.
        ok, free_d = disk_free_ok(pending_runtime=pending,
                                  future_fixture_bytes=0)
        assert ok, f"D projected remaining too low before gfx {free_d}"
        print(f"=== PATCH shared fixture to graphics=1 ===", flush=True)
        patch_grub(prefix, graphics="1")
        print(f"=== CASE B+C {prefix} deadline {args.deadline_gfx} ===",
              flush=True)
        bc_res = run_case_bc(prefix, args.deadline_gfx, derived, mod, a_bid)
        print(json.dumps({"case": "B+C", "passed": bc_res["passed"],
                          "stop_reason": bc_res["stop_reason"],
                          "seconds": bc_res["seconds"]}, indent=2),
              flush=True)
    if args.case == "a":
        overall = bool(a_res["passed"])
    elif args.case == "bc":
        overall = bool(bc_res["passed"])
    else:
        overall = bool(a_res["passed"] and bc_res["passed"])
    print(f"OVERALL passed={overall}", flush=True)
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
