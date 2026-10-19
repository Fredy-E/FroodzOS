#!/usr/bin/env python3
"""Collect dt25 integration evidence into fresh summary. No native claims."""
import hashlib
import json
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure")
OUT = Path("/home/builder/uki-v2-dt25")

def load(name):
    return json.loads((P / name).read_text())

gate = load("dt25-integration-platform-graphics-gate.json")
packed = load("dt25-integration-packed-graphics.json")
board = load("dt25-integration-board.json")
policy = load("dt25-integration-policy.json")
valid = load("dt25-integration-validation.json")
audit = load("dt25-artifact-audit.json")

summary = {
    "revision": "v2-dt25",
    "passed": all([
        gate["passed"],
        packed["passed"],
        board["passed"],
        policy["passed"],
        valid["passed"],
        audit["passed"],
    ]),
    "build": {
        "out": str(OUT),
        "log": str(P / "dt25-integration-build-dt25-live.log"),
        "exit": 0,
    },
    "gate": {"tests_run": gate["tests_run"], "passed": gate["passed"]},
    "packed": {"tests_run": packed["tests_run"], "passed": packed["passed"]},
    "board": {"checks": len(board["checks"]), "passed": board["passed"]},
    "policy": {"checks": len(policy["checks"]), "passed": policy["passed"]},
    "validation": {"checks": len(valid["checks"]), "passed": valid["passed"]},
    "audit": {
        "uki_sha256": audit["uki_sha256"],
        "uki_bytes": audit["uki_bytes"],
        "initramfs_sha256": audit["initramfs_sha256"],
        "uki_path": audit["uki_path"],
        "passed": audit["passed"],
    },
    "candidate": str(P / "dt25-candidate.efi"),
    "old_uki_preserved": audit["old_uki_preserved"],
    "sfs_preserved": audit["sfs_preserved"],
    "native_hardware_validated": False,
    "native_graphics_validated": False,
    "remaining": [
        "QEMU EFI regression (QEMU_EFI.fd exists, no install needed)",
        "native CPU thermal readings + software-Plasma pixels/input",
        "physical USB health + occupied slot prerequisites",
        "isolated VM SIGKILL chaos gate (not normal stop)",
        "media/file-only update decision (parent-owned)",
    ],
}

target = P / "dt25-integration-summary.json"
if target.exists():
    raise SystemExit(f"refusing: exists {target}")
with target.open("x") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
