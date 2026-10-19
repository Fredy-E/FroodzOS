#!/usr/bin/env python3
"""Build ONE fresh bounded 2.25GiB FAT32 EFI fixture for dt26 (v2-dt26).

Creates exactly one image reused SEQUENTIALLY for A then B/C (no second
FAT, no reuse/mutation of old dt25b FATs, no deletion of old boot Logs).
Revision-aware: --audit must be an explicit parent-verified
dt26-artifact-audit.json (revision v2-dt26, passed true); expected UKI /
initrd / SFS hashes+sizes come from the audit, or from explicit gated
--sfs-* tokens. Absent/malformed/mismatched audit or artifacts refuse
BEFORE any allocation. All outputs are preflighted exclusive before side
effects; every failed attempt is kept, never cleaned.

Layout (2.25GiB = 9*1024**3//4, partition offset 1MiB):
  image:  /home/builder/boot-failure-tests/<prefix>.fat
  grub:   testing/boot-failure/<prefix>-grub.cfg  (local copy of --menu)
  receipt: testing/boot-failure/<prefix>-fixture.json (exclusive)

Payload: EFI/Linux/kestrel-live.efi (audit UKI) + arch/aarch64/airootfs.sfs
(audit SFS) + boot/grub/grub.cfg + KESTREL-LOG-TARGET marker + GRUB AA64.
FAT UKI/SFS readback must equal the audit before returning.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
B = Path("/home/builder/boot-failure-tests")
LOCK = B / "dt25-build.lock"

REVISION = "v2-dt26"
FIXTURE_BYTES = 9 * 1024 ** 3 // 4  # 2415919104 (2.25GiB)
PART_START = 2048  # 1MiB offset at 512B sectors
# Legacy estimate of already-present build/hostcopy bytes: audit artifacts
# must already exist by fixture time, so this is NOT counted as future
# bytes in the capacity formula (kept for provenance only).
HOSTCOPY_HEADROOM = 733107104  # already present by fixture time; not future
RUNTIME_SIBLING_CAP = 512 * 1024 ** 2  # default pending-runtime budget
RESERVE_BYTES = 10 * 1024 ** 3
PHYSICAL_D = "/mnt/d"
PARSER_PATH = T / "dt26-efi-parser.py"


def pending_runtime_bytes(cli_value=None):
    """Bounded pending-runtime budget (future bytes only, default 512MiB).

    Parent may pass --pending-runtime-bytes 0 once the runtime worker has
    finished and no further runtime writes are pending. Env
    DT26_PENDING_RUNTIME_BYTES overrides the default when the CLI flag is
    absent. Never negative.
    """
    if cli_value is not None:
        v = int(cli_value)
        assert v >= 0, "pending-runtime must be >= 0"
        return v
    env = os.environ.get("DT26_PENDING_RUNTIME_BYTES")
    if env is not None and env != "":
        v = int(env)
        assert v >= 0, "pending-runtime must be >= 0"
        return v
    return RUNTIME_SIBLING_CAP


def capacity_plan(free_d, pending_runtime, future_fixture_bytes=FIXTURE_BYTES):
    """Return (future_bytes, projected_remaining). Future = fixture + pending.

    future_fixture_bytes is explicit planned allocation: pass FIXTURE_BYTES
    before prepare (fixture not yet allocated), 0 after A / for BC-only
    (fixture already exists, only pending future bytes remain).
    """
    future = int(future_fixture_bytes) + int(pending_runtime)
    return future, free_d - future


def check_d_capacity(free_d, pending_runtime, future_fixture_bytes=FIXTURE_BYTES):
    """True only when projected remaining D free stays above reserve.

    Formula: remaining = free_D - (future_fixture_bytes + pending_runtime);
    require free_d > future AND remaining > 10GiB. The legacy
    HOSTCOPY_HEADROOM is already present by fixture time and is NOT
    counted as future bytes. Never double-counts written hostcopy/FAT.
    """
    future, remaining = capacity_plan(free_d, pending_runtime, future_fixture_bytes)
    return (free_d > future and remaining > RESERVE_BYTES), future, remaining


LOCK_ENV_FD = "DT26_LOCK_FD"


def _resolve_lock_path(lock_path=None):
    if lock_path is None:
        return LOCK
    from pathlib import Path as _P
    return _P(lock_path)


def validate_inherited_fd(fd_num, lock_path=None):
    """Validate a supplied inherited lock FD against the real lock file.

    Requires: fd is open, regular file, dev/inode equals the lock path,
    and LOCK_EX|LOCK_NB reaffirm succeeds (fake/wrong-FD or foreign-holder
    fails). Never infers inheritance from contention alone.
    """
    import fcntl as _fcntl
    import os as _os
    import stat as _stat
    lp = _resolve_lock_path(lock_path)
    try:
        n = int(fd_num.fileno()) if hasattr(fd_num, "fileno") else int(fd_num)
    except Exception as exc:
        raise OSError(f"inherited lock fd invalid ({fd_num!r}): {exc}")
    try:
        st_fd = _os.fstat(n)
    except OSError as exc:
        raise OSError(f"inherited lock fd {n} not open: {exc}")
    if not _stat.S_ISREG(st_fd.st_mode):
        raise OSError(f"inherited lock fd {n} not regular file")
    try:
        st_path = _os.stat(str(lp))
    except OSError as exc:
        raise OSError(f"lock path {lp} stat failed: {exc}")
    if (st_fd.st_dev, st_fd.st_ino) != (st_path.st_dev, st_path.st_ino):
        raise OSError(f"inherited lock fd {n} dev/inode mismatch vs {lp}")
    try:
        _fcntl.flock(n, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        raise OSError(f"inherited lock fd {n} contended/foreign holder: {exc}")
    return n


def acquire_dt25_lock(lock_path=None, inherited_fd=None):
    """Acquire the shared dt25-build.lock with validated inheritance only.

    Standalone path MUST take LOCK_EX|LOCK_NB or refuse (raise) before any
    allocation. Contention without a validated inherited FD is NEVER treated
    as parent inheritance. Unsupported fcntl / errors refuse before
    allocation. When called as a subprocess of the harness that already holds
    the lock, the caller MUST pass a validated inherited FD explicitly (via
    DT26_LOCK_FD + pass_fds) or call this helper under the verified hold;
    fake/wrong-FD or foreign-holder fails. Never unlinks the lock.
    Returns an owned handle (standalone) or a borrowed handle (validated
    inherited, must not LOCK_UN the shared OFD). Use release_dt25_lock().
    """
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover (non-POSIX runner)
        raise OSError(f"fcntl unavailable, refusing lock before allocation: {exc}")
    import os
    lp = _resolve_lock_path(lock_path)
    if inherited_fd is None:
        env = os.environ.get(LOCK_ENV_FD)
        if env not in (None, ""):
            try:
                inherited_fd = int(env)
            except ValueError as exc:
                raise OSError(f"{LOCK_ENV_FD}={env!r} invalid: {exc}")
    if inherited_fd is not None:
        n = validate_inherited_fd(inherited_fd, lp)
        print(f"VALIDATED INHERITED FLOCK {lp} fd={n} ...", flush=True)
        dup = os.dup(n)
        f = os.fdopen(dup, "a+")
        f._dt26_owned = False
        f._dt26_inherited_num = n
        return f
    fd = open(str(lp), "a+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(f"HOLDING FLOCK {lp} (prepare) ...", flush=True)
        fd._dt26_owned = True
        return fd
    except (BlockingIOError, OSError) as exc:
        try:
            fd.close()
        except Exception:
            pass
        raise OSError(
            f"lock contended, refusing before allocation "
            f"(no validated inherited fd): {exc}")


def release_dt25_lock(handle):
    """Release a handle from acquire_dt25_lock.

    Standalone owner: LOCK_UN + close. Borrowed validated-inherited handle:
    close ONLY the child references, never LOCK_UN the shared inherited OFD
    (would unlock the parent). Never unlinks the lock file.
    """
    if handle is None:
        return
    try:
        import fcntl as _fcntl
    except ImportError:  # pragma: no cover
        try:
            handle.close()
        except Exception:
            pass
        return
    try:
        owned = bool(getattr(handle, "_dt26_owned", True))
    except Exception:
        owned = True
    if owned:
        try:
            _fcntl.flock(handle, _fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass
        try:
            print(f"FLOCK RELEASED {LOCK} (prepare)", flush=True)
        except Exception:
            pass
    else:
        inherited = getattr(handle, "_dt26_inherited_num", None)
        try:
            handle.close()
        except Exception:
            pass
        if inherited is not None:
            import os as _os
            try:
                _os.close(int(inherited))
            except Exception:
                pass


def load_parser():
    spec = importlib.util.spec_from_file_location(
        "dt26_efi_parser", str(PARSER_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            c = f.read(16 * 1024 * 1024)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def mtype_hash(fs, fat_path):
    reader = subprocess.Popen(
        ["mtype", "-i", fs, fat_path], stdout=subprocess.PIPE)
    h = hashlib.sha256()
    while True:
        chunk = reader.stdout.read(16 * 1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    rc = reader.wait()
    assert rc == 0, f"mtype {fat_path} failed rc={rc}"
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True,
                    help="parent-verified dt26-artifact-audit.json")
    ap.add_argument("--prefix", required=True,
                    help="fresh tag, must match dt26-efi-[a-z0-9-]+")
    ap.add_argument("--menu", required=True,
                    help="local dt26 grub menu template")
    ap.add_argument("--sfs-path", default=None)
    ap.add_argument("--sfs-sha256", default=None)
    ap.add_argument("--sfs-bytes", type=int, default=None)
    ap.add_argument("--pending-runtime-bytes", type=int, default=None,
                    help="bounded future runtime writes (default 512MiB; "
                    "pass 0 after the runtime worker finishes)")
    args = ap.parse_args()
    pending = pending_runtime_bytes(args.pending_runtime_bytes)

    if not re.fullmatch(r"dt26-efi-[a-z0-9-]+", args.prefix):
        ap.error("prefix must match dt26-efi-[a-z0-9-]+ (fresh, owned)")
    if not args.audit.endswith("dt26-artifact-audit.json"):
        ap.error("audit must be a dt26-artifact-audit.json path")

    mod = load_parser()
    audit_raw = json.loads(Path(args.audit).read_text())
    ok, errors, derived = mod.validate_audit_dict(audit_raw)
    if not ok:
        print(f"AUDIT_INVALID {errors}", flush=True)
        sys.exit(2)

    sfs_sha = derived["sfs_sha256"]
    sfs_bytes = derived["sfs_bytes"]
    sfs_p = None
    if args.sfs_path or args.sfs_sha256 is not None or args.sfs_bytes is not None:
        if not (args.sfs_path and args.sfs_sha256 and args.sfs_bytes):
            print("EXPLICIT_SFS_INCOMPLETE need all of --sfs-path/--sfs-sha256/--sfs-bytes",
                  flush=True)
            sys.exit(2)
        ok2, errs2 = mod.validate_explicit_sfs(args.sfs_sha256, args.sfs_bytes)
        if not ok2:
            print(f"EXPLICIT_SFS_INVALID {errs2}", flush=True)
            sys.exit(2)
        sfs_sha = args.sfs_sha256
        sfs_bytes = args.sfs_bytes
        sfs_p = Path(args.sfs_path)
    else:
        if "sfs_path" in derived and derived["sfs_path"]:
            sfs_p = Path(derived["sfs_path"])
    print(f"AUDIT OK revision={audit_raw.get('revision')} "
          f"uki={derived['uki_sha256'][:12]}.. sfs={sfs_sha[:12]}..", flush=True)

    image = B / (args.prefix + ".fat")
    grub_copy = T / (args.prefix + "-grub.cfg")
    receipt = T / (args.prefix + "-fixture.json")
    menu_src = Path(args.menu)

    # Collision preflight: exclusive before ANY side effect.
    for p in (image, grub_copy, receipt):
        assert not p.exists(), f"collision: {p} exists, use fresh --prefix"
    assert menu_src.is_file(), f"missing menu template {menu_src}"
    assert PARSER_PATH.is_file(), "missing dt26 parser"

    # Host artifact source checks (before allocation).
    uki_host = Path(derived["uki_path"])
    initrd_host = Path(derived["initramfs_path"])
    assert uki_host.is_file(), f"missing UKI {uki_host} (build not ready)"
    assert initrd_host.is_file(), f"missing initrd {initrd_host}"
    got_uki = sha_file(str(uki_host))
    assert got_uki == derived["uki_sha256"], f"host UKI mismatch {got_uki}"
    print(f"HOST UKI SHA OK {got_uki[:16]}..", flush=True)
    got_initrd = sha_file(str(initrd_host))
    assert got_initrd == derived["initramfs_sha256"], "host initrd mismatch"
    print("HOST initrd SHA OK", flush=True)
    sfs_cands = [Path("/home/builder/live-rootfs-v2.squashfs")]
    if sfs_p is not None:
        sfs_cands.insert(0, sfs_p)
    sfs_host = next((q for q in sfs_cands if q.is_file()), None)
    assert sfs_host is not None, "missing SFS (build not ready)"
    assert sfs_host.stat().st_size == sfs_bytes, (
        f"SFS size mismatch {sfs_host.stat().st_size} != {sfs_bytes}")
    print(f"SFS size OK {sfs_bytes}, hashing...", flush=True)
    got_sfs = sha_file(str(sfs_host))
    assert got_sfs == sfs_sha, "SFS SHA mismatch audit/explicit"
    print("SFS SHA OK", flush=True)

    # Payload capacity: UKI+SFS must fit the bounded fixture with margin.
    uki_bytes = uki_host.stat().st_size
    if derived.get("uki_bytes") and derived["uki_bytes"] != uki_bytes:
        print(f"UKI size differs audit={derived['uki_bytes']} host={uki_bytes}",
              flush=True)
        sys.exit(2)
    margin = 32 * 1024 ** 2
    assert uki_bytes + sfs_bytes < FIXTURE_BYTES - margin, (
        f"payload {uki_bytes + sfs_bytes} exceeds fixture {FIXTURE_BYTES}")
    print(f"PAYLOAD OK uki={uki_bytes} sfs={sfs_bytes} "
          f"fixture={FIXTURE_BYTES}", flush=True)

    # D free guard BEFORE any allocation: physical D only, projected
    # remaining after ALL future writes must stay above the 10GiB reserve.
    # Capacity formula: remaining = free_D - (future_fixture + pending).
    # Before prepare the fixture is NOT yet allocated, so future_fixture is
    # exactly one FIXTURE_BYTES (explicit). HOSTCOPY_HEADROOM is already
    # present by fixture time (audit artifacts must exist) and is NOT
    # double-counted as future bytes.
    free_d = shutil.disk_usage(PHYSICAL_D).free
    ok_cap, future_need, remaining = check_d_capacity(
        free_d, pending, FIXTURE_BYTES)
    assert ok_cap, (
        f"D projected remaining {remaining} <= reserve {RESERVE_BYTES} "
        f"(free_D={free_d} future={future_need} "
        f"fixture={FIXTURE_BYTES} pending={pending})")
    print(f"D free OK {free_d // 1024 // 1024}MiB "
          f"(fixture {FIXTURE_BYTES // 1024 // 1024}MiB + "
          f"pending {pending // 1024 // 1024}MiB; "
          f"projected remaining {remaining // 1024 // 1024}MiB "
          f"reserve {RESERVE_BYTES // 1024 // 1024}MiB)", flush=True)
    # Guest filesystem must separately hold the fixture image itself.
    try:
        free_guest = shutil.disk_usage(str(B)).free
        assert free_guest > FIXTURE_BYTES, (
            f"guest filesystem free {free_guest} cannot hold fixture "
            f"{FIXTURE_BYTES}")
        print(f"GUEST free OK {free_guest // 1024 // 1024}MiB", flush=True)
    except AssertionError:
        raise
    except Exception as exc:
        print(f"GUEST free check skipped ({exc}); D guard is authoritative",
              flush=True)

    # Shared build lock with validated inheritance only (standalone must
    # take EX|NB or refuse; never infer from contention). Hold across ALL
    # format/copy; never unlink. Borrowed handle closes only, owned UN+close.
    _lock_fd = acquire_dt25_lock()

    # Allocate + partition (1MiB offset) + FAT32.
    # Lock is held across the entire critical section (no unlink, no early
    # release); release happens in the finally below via release_dt25_lock.
    try:
        try:
            with image.open("xb") as f:
                f.truncate(FIXTURE_BYTES)
            subprocess.run(["sfdisk", str(image)],
                           input="label: dos\nunit: sectors\n\nstart=2048, type=c, bootable\n",
                           text=True, check=True, capture_output=True)
            info = json.loads(subprocess.run(
                ["sfdisk", "--json", str(image)],
                check=True, text=True, capture_output=True).stdout)["partitiontable"]
            part = info["partitions"][0]
            assert part["start"] == PART_START and part["type"] == "c", (
                f"unexpected partition {part}")
            offset = part["start"] * info["sectorsize"]
            assert offset == 1024 * 1024, f"offset must be 1MiB, got {offset}"
            fs = str(image) + "@@" + str(offset)
            subprocess.run(["mformat", "-i", fs, "-T", str(part["size"]),
                            "-F", "-v", "KESTREL_A64", "::"], check=True)
            for directory in ["::/EFI", "::/EFI/BOOT", "::/EFI/Linux",
                              "::/arch", "::/arch/aarch64", "::/boot",
                              "::/boot/grub", "::/Logs", "::/notes"]:
                subprocess.run(["mmd", "-i", fs, directory], check=True)
            marker = T / "log-option/KESTREL-LOG-TARGET"
            assert marker.is_file(), f"missing log marker {marker}"
            assert marker.read_text().strip() == "KESTREL_A64_USB_CAPTURE_V1"
            grub_src = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure/"
                            "control-reference/EFI/boot/grubaa64.efi")
            assert grub_src.is_file(), f"missing GRUB AA64 {grub_src}"
            for source, dest in [
                (grub_src, "::/EFI/BOOT/BOOTAA64.EFI"),
                (str(uki_host), "::/EFI/Linux/kestrel-live.efi"),
                (str(sfs_host), "::/arch/aarch64/airootfs.sfs"),
                (str(marker), "::/KESTREL-LOG-TARGET"),
            ]:
                subprocess.run(["mcopy", "-i", fs, source, dest], check=True)
            cfg = menu_src.read_text()
            grub_copy.write_text(cfg)
            subprocess.run(["mcopy", "-i", fs, str(grub_copy),
                            "::/boot/grub/grub.cfg"], check=True)
            assert subprocess.check_output(
                ["mtype", "-i", fs, "::/boot/grub/grub.cfg"]).decode() == cfg
            got_fat_uki = mtype_hash(fs, "::/EFI/Linux/kestrel-live.efi")
            assert got_fat_uki == derived["uki_sha256"], (
                f"FAT UKI mismatch {got_fat_uki}")
            got_fat_sfs = mtype_hash(fs, "::/arch/aarch64/airootfs.sfs")
            assert got_fat_sfs == sfs_sha, "FAT SFS mismatch"
            print(f"FAT READBACK OK {args.prefix} uki+sfs match", flush=True)
        except Exception:
            print(f"FIXTURE FAILED, keeping partial evidence {image} for review",
                  flush=True)
            raise

        with receipt.open("x") as s:
            json.dump({"revision": REVISION, "prefix": args.prefix,
                       "image": str(image), "bytes": FIXTURE_BYTES,
                       "offset": 1024 * 1024,
                       "uki_sha256": derived["uki_sha256"],
                       "initramfs_sha256": derived["initramfs_sha256"],
                       "sfs_sha256": sfs_sha, "sfs_bytes": sfs_bytes,
                       "menu": str(menu_src), "grub_copy": str(grub_copy)},
                      s, indent=2)
        print(f"FIXTURE OK {image}", flush=True)
    finally:
        # Always release (owned UN+close, borrowed close-only, never unlink,
        # never UN shared inherited OFD). Held across all format/copy above.
        try:
            release_dt25_lock(_lock_fd)
        except Exception:
            pass


if __name__ == "__main__":
    main()
