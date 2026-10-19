#!/usr/bin/env python3
"""RED on frozen dt25 baseline, GREEN on built dtb, per-clause mutation proof.

Evidence-integrity fix (dt25-fix-v2):
- Project root derived from __file__; explicit --tag or explicit result
  paths; tag syntax validated; ALL T outputs preflighted BEFORE any
  copy/fdtput/checker mutation; exclusive creation; no unlink-existing.
- Mutation check outputs live in a disposable fixture dir under
  /home/builder/boot-failure-tests (never in archived T), so tmp cleanup
  deletes only disposable files and archived evidence is never removed.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

T = Path(__file__).resolve().parent
K = Path('/home/builder/src/ksrc')
BASE_DTB_D = Path('/home/builder/boot-failure-tests/dt25-baseline/board.dtb')
NEW_DTB_D = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
CHECK_D = T / 'check-dt25-board.py'
FIXBASE = Path('/home/builder/boot-failure-tests/dt25-fix-v2-fixtures')

TAG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def fail(msg):
    print(f'ERROR: {msg}', file=sys.stderr)
    raise SystemExit(2)


def validate_tag(tag):
    if not TAG_RE.fullmatch(tag):
        fail(f'invalid --tag {tag!r}: must match {TAG_RE.pattern}')
    return tag


def must_be_in_T(p, what):
    try:
        rp = Path(p).resolve()
        td = T.resolve()
        if rp != td and td not in rp.parents:
            fail(f'{what} {p} escapes evidence dir {T}')
    except SystemExit:
        raise
    except Exception as e:
        fail(f'bad {what} {p}: {e}')
    return Path(p)


parser = argparse.ArgumentParser()
parser.add_argument('--tag', default=None)
parser.add_argument('--red-result', default=None)
parser.add_argument('--green-result', default=None)
parser.add_argument('--dt24-result', default=None)
parser.add_argument('--dt21-result', default=None)
parser.add_argument('--result', default=None)
parser.add_argument('--base-dtb', default=None)
parser.add_argument('--new-dtb', default=None)
parser.add_argument('--check', default=None)
args = parser.parse_args()

if args.tag is not None:
    validate_tag(args.tag)
    red_p = T / f'dt25-thermal-fix-v2-board-red-{args.tag}.json'
    green_p = T / f'dt25-thermal-fix-v2-predicate-green-{args.tag}.json'
    dt24_p = T / f'dt25-thermal-fix-v2-predicate-dt24-{args.tag}.json'
    dt21_p = T / f'dt25-thermal-fix-v2-predicate-dt21-{args.tag}.json'
    agg_p = T / f'dt25-thermal-fix-v2-predicate-result-{args.tag}.json'
else:
    red_p = T / 'dt25-thermal-board-red.json'
    green_p = T / 'dt25-thermal-predicate-green.json'
    dt24_p = T / 'dt25-thermal-predicate-dt24-green.json'
    dt21_p = T / 'dt25-thermal-predicate-dt21-green.json'
    agg_p = T / 'dt25-thermal-predicate-result.json'

if args.red_result:
    red_p = must_be_in_T(args.red_result, '--red-result')
if args.green_result:
    green_p = must_be_in_T(args.green_result, '--green-result')
if args.dt24_result:
    dt24_p = must_be_in_T(args.dt24_result, '--dt24-result')
if args.dt21_result:
    dt21_p = must_be_in_T(args.dt21_result, '--dt21-result')
if args.result:
    agg_p = must_be_in_T(args.result, '--result')

BASE_DTB = Path(args.base_dtb) if args.base_dtb else BASE_DTB_D
NEW_DTB = Path(args.new_dtb) if args.new_dtb else NEW_DTB_D
CHECK = Path(args.check) if args.check else CHECK_D

# PREFLIGHT ALL archived outputs BEFORE any copy/fdtput/subprocess mutation.
existing = [str(p) for p in (red_p, green_p, dt24_p, dt21_p, agg_p) if p.exists()]
if existing:
    fail('refusing: intended output(s) already exist (no bytes changed): ' + ', '.join(existing))
if not BASE_DTB.is_file():
    fail(f'base dtb missing: {BASE_DTB}')
if not NEW_DTB.is_file():
    fail(f'new dtb missing: {NEW_DTB}')
if not CHECK.is_file():
    fail(f'checker missing: {CHECK}')

results = {'red': None, 'green': None, 'mutations': [], 'retained': {}, 'tag': args.tag}


def run_check(dtb, rp):
    # No unlink: rp was preflighted absent; checker uses exclusive creation.
    r = subprocess.run(['python3', str(CHECK), str(dtb), '--result', str(rp)],
                       capture_output=True, text=True)
    data = json.loads(rp.read_text()) if rp.exists() else {'passed': False, 'checks': {}}
    return r.returncode, data, rp


# RED on frozen baseline (all tsens disabled)
rc, data, rp = run_check(BASE_DTB, red_p)
results['red'] = {'exit': rc, 'passed': data.get('passed'),
                  'tsens0_enabled': data.get('checks', {}).get('tsens0_enabled'),
                  'tsens1_enabled': data.get('checks', {}).get('tsens1_enabled'),
                  'result': str(rp)}
assert rc != 0 and not data.get('passed'), 'RED failed: baseline should not pass dt25 check'
assert data['checks']['tsens0_enabled'] is False and data['checks']['tsens1_enabled'] is False

# GREEN on built dtb
rc, data, rp = run_check(NEW_DTB, green_p)
results['green'] = {'exit': rc, 'passed': data.get('passed'), 'failed': [k for k, v in data.get('checks', {}).items() if not v], 'result': str(rp)}
assert rc == 0 and data.get('passed'), f"GREEN failed: {results['green']['failed']}"

# retained dt24/dt21 gates
for script, rp in [('check-dt24-board.py', dt24_p),
                   ('check-dt21-board.py', dt21_p)]:
    r = subprocess.run(['python3', str(T / script), str(NEW_DTB), '--result', str(rp)],
                       capture_output=True, text=True, check=True)
    d = json.loads(rp.read_text())
    assert d.get('passed'), f'{script} retained gate failed'
    results['retained'][script] = {'passed': True, 'result': str(rp)}

# per-clause mutations
def symmap():
    m = {}
    for n in ['tsens0', 'tsens1', 'tsens2', 'tsens3', 'i2c9', 'i2c5', 'gpi_dma1', 'gpi_dma0',
              'vreg_misc_3p3', 'gem_noc', 'gpu', 'gmu', 'mdss', 'pcie3', 'vreg_pcie3_nvme',
              'eusb3_repeater']:
        m[n] = subprocess.check_output(['fdtget', '-t', 's', str(NEW_DTB), '/__symbols__', n], text=True).strip()
    m['tsens0_path'] = m['tsens0']
    return m

S = symmap()
tsens2ph = subprocess.check_output(['fdtget', '-t', 'x', str(NEW_DTB), S['tsens2'], 'phandle'], text=True).strip()

MUTS = [
    ('tsens0_enabled', S['tsens0'], 'status', 's', ['disabled'], 'tsens0_enabled'),
    ('tsens1_enabled', S['tsens1'], 'status', 's', ['disabled'], 'tsens1_enabled'),
    ('tsens2_stays_disabled', S['tsens2'], 'status', 's', ['okay'], 'tsens2_stays_disabled'),
    ('tsens3_stays_disabled', S['tsens3'], 'status', 's', ['okay'], 'tsens3_stays_disabled'),
    ('tsens0_compatible', S['tsens0'], 'compatible', 's', ['wrong-compat'], 'tsens0_compatible_retained'),
    ('tsens0_reg', S['tsens0'], 'reg', 'x', ['0', '0', '0', '1000', '0', 'c222000', '0', '1000'], 'tsens0_reg_retained'),
    ('tsens0_irq', S['tsens0'], 'interrupts-extended', 'x', ['99', 'ff', '4', '1', '0', '281', '4'], 'tsens0_irq_retained'),
    ('cpu0_zone_supplier', '/thermal-zones/cpu0-0-top-thermal', 'thermal-sensors', 'x', [tsens2ph, '1'], 'cpu0_zones_on_tsens0'),
    ('cpuss0_zone_supplier', '/thermal-zones/cpuss0-top-thermal', 'thermal-sensors', 'x', [tsens2ph, '1'], 'cpuss0_zones_on_tsens0'),
    ('cpu1_zone_supplier', '/thermal-zones/cpu1-0-top-thermal', 'thermal-sensors', 'x', [tsens2ph, '1'], 'cpu1_zones_on_tsens1'),
    ('cpuss1_zone_supplier', '/thermal-zones/cpuss1-top-thermal', 'thermal-sensors', 'x', [tsens2ph, '1'], 'cpuss1_zones_on_tsens1'),
    ('keyboard_bus', S['i2c9'], 'status', 's', ['disabled'], 'keyboard_bus_enabled'),
    ('keyboard_rail', S['vreg_misc_3p3'], 'status', 's', ['disabled'], 'keyboard_power_rail_enabled'),
    ('keyboard_dma', S['gpi_dma1'], 'status', 's', ['disabled'], 'keyboard_dma_provider_enabled'),
    ('usb_bus', S['i2c5'], 'status', 's', ['disabled'], 'usb_repeater_i2c5_enabled'),
    ('usb_dma', S['gpi_dma0'], 'status', 's', ['disabled'], 'i2c5_dma_provider_enabled'),
    ('gem_disabled', S['gem_noc'], 'status', 's', ['okay'], 'gem_noc_stays_disabled'),
    ('gpu_disabled', S['gpu'], 'status', 's', ['okay'], 'gpu_stays_disabled'),
    ('gmu_disabled', S['gmu'], 'status', 's', ['okay'], 'gmu_stays_disabled'),
    ('mdss_disabled', S['mdss'], 'status', 's', ['okay'], 'mdss_stays_disabled'),
    ('pcie3_disabled', S['pcie3'], 'status', 's', ['okay'], 'pcie3_stays_disabled'),
    ('nvme_rail_disabled', S['vreg_pcie3_nvme'], 'status', 's', ['okay'], 'vreg_pcie3_nvme_stays_disabled'),
]

mut_pass = 0
try:
    FIXBASE.mkdir(parents=True, exist_ok=True)
except PermissionError:
    fail(f'fixture base not writable: {FIXBASE}')
with tempfile.TemporaryDirectory(prefix='dt25-thermal-mut-', dir=str(FIXBASE)) as tmp:
    for label, node, prop, kind, bad, expect_key in MUTS:
        dst = Path(tmp) / (label + '.dtb')
        shutil.copyfile(NEW_DTB, dst)
        pr = subprocess.run(['fdtput', '-t', kind, str(dst), node, prop] + bad,
                            capture_output=True, text=True)
        assert pr.returncode == 0, f'fdtput failed for {label}: {pr.stderr}'
        # Mutation check outputs live ONLY in the disposable fixture dir,
        # never in archived T; tmp cleanup removes solely disposable files.
        rp = Path(tmp) / f'dt25-thermal-mut-{label}.json'
        r = subprocess.run(['python3', str(CHECK), str(dst), '--result', str(rp)],
                           capture_output=True, text=True)
        d = json.loads(rp.read_text())
        ok = (r.returncode != 0 and not d.get('passed') and d.get('checks', {}).get(expect_key) is False)
        results['mutations'].append({'label': label, 'expect_failed': expect_key,
                                     'overall_failed': not d.get('passed'),
                                     'clause_failed': d.get('checks', {}).get(expect_key) is False,
                                     'load_bearing': ok})
        assert ok, f'Mutation not load-bearing: {label}'
        mut_pass += 1

results.update({'mutation_tests': mut_pass, 'mutation_total': len(MUTS),
                'passed': True, 'native_hardware_validated': False,
                'note': 'RED on frozen baseline, GREEN on built dtb, each clause proven by single-property fixture'})
with agg_p.open('x') as f:
    json.dump(results, f, indent=2)
print(json.dumps({'red_exit': results['red']['exit'], 'red_passed': results['red']['passed'],
                  'green_exit': results['green']['exit'], 'green_passed': results['green']['passed'],
                  'mutations_passed': mut_pass, 'mutations_total': len(MUTS),
                  'retained': results['retained'], 'tag': args.tag}, indent=2))
print('DT25_PREDICATES_COMPLETE')
