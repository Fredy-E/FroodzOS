#!/usr/bin/env python3
"""Failed-case preservation proof (fix-owned, no candidate/output touched).

Simulates a failed packed case: creates fresh BASE, writes scripts/stdout/stderr,
writes immutable receipt via exclusive creation, preserves dir (no rmtree),
writes fresh JSON result via exclusive creation. Proves harness detects failure
and preserves evidence; successful fixtures are cleaned elsewhere.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
T = Path(__file__).parent
BASE_ROOT = Path("/home/builder/boot-failure-tests")
OLD_BASELINE = {
    "dt25-artifact-audit.json": "7133b357371fea37ae72b40b5fcbf4b341dc63e2d67b09e08c83d143446a4308",
}
def _validate(tag, result):
    import re
    assert re.fullmatch(r"fix-[A-Za-z0-9._-]{1,64}", tag), tag
    rp = Path(result)
    assert rp.parent.resolve() == T.resolve(), rp
    assert rp.name.startswith("dt25-integration-fix-"), rp.name
    assert tag in rp.name, rp.name
    assert rp.name.endswith(".json"), rp.name
    assert not rp.exists(), f"exists {rp}"
    for rel, exp in OLD_BASELINE.items():
        data = (T/rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == exp, rel
    return rp
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--result", required=True)
    ns = ap.parse_args()
    rp = _validate(ns.tag, ns.result)
    base = Path(tempfile.mkdtemp(dir=BASE_ROOT, prefix=f"dt25-integration-fix-preserved-fail-{ns.tag}-"))
    try:
        (base/"outer.sh").write_text("#!/bin/bash\nset -euo pipefail\necho FAIL_DEMO\n")
        (base/"inner-test-inner-abc123.sh.txt").write_text("#!/usr/bin/ash\ngetarg() { echo 1; }\n")
        (base/"outer-stdout.txt").write_text("STAGE_OK\nFAILED_COPY_DETECTION_OK\nSIMULATED_FAILURE\n")
        (base/"outer-stderr.txt").write_text("")
        (base/"outer-rc.txt").write_text("1")
        receipt = {"test": "preservation_demo", "failed": True, "base": str(base), "tag": ns.tag}
        receipt_path = base / f"dt25-integration-fix-packed-receipt-preservation_demo.json"
        with receipt_path.open("x") as f:
            json.dump(receipt, f, indent=2)
        print(f"PRESERVED_FAILED_CASE={base}")
        # Do NOT rmtree on failure (preserve).
        report = {"passed": False, "tag": ns.tag, "preserved_base": str(base), "receipt": str(receipt_path), "originals_preserved": True, "native_hardware_validated": False, "demo_failure_intentional": True}
        with rp.open("x") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"DEMO_ERROR {e}")
        raise SystemExit(2)
