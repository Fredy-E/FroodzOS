#!/usr/bin/env python3
"""Generate kestrel graphics runtime sensor policy from compiled DT (20 CPU zones).

Evidence-integrity fix (dt25-fix-v2):
- Project root derived from __file__; explicit --tag/--out/--dtb;
  tag syntax validated; intended output preflighted BEFORE DT reads and
  before any write; exclusive creation; no overwrite.
- Default OUT preserves the canonical builder policy path (immutable);
  tagged runs write to testing/boot-failure/dt25-thermal-fix-v2-policy-<tag>.json.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
T = Path(__file__).resolve().parent
K = Path('/home/builder/src/ksrc')
DTB_D = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
OUT_D = ROOT / 'builder/diagnostics/kestrel-graphics-policy.json'
BASE = Path('/home/builder/boot-failure-tests/dt25-baseline')

TAG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def fail(msg):
    print(f'ERROR: {msg}', file=sys.stderr)
    raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--tag', default=None)
parser.add_argument('--out', default=None)
parser.add_argument('--dtb', default=None)
args = parser.parse_args()

if args.tag is not None:
    if not TAG_RE.fullmatch(args.tag):
        fail(f'invalid --tag {args.tag!r}')
    OUT = T / f'dt25-thermal-fix-v2-policy-{args.tag}.json'
elif args.out:
    OUT = Path(args.out)
    try:
        rp = OUT.resolve()
        rd = ROOT.resolve()
        if rp != rd and rd not in rp.parents:
            fail(f'--out {OUT} escapes project root {ROOT}')
    except SystemExit:
        raise
    except Exception as e:
        fail(f'bad --out {OUT}: {e}')
else:
    OUT = OUT_D

DTB = Path(args.dtb) if args.dtb else DTB_D

# PREFLIGHT BEFORE any DT mutation-adjacent work or writes.
if OUT.exists():
    fail(f'refusing: intended output already exists (no bytes changed): {OUT}')
if not DTB.is_file():
    fail(f'dtb missing: {DTB}')


def fdt(node, prop=None, kind='s', listing=None):
    cmd = ['fdtget']
    if listing:
        cmd += [listing, str(DTB), node]
    else:
        cmd += ['-t', kind, str(DTB), node, prop]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


ph = {}
for label in ('tsens0', 'tsens1'):
    node = fdt('/__symbols__', label)
    p = fdt(node, 'phandle', 'x')
    ph[p] = label

zones = []
for name in (fdt('/thermal-zones', listing='-l') or '').splitlines():
    ref = (fdt('/thermal-zones/' + name, 'thermal-sensors', 'x') or '').split()
    if not ref or ref[0] not in ph:
        continue
    # only CPU core top/btm and cpuss top/btm (exclude aoss/mem/video)
    if name.startswith('cpu0-') or name.startswith('cpu1-') or name.startswith('cpuss0') or name.startswith('cpuss1'):
        zones.append({'name': name, 'provider': ph[ref[0]], 'sensor_id': ref[1:]})

names = sorted(z['name'] for z in zones)
assert len(names) == 20, f'expected 20 CPU/cpuss zones, got {len(names)}: {names}'
assert all(n.startswith(('cpu0-', 'cpu1-', 'cpuss0', 'cpuss1')) for n in names)
assert 'qcom-battmgr-bat' not in names, 'battery must never substitute SoC sensors'

policy = {
    'required_sensor_types': names,
    'required_sensor_count': len(names),
    'experiment_minimum_mc': 5000,
    'experiment_stop_mc': 80000,
    'battery_substitution_allowed': False,
    'platform_trips_modified': False,
    'cooling_maps_modified': False,
    'provenance': {
        'source_pin': '3f0d8691afa098ba378d7d5a3968f03219887719',
        'dtb': str(DTB),
        'dtb_sha256': hashlib.sha256(DTB.read_bytes()).hexdigest(),
        'dtb_bytes': DTB.stat().st_size,
        'baseline_board_dtb_sha256': hashlib.sha256((BASE / 'board.dtb').read_bytes()).hexdigest(),
        'derived_from': 'compiled /thermal-zones thermal-sensors suppliers on TSENS0/1',
        'providers': {'tsens0': [n for n in names if n.startswith(('cpu0-', 'cpuss0'))],
                      'tsens1': [n for n in names if n.startswith(('cpu1-', 'cpuss1'))]},
        'audit': 'dt25-thermal-source-evidence.json + dt25-thermal-audit.json (read-only)',
        'guard': 'builder/diagnostics/kestrel_graphics_guard.py evaluate_temperatures/evaluate_drm',
    },
    'scope': 'read-only preflight; sets no trips, clocks, voltages, fans, firmware or power state; 80C is a conservative experiment stop, not a platform trip',
    'native_graphics_validated': False,
    'read_only_preflight': True,
    'tag': args.tag,
}
with OUT.open('x') as f:
    json.dump(policy, f, indent=2)
print(json.dumps({'required_sensor_count': len(names), 'out': str(OUT)}, indent=2))
print('WROTE ' + str(OUT))
