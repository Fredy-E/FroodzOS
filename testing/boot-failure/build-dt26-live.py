#!/usr/bin/env python3
"""Build dt26 live initrd/UKI from reviewed sources, guarded and fresh.

Preparation-only wrapper: performs every preflight rejection check without
building until the parent publishes a reviewed source manifest. Never patches
dt25b, never rebuilds the kernel, never touches SFS/firmware/accounts.

CLI contract:
  build-dt26-live.py --source-manifest <manifest.json> --tag <unique-tag>

  --source-manifest: JSON file created by the parent only after final
    spec (PASS) + quality (PASS) reviews. Schema (all required unless noted):
      {"revision": "v2-dt26",
       "approved_for_build": true,
       "spec_review": "PASS",
       "quality_review": "PASS",
       "review_id": "<optional string>",
       "sources": {"<project-rel>": {"path": "<same rel exactly>",
                                      "sha256": "<64 lowercase hex, no LF>",
                                      "bytes": <positive int>}, ...}}
       Every entry of REQUIRED_SOURCES must be present with path exactly equal
       to its key (no normalization, no affixed/escaped variants); extra keys
       beyond REQUIRED_SOURCES are refused. Literal formats (fullmatch, so
       trailing LF is rejected) are validated BEFORE any filesystem lookup;
       actual file size/sha256 are then hashed at execution. Any mismatch
       refuses the build with no effects.
       --tag: unique attempt label, ^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$ (fullmatch,
       trailing LF refused; refused before any manifest load). Derives
    OUT=/home/builder/uki-v2-dt26-<tag> and
    LOG=testing/boot-failure/build-dt26-live-<tag>.log, both required fresh.

Effects (only after all read-only checks pass):
  exclusive LOG creation (open "x"), hold the SAME existing
  /home/builder/boot-failure-tests/dt25-build.lock (LOCK_EX|LOCK_NB, never
  created, never unlinked) throughout mkinitcpio+UKI, run canonical
  builder/build-live-uki.sh with explicit env OUT/ROOT/KESTREL_PROJECT/
  KESTREL_LOG_BINARY/KESTREL_LOG, full stdout+stderr to LOG.
  Checked rc; no exit-0 masks failure. Planned D writes: 3GiB conservative
  guard, must leave >10GiB free.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
LOCK = Path("/home/builder/boot-failure-tests/dt25-build.lock")
CANONICAL_BUILDER = P / "builder/build-live-uki.sh"

REVISION = "v2-dt26"
BUILD_PLANNED_BYTES = 3 * 1024**3
RESERVE_BYTES = 10 * 1024**3
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DENY_TAGS = {"dt24", "dt25", "dt25b", "dt26", "integration-build"}

# Explicit build fields matching the accepted pipeline (builder/build-live-uki.sh
# defaults: ROOT=/home/builder/imgroot, KESTREL_PROJECT=$PROJECT,
# KESTREL_LOG_BINARY=/home/builder/diag/kestrel-kmsg, KESTREL_LOG=0).
BUILD_ROOT = "/home/builder/imgroot"
BUILD_KESTREL_LOG_BINARY = "/home/builder/diag/kestrel-kmsg"
BUILD_KESTREL_LOG = "0"

# Every canonical packing input + changed diagnostic, traced from
# builder/build-live-uki.sh, builder/initcpio/install/*,
# builder/initcpio/hooks/*, builder/validate-live-initramfs.py imports.
# Kernel Image / DTB / SFS / stub are frozen (hardcoded below), not manifest.
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

# Frozen accepted inputs (from accepted dt24/dt25b audits/baselines).
EXP_IMAGE_SHA = "682273a91f2016b9d5484857639bd043e021b961d7f4cfd385a09566b2df3abc"
EXP_IMAGE_SIZE = 52492800
EXP_DTB_SHA = "f5f67c13bdfe975998b083ac06465c36231c0bae205e8e60fff99832264f5232"
EXP_DTB_SIZE = 207772
EXP_SFS_SIZE = 1748525056

BASH_SYNTAX = (
    "builder/build-live-uki.sh",
    "builder/diagnostics/kestrel-text-login.sh",
    "builder/diagnostics/kestrel-text-proof.sh",
    "builder/diagnostics/kestrel-text-bashrc",
    "builder/initcpio/install/kestrel_firmware",
    "builder/initcpio/install/kestrel_graphics",
    "builder/initcpio/install/kestrel_text",
)
PY_SYNTAX = (
    "builder/validate-live-initramfs.py",
    "builder/platform_graphics_gate.py",
    "builder/platform_usb_gate.py",
    "builder/platform_input_gate.py",
    "builder/diagnostics/kestrel-graphics-supervisor.py",
    "builder/diagnostics/kestrel_graphics_guard.py",
)
ASH_SYNTAX = (
    "builder/initcpio/hooks/kestrel_graphics",
    "builder/initcpio/hooks/kestrel_text",
    "builder/initcpio/hooks/kestrel_log",
    "builder/initcpio/hooks/kestrel_efilog",
)


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_fresh(paths):
    """Refuse if any output path already exists; create nothing, unlink nothing."""
    for p in paths:
        if Path(p).exists():
            fail(f"refusing: fresh output already exists {p}")


def check_d_remaining(free_bytes, planned_bytes, reserve_bytes=RESERVE_BYTES):
    """Single post-reserve check: free - planned must leave >reserve."""
    remaining = free_bytes - planned_bytes
    if remaining <= reserve_bytes:
        fail(f"D would fall to {remaining} bytes (need >10GiB after planned writes)")
    return remaining


def canonical_build_env(out):
    """Explicit env for the canonical builder (no implicit inheritance).

    Copies os.environ for PATH/HOME plumbing but pins every known build
    field: OUT, ROOT, KESTREL_PROJECT, KESTREL_LOG_BINARY, KESTREL_LOG.
    """
    env = os.environ.copy()
    env["OUT"] = str(out)
    env["ROOT"] = BUILD_ROOT
    env["KESTREL_PROJECT"] = str(P)
    env["KESTREL_LOG_BINARY"] = BUILD_KESTREL_LOG_BINARY
    env["KESTREL_LOG"] = BUILD_KESTREL_LOG
    return env


def check_compression_budget(builder_text):
    """Bound actual COMPRESSION_OPTIONS threads to 1..2 (no comment bypass).

    Inspects only real COMPRESSION_OPTIONS code lines (comments stripped),
    so a '-T2' inside a comment cannot mask a '-T0'/'-T10' in the options.
    """
    vals = []
    for line in builder_text.splitlines():
        if "COMPRESSION_OPTIONS" not in line:
            continue
        code = line.split("#", 1)[0]
        if "COMPRESSION_OPTIONS" not in code:
            continue
        for m in re.finditer(r"-T\s*(\d+)", code):
            vals.append(int(m.group(1)))
    if not vals:
        fail("canonical builder compression thread count not bounded (no COMPRESSION_OPTIONS -T found)")
    for v in vals:
        if v < 1 or v > 2:
            fail(f"canonical builder exceeds 1..2 compression CPUs (found -T{v})")
    print("DT26_COMPRESSION_BUDGET_OK", flush=True)


def load_manifest(manifest_path):
    try:
        text = Path(manifest_path).read_text()
    except OSError as e:
        fail(f"manifest unreadable {manifest_path}: {e}")
    try:
        m = json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"manifest malformed JSON: {e}")
    if not isinstance(m, dict):
        fail("manifest must be a JSON object")
    return m


def validate_manifest_literal(m):
    # Literal-format checks BEFORE any source lookup.
    if m.get("revision") != REVISION:
        fail(f"manifest revision must be exactly {REVISION!r}")
    if m.get("approved_for_build") is not True:
        fail("manifest approved_for_build must be boolean true (no build approval)")
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
        if not isinstance(nbytes, int) or isinstance(nbytes, bool):
            fail(f"manifest entry {rel} bytes must be an integer")
        if nbytes <= 0 or nbytes > 100 * 1024 * 1024:
            fail(f"manifest entry {rel} bytes out of range: {nbytes}")
    return sources


def verify_manifest_sources(sources):
    # Actual hashing at execution; no fabricated approvals.
    for rel in REQUIRED_SOURCES:
        entry = sources[rel]
        q = P / rel
        if not q.is_file():
            fail(f"source missing on disk {rel}")
        got_size = q.stat().st_size
        if got_size != entry["bytes"]:
            fail(f"source size changed {rel}: manifest {entry['bytes']} disk {got_size}")
        got_sha = sha_file(q)
        if got_sha != entry["sha256"]:
            fail(f"source hash changed {rel}: manifest {entry['sha256']} disk {got_sha}")
    print("DT26_MANIFEST_SOURCES_OK", flush=True)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Guarded fresh dt26 initrd/UKI build wrapper (preparation-only until reviewed manifest).")
    ap.add_argument("--source-manifest", required=True, type=Path, help="Reviewed manifest JSON (revision v2-dt26, approved_for_build true, spec+quality PASS).")
    ap.add_argument("--tag", required=True, help="Unique attempt tag; OUT=/home/builder/uki-v2-dt26-<tag>.")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    tag = args.tag
    if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
        fail(f"invalid --tag {tag!r} (must match ^[A-Za-z0-9][A-Za-z0-9._-]{{1,63}}$)")
    if tag in DENY_TAGS:
        fail(f"refusing reserved tag {tag!r} (old outputs immutable)")

    OUT = Path(f"/home/builder/uki-v2-dt26-{tag}")
    LOG = T / f"build-dt26-live-{tag}.log"
    for old in (Path("/home/builder/uki-v2-dt24"), Path("/home/builder/uki-v2-dt25"), Path("/home/builder/uki-v2-dt25b")):
        if OUT == old:
            fail(f"refusing: OUT collides with preserved output {old}")

    manifest = load_manifest(args.source_manifest)
    sources = validate_manifest_literal(manifest)
    verify_manifest_sources(sources)

    # Frozen kernel/DTB read-only checks (fast); full SFS hash is audit-owned.
    ksrc = Path("/home/builder/src/ksrc")
    img = ksrc / "arch/arm64/boot/Image"
    dtb = ksrc / "arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb"
    for label, path, exp_sha, exp_size in (
        ("Image", img, EXP_IMAGE_SHA, EXP_IMAGE_SIZE),
        ("DTB", dtb, EXP_DTB_SHA, EXP_DTB_SIZE),
    ):
        if not path.is_file():
            fail(f"frozen {label} missing {path}")
        if path.stat().st_size != exp_size:
            fail(f"frozen {label} size changed: disk {path.stat().st_size} != {exp_size}")
        if sha_file(path) != exp_sha:
            fail(f"frozen {label} hash changed (kernel rebuild forbidden)")
    print("DT26_FROZEN_KERNEL_DTB_OK", flush=True)

    # Explicit build-root inputs must exist (no secrets read, no hashes guessed).
    if not Path(BUILD_ROOT).is_dir():
        fail(f"build ROOT missing {BUILD_ROOT}")
    if not Path(BUILD_KESTREL_LOG_BINARY).is_file():
        fail(f"build KESTREL_LOG_BINARY missing {BUILD_KESTREL_LOG_BINARY}")
    if not Path(str(P)).is_dir():
        fail(f"build KESTREL_PROJECT missing {P}")

    # Read-only syntax gates on canonical files.
    for rel in BASH_SYNTAX:
        subprocess.run(["bash", "-n", str(P / rel)], check=True)
    for rel in PY_SYNTAX:
        subprocess.run([sys.executable, "-m", "py_compile", str(P / rel)], check=True)
    for rel in ASH_SYNTAX:
        subprocess.run(["sh", "-n", str(P / rel)], check=True)
    print("DT26_SYNTAX_OK", flush=True)

    # Compression budget: actual COMPRESSION_OPTIONS threads must be 1..2.
    builder_text = CANONICAL_BUILDER.read_text()
    check_compression_budget(builder_text)

    # Projected D writes must leave >10GiB (single reserve check, not
    # separate free>reserve and free>planned).
    try:
        free = shutil.disk_usage("/mnt/d").free
    except FileNotFoundError:
        fail("missing /mnt/d for D-free check")
    remaining = free - BUILD_PLANNED_BYTES
    print(f"D_FREE_BYTES={free}", flush=True)
    print(f"D_PLANNED_BYTES={BUILD_PLANNED_BYTES}", flush=True)
    print(f"D_REMAINING_AFTER_PLANNED={remaining}", flush=True)
    if remaining <= RESERVE_BYTES:
        fail(f"D would fall to {remaining} bytes (need >10GiB after planned writes)")

    # Preflight ALL outputs before effects; exclusive, no unlinks.
    require_fresh([OUT, LOG])
    # Shared lock must already exist (used by every build/extraction/runtime/VM).
    # Never create it, never unlink it; nonblocking contention refuses.
    if not LOCK.is_file():
        fail(f"refusing: shared lock missing (must already exist) {LOCK}")

    try:
        log_fd = LOG.open("x")
    except FileExistsError:
        fail(f"refusing: log already exists {LOG}")
    else:
        log_fd.close()

    with LOCK.open("r+") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fail("could not hold dt25-build.lock exclusively (one process slot)")
        env = canonical_build_env(OUT)
        with LOG.open("ab") as log:
            result = subprocess.run(
                ["bash", str(CANONICAL_BUILDER)],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        try:
            fcntl.flock(lf, fcntl.LOCK_UN)
        except OSError:
            pass
    if result.returncode != 0:
        fail(f"canonical builder failed rc={result.returncode} see {LOG}")
    if (OUT / "vmlinuz-live.efi").stat().st_size < 100000000:
        fail("built UKI unexpectedly small")
    if (OUT / "live-initramfs.img").stat().st_size < 100000000:
        fail("built initramfs unexpectedly small")
    print("DT26_LIVE_BUILD_COMPLETE", flush=True)
    print(f"OUT={OUT}", flush=True)
    print(f"LOG={LOG}", flush=True)


if __name__ == "__main__":
    main()
