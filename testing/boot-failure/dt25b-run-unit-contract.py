#!/usr/bin/env python3
"""Run dt25b lifetime unit-contract (16 tests) + optional regression.

Imports approved test-dt25-graphics-unit-contract.py via importlib WITHOUT
__main__ side effects, runs actual UnitContract against current on-disk fixed
units (f5a/6a88). Optionally runs guard71/staging19/supervisor16 for regression
if cheap. Fresh dt25b-* result/log, 0 skip expected. Does NOT claim actual
SIGKILL fix from static; VM retest remains required.
"""
import argparse
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"

UNIT_MOD = T / "test-dt25-graphics-unit-contract.py"
GUARD_MOD = T / "test-dt25-graphics-guard.py"
STAGING_MOD = T / "test-dt25-graphics-staging.py"
SUPERVISOR_MOD = T / "test-dt25-graphics-supervisor.py"


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


for q in [UNIT_MOD]:
    subprocess.run([sys.executable, "-m", "py_compile", str(q)], check=True)

ap = argparse.ArgumentParser(description="dt25b unit contract (revision-aware)")
ap.add_argument("--tag", required=True)
ap.add_argument("--result", required=True)
ap.add_argument("--log", required=True)
ap.add_argument("--with-regression", action="store_true", help="also run guard71/staging19/supervisor16")
ns = ap.parse_args()

if "dt25b" not in ns.tag:
    fail(f"refusing: dt25b wrapper requires dt25b in tag, got {ns.tag!r}")
rp = Path(ns.result)
lp = Path(ns.log)
if rp.parent.resolve() != T.resolve():
    fail(f"refusing: --result must be under {T}")
if not rp.name.startswith("dt25b-"):
    fail(f"refusing: --result must start with dt25b-, got {rp.name}")
if ns.tag not in rp.name:
    fail(f"refusing: --result must contain tag {ns.tag}")
if not rp.name.endswith(".json"):
    fail(f"refusing: --result must end .json")
if rp.exists():
    fail(f"refusing: fresh output already exists {rp}")
if not lp.name.startswith("dt25b-"):
    fail(f"refusing: --log must start with dt25b-, got {lp.name}")
if ns.tag not in lp.name:
    fail(f"refusing: --log must contain tag {ns.tag}")
if lp.exists():
    fail(f"refusing: fresh log already exists {lp}")
if lp.parent.resolve() != T.resolve():
    fail(f"refusing: --log must be under {T}")

spec = importlib.util.spec_from_file_location("dt25_unit_mod", str(UNIT_MOD))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

stream = io.StringIO()
suite = unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(mod.UnitContract))
runner = unittest.TextTestRunner(verbosity=2, stream=stream)
result = runner.run(suite)
output = stream.getvalue()
unit_tests = result.testsRun
unit_fail = len(result.failures)
unit_err = len(result.errors)
unit_skip = len(getattr(result, "skipped", []))

regression = {}
if ns.with_regression:
    for label, path in [("guard71", GUARD_MOD), ("staging19", STAGING_MOD), ("supervisor16", SUPERVISOR_MOD)]:
        try:
            subprocess.run([sys.executable, "-m", "py_compile", str(path)], check=True)
            s = importlib.util.spec_from_file_location(f"dt25_{label}_mod", str(path))
            m = importlib.util.module_from_spec(s)
            s.loader.exec_module(m)
            # Collect all TestCase subclasses in that module.
            cases = []
            for attr in dir(m):
                try:
                    obj = getattr(m, attr)
                    import inspect as _inspect
                    if _inspect.isclass(obj) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
                        cases.append(obj)
                except Exception:
                    continue
            rs = io.StringIO()
            st = unittest.TestSuite()
            for c in cases:
                st.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(c))
            rr = unittest.TextTestRunner(verbosity=1, stream=rs).run(st)
            regression[label] = {
                "tests_run": rr.testsRun,
                "failures": len(rr.failures),
                "errors": len(rr.errors),
                "skipped": len(getattr(rr, "skipped", [])),
                "passed": rr.wasSuccessful(),
            }
            output += f"\n# regression {label}\n" + rs.getvalue()
        except Exception as e:
            regression[label] = {"error": str(e), "passed": False}

passed = result.wasSuccessful() and all(v.get("passed", False) for v in regression.values()) if regression else result.wasSuccessful()

report = {
    "passed": passed,
    "tests_run": unit_tests,
    "failures": unit_fail,
    "errors": unit_err,
    "skipped": unit_skip,
    "tag": ns.tag,
    "result_path": str(rp),
    "revision": "v2-dt25b",
    "sources": {
        "builder/diagnostics/kestrel-graphics.service": {
            "sha256": __import__("hashlib").sha256((P / "builder/diagnostics/kestrel-graphics.service").read_bytes()).hexdigest(),
            "bytes": (P / "builder/diagnostics/kestrel-graphics.service").stat().st_size,
        },
        "builder/diagnostics/kestrel-graphics-sddm.service": {
            "sha256": __import__("hashlib").sha256((P / "builder/diagnostics/kestrel-graphics-sddm.service").read_bytes()).hexdigest(),
            "bytes": (P / "builder/diagnostics/kestrel-graphics-sddm.service").stat().st_size,
        },
    },
    "synthetic_fixtures_only": True,
    "native_hardware_validated": False,
    "vm_retest_required_after_rebuild": True,
    "old_9c_image_rejected_for_native": True,
    "regression": regression,
    "static_does_not_claim_live_sigkill": True,
}
with rp.open("x") as f:
    json.dump(report, f, indent=2)
with lp.open("x") as f:
    f.write(f"# tag={ns.tag} result={rp} revision=v2-dt25b\n")
    f.write(output)
    f.write("\n# report\n")
    f.write(json.dumps(report, indent=2))
    f.write("\n")
sys.stdout.write(output)
sys.stdout.write(json.dumps(report, indent=2) + "\n")
raise SystemExit(0 if passed else 1)
