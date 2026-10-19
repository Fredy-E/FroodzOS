#!/usr/bin/env python3
"""Build dt25 live UKI with checked subprocesses; retain complete output.

Fresh output /home/builder/uki-v2-dt25 only. Holds flock
/home/builder/boot-failure-tests/dt25-build.lock throughout mkinitcpio+UKI.
Checks host D free >10GiB before big writes; uses 2CPU compression max
(via live-mkinitcpio.conf) and one process slot via exclusive lock.
"""
import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
OUT = Path("/home/builder/uki-v2-dt25")
LOCK = Path("/home/builder/boot-failure-tests/dt25-build.lock")
LOG = T / "dt25-integration-build-dt25-live.log"

TAG = "dt25-integration-build"


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


if OUT.exists():
    fail(f"refusing: OUT already exists {OUT} (fresh output required)")
# Disk check before big writes.
try:
    free = shutil.disk_usage("/mnt/d").free
except FileNotFoundError:
    fail("missing /mnt/d for D-free check")
if free < 10 * 1024**3:
    fail(f"D free too low: {free} bytes (need >10GiB)")
print(f"D_FREE_BYTES={free}", flush=True)

for rel in [
    "builder/build-live-uki.sh",
    "builder/diagnostics/kestrel-text-login.sh",
    "builder/diagnostics/kestrel-text-proof.sh",
    "builder/diagnostics/kestrel-text-bashrc",
    "builder/initcpio/install/kestrel_graphics",
    "builder/initcpio/install/kestrel_text",
]:
    subprocess.run(["bash", "-n", str(P / rel)], check=True)
for rel in [
    "builder/validate-live-initramfs.py",
    "builder/platform_graphics_gate.py",
    "builder/diagnostics/kestrel-graphics-supervisor.py",
    "builder/diagnostics/kestrel_graphics_guard.py",
]:
    subprocess.run([sys.executable, "-m", "py_compile", str(P / rel)], check=True)
for rel in [
    "builder/initcpio/hooks/kestrel_graphics",
    "builder/initcpio/hooks/kestrel_text",
]:
    subprocess.run(["sh", "-n", str(P / rel)], check=True)

# Exclusive log creation; refuse if exists.
try:
    log_fd = LOG.open("x")
except FileExistsError:
    fail(f"refusing: log already exists {LOG}")
else:
    log_fd.close()

LOCK.parent.mkdir(parents=True, exist_ok=True)
LOCK.touch(exist_ok=True)
with LOCK.open("r+") as lf:
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fail("could not hold dt25-build.lock exclusively (one process slot)")
    env = os.environ.copy()
    env["OUT"] = str(OUT)
    # Hold lock throughout build; real exclusive full log.
    with LOG.open("ab") as log:
        result = subprocess.run(
            ["bash", str(P / "builder/build-live-uki.sh")],
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
assert (OUT / "vmlinuz-live.efi").stat().st_size > 100000000
assert (OUT / "live-initramfs.img").stat().st_size > 100000000
print("DT25_LIVE_BUILD_COMPLETE", flush=True)
print(f"OUT={OUT}", flush=True)
print(f"LOG={LOG}", flush=True)
