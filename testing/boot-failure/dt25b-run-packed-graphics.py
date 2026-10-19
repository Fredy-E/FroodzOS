#!/usr/bin/env python3
"""Revision-aware packed-graphics validation for dt25b (10 tests, 0 skip).

Loads approved test-dt25-packed-graphics.py via importlib WITHOUT __main__,
overrides module.DT25_IMG to NEW dt25b initramfs, uses actual PackedGraphicsTests
with fresh fix-dt25b tag. Runs real packed chroot getarg0/1, text-before-graphics,
full unit graph --man=no. Does NOT edit approved module or rewrite old results.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
SRC_MOD = T / "test-dt25-packed-graphics.py"
NEW_IMG = Path("/home/builder/uki-v2-dt25b/live-initramfs.img")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


subprocess.run([sys.executable, "-m", "py_compile", str(SRC_MOD)], check=True)

spec = importlib.util.spec_from_file_location("dt25_packed_mod", str(SRC_MOD))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.DT25_IMG = NEW_IMG
assert str(mod.DT25_IMG) == str(NEW_IMG)

if not NEW_IMG.is_file():
    fail(f"missing NEW initramfs {NEW_IMG}; build dt25b first")

ap = argparse.ArgumentParser(description="dt25b packed graphics (revision-aware)")
ap.add_argument("--tag", required=True)
ap.add_argument("--result", required=True)
ap.add_argument("--log", required=True)
ns = ap.parse_args()

result_path, log_path = mod._validate_tag_result(ns.tag, ns.result, ns.log)
if "dt25b" not in ns.tag:
    fail(f"refusing: dt25b wrapper requires dt25b in tag, got {ns.tag!r}")

mod.PackedGraphicsTests.FIX_TAG = ns.tag
mod.PackedGraphicsTests.FIX_RESULT = str(result_path)
mod.PackedGraphicsTests.FIX_LOG = str(log_path)

stream = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(mod.PackedGraphicsTests)
runner = unittest.TextTestRunner(verbosity=2, stream=stream)
result = runner.run(suite)
output = stream.getvalue()

preserved = {}
for rel, exp in mod.OLD_BASELINE.items():
    q = T / rel
    data = q.read_bytes()
    ok = (hashlib.sha256(data).hexdigest() == exp["sha256"] and len(data) == exp["bytes"])
    preserved[rel] = ok

report = {
    "passed": result.wasSuccessful(),
    "tests_run": result.testsRun,
    "failures": len(result.failures),
    "errors": len(result.errors),
    "skipped": len(getattr(result, "skipped", [])),
    "tag": ns.tag,
    "result_path": str(result_path),
    "candidate": str(NEW_IMG),
    "revision": "v2-dt25b",
    "fixture_only": True,
    "private_namespace": True,
    "chroot_closure_no_host_fallback": True,
    "getarg_inside_packed_ash": True,
    "run_latehook_both_flags": True,
    "full_graph_man_no": True,
    "native_hardware_validated": False,
    "collision_preflight_passed": True,
    "originals_preserved": preserved,
    "all_originals_preserved": all(preserved.values()),
    "previously_lost_history_note": "prior __main__ unlinked outputs before exclusive creation; overwritten history (if any) is not recoverable and not fabricated; current baseline hashes preserved",
}
with result_path.open("x") as f:
    json.dump(report, f, indent=2)
with log_path.open("x") as f:
    f.write(f"# tag={ns.tag} result={result_path} candidate={NEW_IMG} revision=v2-dt25b\n")
    f.write(output)
    f.write("\n# report\n")
    f.write(json.dumps(report, indent=2))
    f.write("\n")
sys.stdout.write(output)
sys.stdout.write(json.dumps(report, indent=2) + "\n")
raise SystemExit(0 if (result.wasSuccessful() and all(preserved.values())) else 1)
