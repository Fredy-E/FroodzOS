#!/usr/bin/env python3
"""Exact-artifact provenance auditor for dt26 (preparation-only).

Traces every packing path from builder/build-live-uki.sh and
builder/initcpio/install|hooks/* (never invents names): packed /init (no
WSL), module/provider/NLS contracts, copied helpers/units/policy, frozen
config/Image/DTB/SFS. Covers the changed root logger
(builder/diagnostics/kestrel-root-log.sh) which old logger-pair checks
omitted, plus text proof/bashrc, supervisor, guard/gates, private SDDM,
parent/child units.

CLI contract:
  audit-dt26-artifacts.py --source-manifest <manifest.json> --tag <tag>
      --audit-dir /home/builder/boot-failure-tests/dt26-audit-<tag>
      [--host-copy /mnt/d/.../dt26-candidate-<tag>.efi]

--tag must match build-dt26-live.py (OUT=/home/builder/uki-v2-dt26-<tag>).
--audit-dir must be fresh; the audit file is always
  <audit-dir>/dt26-artifact-audit.json (suffix required). No
  <audit-dir>/dt26-candidate.efi is written (the built UKI in OUT is the
  artifact; a redundant local clone is not a future write).
--host-copy (optional) must be a NEW tagged path under /mnt/d; its actual
  projected bytes (UKI size) are counted in the D budget. After all checks
  pass, the UKI bytes are copied there with flush+fsync and hashed back
  (readback must match) BEFORE the passed receipt is written.

Manifest schema is identical to build-dt26-live.py: revision exactly
"v2-dt26", approved_for_build boolean true, spec_review/quality_review
"PASS", sources covering every REQUIRED_SOURCES entry with literal
path (exactly equal to key)/sha256(fullmatch, no LF)/bytes; literals
validated BEFORE lookup (extra keys refused), actual sources hashed
at execution. Absent/false manifest or missing artifacts refuse BEFORE any
extraction/copy effects.

Report schema (minimum): revision "v2-dt26", passed bool,
uki_path/sha256/bytes, initramfs_path/sha256/bytes, sfs_path (canonical
private build root)/sha256/bytes, sfs_required_paths_present true,
sfs_runtime_closure_proven false + sfs_runtime_proof_pending_vm true,
qemu_firmware{path,sha256,bytes}, guard_policy{passed,
required_sensor_count 20}, sources/provenance,
native_hardware_validated false (+ native/native_graphics false).
The receipt is written ONCE, atomically exclusive, only after all
copy/flush/readback steps succeed; any copy/readback failure leaves NO
passed receipt (failed fresh dirs are preserved as evidence, never
auto-cleaned, never rewritten after the fact).
Canonical SFS: /home/builder/live-rootfs-v2.squashfs (frozen full hash is
the oracle). The old staged copy under live-staging-v2, if present, is
checked only as optional preservation, never as the audited path.
imgroot pacman versions are auxiliary reference-only (mutable), never a
gate on the frozen SFS.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
LOCK = Path("/home/builder/boot-failure-tests/dt25-build.lock")
K = Path("/home/builder/src/ksrc")
ROOT = Path("/home/builder/imgroot")
SFS = Path("/home/builder/live-rootfs-v2.squashfs")
STAGED_SFS = Path("/mnt/d/CachyOS-ARM64/live-staging-v2/arch/aarch64/airootfs.sfs")
OLD_OUT = Path("/home/builder/uki-v2-dt24")
FAILED_OUT = Path("/home/builder/uki-v2-dt25")
FAILED_CANDIDATE = T / "dt25-candidate.efi"
OLD_CANDIDATE = T / "dt24-candidate.efi"
DT25B_CANDIDATE = T / "dt25b-candidate.efi"

REVISION = "v2-dt26"
RESERVE_BYTES = 10 * 1024**3
FAT_FUTURE_BYTES = int(2.25 * 1024**3)
EXTRACT_NEW_CAP_BYTES = 1 * 1024**3
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_SOURCES = (
    "builder/build-live-uki.sh",
    "builder/validate-live-initramfs.py",
    "builder/platform_graphics_gate.py",
    "builder/platform_usb_gate.py",
    "builder/platform_input_gate.py",
    "builder/initcpio/hooks/kestrel_graphics",
    "builder/initcpio/hooks/kestrel_text",
    "builder/initcpio/hooks/kestrel_log",
    "builder/initcpio/hooks/kestrel_efilog",
    "builder/initcpio/install/kestrel_graphics",
    "builder/initcpio/install/kestrel_text",
    "builder/initcpio/install/kestrel_log",
    "builder/initcpio/install/kestrel_efilog",
    "builder/initcpio/install/kestrel_firmware",
    "builder/initcpio/install/filesystems",
    "builder/diagnostics/kestrel-graphics-supervisor.py",
    "builder/diagnostics/kestrel_graphics_guard.py",
    "builder/diagnostics/kestrel-graphics-env.conf",
    "builder/diagnostics/kestrel-graphics-policy.json",
    "builder/diagnostics/kestrel-graphics.service",
    "builder/diagnostics/kestrel-graphics-sddm.service",
    "builder/diagnostics/kestrel-graphics-tty2.conf",
    "builder/diagnostics/kestrel-text-login.sh",
    "builder/diagnostics/kestrel-text-proof.sh",
    "builder/diagnostics/kestrel-text-bashrc",
    "builder/diagnostics/kestrel-text-getty.conf",
    "builder/diagnostics/kestrel-init-log.sh",
    "builder/diagnostics/kestrel-root-log.sh",
    "builder/diagnostics/kestrel-pid1.sh",
    "builder/diagnostics/kestrel-usb-log.service",
    "builder/diagnostics/kestrel-checkpoint.c",
)

# (packed relative path, project source rel) — traced from install/* add_file
# lines. Binary checkpoint is provenance-only (compiled, not byte-copied).
PACKED_PROVENANCE = (
    ("hooks/kestrel_graphics", "builder/initcpio/hooks/kestrel_graphics"),
    ("hooks/kestrel_text", "builder/initcpio/hooks/kestrel_text"),
    ("hooks/kestrel_log", "builder/initcpio/hooks/kestrel_log"),
    ("hooks/kestrel_efilog", "builder/initcpio/hooks/kestrel_efilog"),
    ("etc/kestrel-graphics-supervisor", "builder/diagnostics/kestrel-graphics-supervisor.py"),
    ("etc/kestrel-graphics-guard", "builder/diagnostics/kestrel_graphics_guard.py"),
    ("etc/kestrel-graphics-env", "builder/diagnostics/kestrel-graphics-env.conf"),
    ("etc/kestrel-graphics-policy", "builder/diagnostics/kestrel-graphics-policy.json"),
    ("etc/kestrel-graphics-service", "builder/diagnostics/kestrel-graphics.service"),
    ("etc/kestrel-graphics-sddm", "builder/diagnostics/kestrel-graphics-sddm.service"),
    ("etc/kestrel-graphics-tty2", "builder/diagnostics/kestrel-graphics-tty2.conf"),
    ("etc/kestrel-text-login", "builder/diagnostics/kestrel-text-login.sh"),
    ("etc/kestrel-text-proof", "builder/diagnostics/kestrel-text-proof.sh"),
    ("etc/kestrel-text-bashrc", "builder/diagnostics/kestrel-text-bashrc"),
    ("etc/kestrel-text-getty.conf", "builder/diagnostics/kestrel-text-getty.conf"),
    ("usr/bin/kestrel-init-log", "builder/diagnostics/kestrel-init-log.sh"),
    ("usr/bin/kestrel-root-log", "builder/diagnostics/kestrel-root-log.sh"),
    ("usr/bin/kestrel-pid1", "builder/diagnostics/kestrel-pid1.sh"),
    ("etc/kestrel-usb-log.service", "builder/diagnostics/kestrel-usb-log.service"),
)

EXP_OLD_UKI_SHA = "4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02"
EXP_FAILED_UKI_SHA = "9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb"
EXP_DT25B_UKI_SHA = "b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753"
EXP_SFS_SHA = "5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c"
EXP_SFS_SIZE = 1748525056
EXP_IMAGE_SHA = "682273a91f2016b9d5484857639bd043e021b961d7f4cfd385a09566b2df3abc"
EXP_IMAGE_SIZE = 52492800
EXP_DTB_SHA = "f5f67c13bdfe975998b083ac06465c36231c0bae205e8e60fff99832264f5232"
EXP_DTB_SIZE = 207772
EXP_QEMU_SHA = "a996c72d5258dabf5fcb11a64bd22e0cc6673e3d193031feea02ac643f16dad5"
EXP_QEMU_SIZE = 3145728


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def sha_file(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_planned_bytes(host_copy_bytes=0):
    """Future writes only: new-only extract cap + one future 2.25GiB FAT.

    The built UKI in OUT is already an artifact (not a future write), and
    no audit_dir/dt26-candidate.efi clone is created. An optional host copy
    counts its actual projected bytes (0 when not requested).
    """
    return EXTRACT_NEW_CAP_BYTES + FAT_FUTURE_BYTES + int(host_copy_bytes)


def write_host_copy(src_data, dest):
    """Exclusive host copy with flush+fsync and readback verification.

    Writes src_data to dest via open('xb') (refuses if exists), flushes,
    fsyncs, then reads back and verifies sha256 + size. Returns the copy
    record dict. Any failure propagates with NO receipt written.
    """
    dest = Path(dest)
    with dest.open("xb") as f:
        f.write(src_data)
        f.flush()
        os.fsync(f.fileno())
    back = sha_file(dest)
    want = hashlib.sha256(src_data).hexdigest()
    if back != want:
        fail("host candidate readback hash mismatch")
    if dest.stat().st_size != len(src_data):
        fail("host candidate readback size mismatch")
    return {"path": str(dest), "sha256": back,
            "bytes": dest.stat().st_size, "readback_verified": True}


def commit_audit_report(audit_json, report):
    """Atomically write the passed receipt exactly once (exclusive create).

    Must be called only after all required copy/flush/readback steps have
    succeeded. Never rewrites an existing receipt.
    """
    audit_json = Path(audit_json)
    with audit_json.open("x") as f:
        json.dump(report, f, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def sections(path):
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0"
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    assert machine == 0xAA64
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    result = {}
    for i in range(count):
        off = pe + 24 + opt + 40 * i
        name = data[off:off + 8].rstrip(b"\0").decode()
        size = struct.unpack_from("<I", data, off + 8)[0]
        raw_size, ptr = struct.unpack_from("<II", data, off + 16)
        assert size <= raw_size or raw_size == 0
        result[name] = data[ptr:ptr + size]
    return data, result


def load_manifest(mp):
    try:
        text = Path(mp).read_text()
    except OSError as e:
        fail(f"manifest unreadable {mp}: {e}")
    try:
        m = json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"manifest malformed JSON: {e}")
    if not isinstance(m, dict):
        fail("manifest must be a JSON object")
    return m


def validate_manifest_literal(m):
    if m.get("revision") != REVISION:
        fail(f"manifest revision must be exactly {REVISION!r}")
    if m.get("approved_for_build") is not True:
        fail("manifest approved_for_build must be boolean true")
    if m.get("spec_review") != "PASS":
        fail("manifest spec_review must be 'PASS'")
    if m.get("quality_review") != "PASS":
        fail("manifest quality_review must be 'PASS'")
    sources = m.get("sources")
    if not isinstance(sources, dict):
        fail("manifest sources must be an object")
    for rel in REQUIRED_SOURCES:
        if rel not in sources:
            fail(f"manifest missing required source entry {rel}")
    allowed = set(REQUIRED_SOURCES)
    for rel, entry in sources.items():
        if rel not in allowed:
            fail(f"manifest has unverified extra entry {rel!r} (not in REQUIRED_SOURCES)")
        if not isinstance(entry, dict):
            fail(f"manifest entry {rel} must be an object")
        path = entry.get("path")
        sha = entry.get("sha256")
        nbytes = entry.get("bytes")
        if not isinstance(path, str) or not path:
            fail(f"manifest entry {rel} path must be a non-empty string")
        # Exact canonical key: no normalization, no affixes, no absolutes.
        if path != rel:
            fail(f"manifest entry {rel} path must equal {rel!r} exactly (got {path!r})")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            fail(f"manifest entry {rel} sha256 must be 64 lowercase hex")
        if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes <= 0:
            fail(f"manifest entry {rel} bytes must be a positive integer")
    return sources


def verify_manifest_sources(sources):
    for rel in REQUIRED_SOURCES:
        entry = sources[rel]
        q = P / rel
        if not q.is_file():
            fail(f"source missing on disk {rel}")
        if q.stat().st_size != entry["bytes"]:
            fail(f"source size changed {rel}")
        if sha_file(q) != entry["sha256"]:
            fail(f"source hash changed {rel}")
    print("DT26_AUDIT_MANIFEST_SOURCES_OK", flush=True)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Exact-artifact provenance auditor for dt26.")
    ap.add_argument("--source-manifest", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--audit-dir", required=True, type=Path)
    ap.add_argument("--host-copy", required=False, type=Path, default=None)
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    tag = args.tag
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
        fail(f"invalid --tag {tag!r}")
    audit_dir = Path(args.audit_dir)
    if ".." in audit_dir.parts:
        fail("audit dir must not contain ..")
    if not str(audit_dir).startswith("/home/builder/boot-failure-tests/dt26-audit-"):
        fail("audit dir must be /home/builder/boot-failure-tests/dt26-audit-<tag>")
    if tag not in str(audit_dir):
        fail("audit dir must contain the tag")
    OUT = Path(f"/home/builder/uki-v2-dt26-{tag}")

    manifest = load_manifest(args.source_manifest)
    sources = validate_manifest_literal(manifest)
    verify_manifest_sources(sources)

    # Reject before effects: artifacts must already exist.
    if not OUT.is_dir():
        fail(f"missing OUT {OUT} (build first; no artifacts to audit)")
    if not (OUT / "vmlinuz-live.efi").is_file():
        fail(f"missing UKI {OUT}/vmlinuz-live.efi")
    if not (OUT / "live-initramfs.img").is_file():
        fail(f"missing initramfs {OUT}/live-initramfs.img")

    # Preflight ALL outputs before extraction effects; exclusive, no unlinks.
    if audit_dir.exists():
        fail(f"refusing: audit dir already exists {audit_dir}")
    audit_json = audit_dir / "dt26-artifact-audit.json"
    if not str(audit_json).endswith("/dt26-artifact-audit.json"):
        fail("audit file must end /dt26-artifact-audit.json")
    board_json = audit_dir / "dt26-board.json"
    policy_json = audit_dir / "dt26-policy.json"
    valid_json = audit_dir / "dt26-validation.json"
    extract_new = audit_dir / "extract-new"
    if args.host_copy is not None:
        hc = Path(args.host_copy)
        if ".." in hc.parts or not str(hc).startswith("/mnt/d/"):
            fail("host copy must be a new tagged path under /mnt/d")
        if tag not in str(hc):
            fail("host copy path must contain the tag")
        if hc.exists():
            fail(f"refusing: host copy already exists {hc}")
        host_copy_bytes = (OUT / "vmlinuz-live.efi").stat().st_size if (OUT / "vmlinuz-live.efi").is_file() else 0
    else:
        host_copy_bytes = 0

    # Disk budget BEFORE extraction (future writes only): new-only extract
    # cap + one future 2.25GiB FAT + optional host copy actual bytes must
    # still leave >10GiB on D (actual /mnt/d). No local candidate clone is
    # created. Failed fresh dirs are preserved; no old-evidence deletion.
    try:
        free = shutil.disk_usage("/mnt/d").free
    except FileNotFoundError:
        fail("missing /mnt/d for D-free check")
    planned = audit_planned_bytes(host_copy_bytes)
    remaining = free - planned
    print(f"D_FREE_BYTES={free}", flush=True)
    print(f"D_PLANNED_EXTRACT_NEW_CAP={EXTRACT_NEW_CAP_BYTES}", flush=True)
    print(f"D_PLANNED_FAT_FUTURE={FAT_FUTURE_BYTES}", flush=True)
    print(f"D_PLANNED_HOSTCOPY={host_copy_bytes}", flush=True)
    print(f"D_PLANNED_TOTAL={planned}", flush=True)
    print(f"D_REMAINING_AFTER_PLANNED={remaining}", flush=True)
    if remaining <= RESERVE_BYTES:
        fail("D budget refuses extraction (need >10GiB after new-only extract + future 2.25GiB FAT + host copy)")

    # Shared lock must already exist (used by every build/extraction/runtime/VM).
    # Never create it, never unlink it; nonblocking contention refuses before
    # any extraction/copy. The lock is held across the entire expensive audit.
    if not LOCK.is_file():
        fail(f"refusing: shared lock missing (must already exist) {LOCK}")
    try:
        lf = LOCK.open("r+")
    except OSError as e:
        fail(f"lock open failed: {e}")
    with lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fail("could not hold dt25-build.lock exclusively")
        try:
            run_audit(OUT, board_json, policy_json, valid_json, audit_json,
                       extract_new, sources, args)
        finally:
            try:
                fcntl.flock(lf, fcntl.LOCK_UN)
            except OSError:
                pass


def run_audit(OUT, board_json, policy_json, valid_json, audit_json,
              extract_new, sources, args):
    audit_dir = audit_json.parent
    audit_dir.mkdir(parents=False, exist_ok=False)

    # Old fallback + failed 9c + dt25b preserved (immutable).
    old_uki_sha = sha_file(OLD_OUT / "vmlinuz-live.efi")
    if old_uki_sha != EXP_OLD_UKI_SHA:
        fail(f"old dt24 UKI changed {old_uki_sha}")
    failed_uki_sha = sha_file(FAILED_OUT / "vmlinuz-live.efi")
    if failed_uki_sha != EXP_FAILED_UKI_SHA:
        fail(f"failed 9c UKI changed {failed_uki_sha}")
    if sha_file(FAILED_CANDIDATE) != EXP_FAILED_UKI_SHA:
        fail("T/dt25-candidate.efi changed")
    if sha_file(OLD_CANDIDATE) != EXP_OLD_UKI_SHA:
        fail("T/dt24-candidate.efi changed")
    if sha_file(DT25B_CANDIDATE) != EXP_DT25B_UKI_SHA:
        fail("T/dt25b-candidate.efi changed")
    print("DT26_AUDIT_OLD_OK", flush=True)

    # Frozen SFS/Image/DTB/QEMU (full hashes; SFS read-only listing only,
    # never extracted/copied/repacked). Canonical private-build-root SFS is
    # the oracle; a staged copy, if present, is preservation-only.
    if str(SFS) != "/home/builder/live-rootfs-v2.squashfs":
        fail(f"auditor SFS must be canonical private-build-root path, got {SFS}")
    sfs_size = SFS.stat().st_size
    if sfs_size != EXP_SFS_SIZE:
        fail(f"SFS size {sfs_size}")
    print("hashing SFS (1.7GB)...", flush=True)
    sfs_sha = sha_file(SFS)
    if sfs_sha != EXP_SFS_SHA:
        fail(f"SFS hash {sfs_sha}")
    print(f"SFS_OK size={sfs_size} sha={sfs_sha}", flush=True)
    staged_preserved = None
    if STAGED_SFS.exists():
        if STAGED_SFS.stat().st_size == EXP_SFS_SIZE and sha_file(STAGED_SFS) == EXP_SFS_SHA:
            staged_preserved = {"path": str(STAGED_SFS), "sha256": EXP_SFS_SHA,
                                "bytes": EXP_SFS_SIZE, "preserved": True}
        else:
            fail("staged SFS copy present but does not match frozen hash/size")
    img_p = K / "arch/arm64/boot/Image"
    if img_p.stat().st_size != EXP_IMAGE_SIZE or sha_file(img_p) != EXP_IMAGE_SHA:
        fail("frozen Image changed (kernel rebuild forbidden)")
    dtb_bytes = (K / "arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb").read_bytes()
    if hashlib.sha256(dtb_bytes).hexdigest() != EXP_DTB_SHA or len(dtb_bytes) != EXP_DTB_SIZE:
        fail("frozen DTB changed")
    qemu = P / "testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
    if not qemu.is_file() or qemu.stat().st_size != EXP_QEMU_SIZE or sha_file(qemu) != EXP_QEMU_SHA:
        fail("QEMU firmware changed/missing")

    # PE sections: new .linux/.text/.hwids/base cmdline/.uname equal accepted
    # dt24; new .dtbauto == frozen DTB; new .initrd == built image.
    _, old = sections(OLD_OUT / "vmlinuz-live.efi")
    data, new = sections(OUT / "vmlinuz-live.efi")
    for name in (".linux", ".text", ".hwids", ".cmdline", ".uname"):
        if old[name] != new[name]:
            fail(f"boot/kernel change {name}")
    old_cmd = (OLD_OUT / "live-cmdline").read_text().strip()
    new_cmd_raw = new[".cmdline"].split(b"\x00")[0].decode().strip()
    if old_cmd != new_cmd_raw:
        fail(f"cmdline {old_cmd!r} vs {new_cmd_raw!r}")
    if new[".dtbauto"] != dtb_bytes:
        fail("dtbauto != frozen accepted DTB")
    if new[".initrd"] != (OUT / "live-initramfs.img").read_bytes():
        fail("initrd section != built image")

    # Board scope fresh (frozen DTB; do not read active new parser).
    subprocess.run(
        ["python3", str(T / "check-dt25-board.py"),
         str(K / "arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb"),
         "--result", str(board_json)], check=True)
    board = json.loads(board_json.read_text())
    if not (board.get("passed") and len(board.get("checks", {})) >= 50):
        fail(f"board scope failed {board}")

    # Guard policy fresh (real guard20).
    subprocess.run(
        ["python3", str(T / "dt25-thermal-check-policy.py"),
         "--result", str(policy_json)], check=True)
    policy = json.loads(policy_json.read_text())
    if not (policy.get("passed") and policy.get("required_sensor_count") == 20):
        fail(f"guard policy failed {policy}")

    # Full initramfs validation fresh.
    val_out = subprocess.check_output(
        ["python3", str(P / "builder/validate-live-initramfs.py"),
         str(OUT / "live-initramfs.img"),
         "--require-local-firmware", "--require-log-capture",
         "--require-platform-usb", "--require-platform-input",
         "--require-graphics"], text=True)
    validation = json.loads(val_out)
    if not validation.get("passed"):
        fail(f"initramfs validation failed {validation}")
    with valid_json.open("x") as f:
        json.dump(validation, f, indent=2)

    # Fresh retained extraction dir for the NEW image only (kept on failure
    # as evidence; never auto-cleaned). The old dt24 image is compared via
    # direct PE-section reads above; its extraction code was removed to
    # avoid an unused 1GiB future write. No old-evidence deletion.
    extract_new.mkdir(parents=False, exist_ok=False)
    r = subprocess.run(["lsinitcpio", "-x", str(OUT / "live-initramfs.img")],
                       cwd=str(extract_new),
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"lsinitcpio failed for {OUT / 'live-initramfs.img'}: {r.stdout[-2000:]} {r.stderr[-2000:]}")
    pb = extract_new

    # /init exact + no WSL helpers (validator is authority; re-assert here).
    init_data = (pb / "init").read_bytes()
    expected_init = Path("/usr/lib/initcpio/init").read_bytes()
    if init_data != expected_init:
        fail("packed /init != mkinitcpio script")
    if (pb / "usr/bin/mount.drvfs").exists() or (pb / "usr/bin/mount.drvfs").is_symlink():
        fail("packed WSL drvfs present")
    if (pb / "usr/bin/mount.wslfs").exists() or (pb / "usr/bin/mount.wslfs").is_symlink():
        fail("packed WSL wslfs present")

    # Copied helpers/units/policy equal manifest accepted bytes.
    snap = {}
    for packed, src in PACKED_PROVENANCE:
        got = (pb / packed).read_bytes() if (pb / packed).is_file() else None
        if got is None:
            fail(f"packed file missing {packed}")
        want = (P / src).read_bytes()
        if got != want:
            fail(f"packed {packed} != source {src}")
        if hashlib.sha256(got).hexdigest() != sources[src]["sha256"]:
            fail(f"packed {packed} != manifest accepted bytes")
        snap[src] = {"sha256": hashlib.sha256(got).hexdigest(), "bytes": len(got)}
    # Manifest-only sources (build scripts, gates, installs, checkpoint.c):
    # verify disk bytes already done; record for provenance.
    for rel in REQUIRED_SOURCES:
        if rel not in snap:
            q = P / rel
            snap[rel] = {"sha256": sha_file(q), "bytes": q.stat().st_size}

    # Lifetime contract: parent pre/post exact (new journal+console allowed),
    # private child BindsTo+After+PartOf unchanged.
    svc_src = (P / "builder/diagnostics/kestrel-graphics.service").read_text()
    svc_packed = (pb / "etc/kestrel-graphics-service").read_text()
    for txt, label in ((svc_src, "source parent"), (svc_packed, "packed parent")):
        if txt.count("ExecStartPre=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed") != 1:
            fail(f"{label} ExecStartPre not exactly once")
        if txt.count("ExecStopPost=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed") != 1:
            fail(f"{label} ExecStopPost not exactly once")
    sddm_src = (P / "builder/diagnostics/kestrel-graphics-sddm.service").read_text()
    sddm_packed = (pb / "etc/kestrel-graphics-sddm").read_text()
    for txt, label in ((sddm_src, "source child"), (sddm_packed, "packed child")):
        if "BindsTo=kestrel-graphics.service" not in txt:
            fail(f"{label} missing BindsTo")
        if "PartOf=kestrel-graphics.service" not in txt:
            fail(f"{label} missing PartOf")
        if "After=" not in txt or "kestrel-graphics.service" not in txt:
            fail(f"{label} missing After parent")

    # Module/provider/NLS contracts resolve inside the new image.
    for module in ["gpi", "i2c-qcom-geni", "phy-nxp-ptn3222", "qrtr",
                   "qrtr-smd", "i2c-hid", "i2c-hid-of", "hid-generic"]:
        txt = subprocess.check_output(
            ["modprobe", "-d", str(pb), "-S", "7.3.0-rc3",
             "--show-depends", module], text=True)
        if "insmod " not in txt:
            fail(f"module does not resolve {module}")

    # SFS required-path PRESENCE only (listing; never extract/copy/repack).
    sfs_list = subprocess.check_output(["unsquashfs", "-l", str(SFS)],
                                       text=True, timeout=120)
    for rel in ["squashfs-root/usr/bin/python3.14",
                "squashfs-root/usr/bin/sddm",
                "squashfs-root/usr/bin/kwin_wayland",
                "squashfs-root/usr/lib/dri/kms_swrast_dri.so",
                "squashfs-root/usr/lib/systemd/system/sddm.service",
                "squashfs-root/usr/lib/systemd/user/plasma-plasmashell.service"]:
        if rel not in sfs_list:
            fail(f"SFS missing {rel}")
    img_versions = {}
    for pkg in ["mesa", "sddm", "plasma-desktop", "kwin", "python"]:
        try:
            out = subprocess.check_output(["pacman", "--root", str(ROOT), "-Q", pkg],
                                          text=True).strip()
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            out = "unavailable (reference-only)"
        img_versions[pkg] = out
    # Mutable imgroot versions are auxiliary reference-only; the frozen SFS
    # full hash above plus a separate runtime proof is the oracle. Never gate.

    # Old preserved baseline (dt25 7-archive) unchanged; never rewritten.
    preserved = json.loads((T / "dt25-integration-fix-00-preserved-baseline-20261018T081521Z.json").read_text())
    for rel, exp in preserved["files"].items():
        q = T / rel
        if not q.is_file():
            fail(f"original missing {rel}")
        if sha_file(q) != exp["sha256"] or q.stat().st_size != exp["bytes"]:
            fail(f"original changed {rel}")

    report = {
        "passed": True,
        "revision": "v2-dt26",
        "uki_path": str(OUT / "vmlinuz-live.efi"),
        "uki_sha256": hashlib.sha256(data).hexdigest(),
        "uki_bytes": len(data),
        "initramfs_path": str(OUT / "live-initramfs.img"),
        "initramfs_sha256": hashlib.sha256((OUT / "live-initramfs.img").read_bytes()).hexdigest(),
        "initramfs_bytes": (OUT / "live-initramfs.img").stat().st_size,
        "sfs_path": str(SFS),
        "sfs_sha256": sfs_sha,
        "sfs_bytes": sfs_size,
        "sfs_preserved": True,
        "sfs_staged_copy_preservation": staged_preserved,
        "sfs_required_paths_present": True,
        "sfs_runtime_closure_proven": False,
        "sfs_runtime_proof_pending_vm": True,
        "kernel_stub_hwids_base_cmdline_unchanged": True,
        "dtb_sha256": EXP_DTB_SHA,
        "dtb_bytes": EXP_DTB_SIZE,
        "dtb_scope": board,
        "initramfs_validation": validation,
        "guard_policy": policy,
        "module_dependencies_resolve": True,
        "lifetime_fix_packed": {"parent_pre_post_exact": True,
                                "child_binds_after_partof": True},
        "old_uki_sha256": old_uki_sha,
        "old_uki_preserved": True,
        "failed_9c_uki_sha256": failed_uki_sha,
        "failed_9c_preserved_rejected_native": True,
        "dt25b_uki_sha256": EXP_DT25B_UKI_SHA,
        "dt25b_preserved": True,
        "old_candidates_preserved": True,
        "old_archives_preserved": True,
        "imgroot_versions_auxiliary_reference_only": img_versions,
        "imgroot_versions": img_versions,
        "qemu_firmware": {"path": str(qemu), "sha256": EXP_QEMU_SHA, "bytes": EXP_QEMU_SIZE},
        "sources": snap,
        "provenance": "packed helpers/units/policy equal manifest accepted bytes; SFS presence-only (canonical private-build-root full hash); frozen Image/DTB/SFS unchanged; imgroot versions reference-only",
        "packing_provenance": "passed",
        "vm_crash_retest_pending": True,
        "native_hardware_validated": False,
        "native_graphics_validated": False,
        "native": False,
    }
    # Final commit: ALL required copy/flush/readback steps FIRST, then the
    # single atomic exclusive passed receipt. Any copy/readback failure
    # propagates with NO receipt; the receipt is never rewritten after fact.
    # Failed fresh dirs are preserved as evidence by the caller.
    if args.host_copy is not None:
        hc = Path(args.host_copy)
        report["host_candidate_copy"] = write_host_copy(data, hc)
    else:
        report["host_candidate_copy"] = None
    commit_audit_report(audit_json, report)
    print(json.dumps({k: report[k] for k in ("passed", "revision", "uki_sha256", "initramfs_sha256", "sfs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
