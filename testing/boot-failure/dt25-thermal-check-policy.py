#!/usr/bin/env python3
"""Validate dt25 runtime sensor policy against guard (synthetic, no native claim).

Evidence-integrity fix (dt25-fix-v2):
- Project root derived from __file__; explicit --tag/--policy/--result/--guard;
  tag syntax validated; result preflighted BEFORE importing any guard or
  reading policy; exclusive creation; no overwrite.
- Guard path is injectable so tests use isolated mocks/copies and never
  import the concurrently-edited canonical guard until the parent integrates.
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
T = Path(__file__).resolve().parent
POL_D = ROOT / 'builder/diagnostics/kestrel-graphics-policy.json'
MOD_D = ROOT / 'builder/diagnostics/kestrel_graphics_guard.py'
OUT_D = T / 'dt25-thermal-policy-result.json'

TAG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def fail(msg):
    print(f'ERROR: {msg}', file=sys.stderr)
    raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--tag', default=None)
parser.add_argument('--policy', default=None)
parser.add_argument('--result', default=None)
parser.add_argument('--guard', default=None)
args = parser.parse_args()

if args.tag is not None:
    if not TAG_RE.fullmatch(args.tag):
        fail(f'invalid --tag {args.tag!r}')
    OUT = T / f'dt25-thermal-fix-v2-policy-result-{args.tag}.json'
elif args.result:
    OUT = Path(args.result)
else:
    OUT = OUT_D

POL = Path(args.policy) if args.policy else POL_D
MOD = Path(args.guard) if args.guard else MOD_D

for label, p in (('policy', POL), ('guard', MOD)):
    try:
        rp = Path(p).resolve()
        rd = ROOT.resolve()
        # Allow fixtures under /home/builder/boot-failure-tests for mocks/copies.
        fix = Path('/home/builder/boot-failure-tests').resolve()
        in_root = (rp == rd or rd in rp.parents)
        in_fix = (rp == fix or fix in rp.parents)
        if not (in_root or in_fix):
            fail(f'--{label} {p} escapes project root and fixture dir')
    except SystemExit:
        raise
    except Exception as e:
        fail(f'bad --{label} {p}: {e}')

# PREFLIGHT BEFORE importing guard or reading policy: fail before mutation.
if OUT.exists():
    fail(f'refusing: intended output already exists (no bytes changed): {OUT}')
if isinstance(POL, Path) and not POL.is_file():
    fail(f'policy missing: {POL}')
if isinstance(MOD, Path) and not MOD.is_file():
    fail(f'guard missing: {MOD}')

spec = importlib.util.spec_from_file_location('kestrel_graphics_guard', MOD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

pol = json.loads(POL.read_text())
req = set(pol['required_sensor_types'])
checks = {}
checks['count_is_20'] = len(req) == 20 == pol.get('required_sensor_count')
checks['names_match_cpu_cpuss'] = all(n.startswith(('cpu0-', 'cpu1-', 'cpuss0', 'cpuss1')) and n.endswith('-thermal') for n in req)
checks['no_battery_in_policy'] = 'qcom-battmgr-bat' not in req
checks['no_platform_trips'] = pol.get('platform_trips_modified') is False and pol.get('cooling_maps_modified') is False
checks['stop_is_80c'] = pol.get('experiment_stop_mc') == 80000 and pol.get('experiment_minimum_mc') == 5000
checks['provenance_has_pin_and_dtb'] = pol.get('provenance', {}).get('source_pin') == '3f0d8691afa098ba378d7d5a3968f03219887719' and bool(pol.get('provenance', {}).get('dtb_sha256'))

# guard behavior with exact policy set (synthetic fixtures only)
good = [{'type': n, 'temp_mc': 42000} for n in sorted(req)]
r_good = guard.evaluate_temperatures(good, req)
checks['guard_accepts_all_20'] = r_good['ok'] is True and r_good['maximum_mc'] == 42000
r_batt = guard.evaluate_temperatures([{'type': 'qcom-battmgr-bat', 'temp_mc': 30000}], req)
checks['guard_battery_alone_blocks'] = r_batt['ok'] is False
r_missing = guard.evaluate_temperatures([r for r in good if r['type'] != sorted(req)[0]], req)
checks['guard_missing_one_blocks'] = r_missing['ok'] is False and any('missing_sensor' in e for e in r_missing['errors'])
r_hot = [{'type': n, 'temp_mc': (80000 if i == 0 else 42000)} for i, n in enumerate(sorted(req))]
checks['guard_80c_inclusive_blocks'] = guard.evaluate_temperatures(r_hot, req)['ok'] is False
r_dup = good + [good[0]]
checks['guard_duplicate_blocks'] = guard.evaluate_temperatures(r_dup, req)['ok'] is False

report = {'passed': all(checks.values()), 'checks': checks,
          'required_sensor_count': len(req),
          'policy': str(POL), 'guard': str(MOD), 'tag': args.tag,
          'synthetic_policy_fixtures_only': True,
          'native_hardware_validated': False}
with OUT.open('x') as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
