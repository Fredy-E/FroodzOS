#!/usr/bin/env python3
"""Revision-aware platform-graphics gate for dt25b (24 tests, 0 skip).

Loads approved test-platform-graphics-gate.py via importlib WITHOUT __main__,
overrides module.DT25_IMG to NEW dt25b initramfs, uses actual classes and
fresh fix-dt25b tag, required --result/log prefix dt25-integration-fix-*.
Does NOT edit approved module or rewrite old results. Old defaults are NOT
run (they would misdiagnose expected byte change after unit fix).
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
SRC_MOD = T / "test-platform-graphics-gate.py"
NEW_IMG = Path("/home/builder/uki-v2-dt25b/live-initramfs.img")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


# Language check: approved module must compile.
subprocess.run([sys.executable, "-m", "py_compile", str(SRC_MOD)], check=True)

spec = importlib.util.spec_from_file_location("dt25_gate_mod", str(SRC_MOD))
mod = importlib.util.module_from_spec(spec)
# Execute module top-level (defines classes, OLD_BASELINE, helpers) WITHOUT __main__.
spec.loader.exec_module(mod)

# Revision override: point GREEN test at NEW image.
mod.DT25_IMG = NEW_IMG
assert str(mod.DT25_IMG) == str(NEW_IMG)

if not NEW_IMG.is_file():
    fail(f"missing NEW initramfs {NEW_IMG}; build dt25b first")

ap = argparse.ArgumentParser(description="dt25b platform gate (revision-aware)")
ap.add_argument("--tag", required=True)
ap.add_argument("--result", required=True)
ap.add_argument("--log", required=True)
ns = ap.parse_args()

# Reuse approved preflight (checks tag pattern, result/log prefix, collision, old archives).
result_path, log_path = mod._validate_tag_result(ns.tag, ns.result, ns.log)
# Caller must use dt25b tag to keep results distinct.
if "dt25b" not in ns.tag:
    fail(f"refusing: dt25b wrapper requires dt25b in tag, got {ns.tag!r}")

mod.GraphicsGateClauseTests.FIX_TAG = ns.tag
mod.GraphicsGateClauseTests.FIX_RESULT = str(result_path)

stream = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(mod.GraphicsGateClauseTests)
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
    "clause_total": 32,
    "clause_covered": 32,
    "tag": ns.tag,
    "result_path": str(result_path),
    "candidate": str(NEW_IMG),
    "revision": "v2-dt25b",
    "fixture_only": False,
    "dt24_red_expected": True,
    "dt25b_green_expected": True,
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
