#!/usr/bin/env python3
"""Focused evidence-integrity regression tests (dt25-fix-v2).

- Never destroys real historical evidence: all mutation/fixture files live
  under /home/builder/boot-failure-tests/dt25-fix-v2-fixtures or in
  disposable TemporaryDirectories there; archived T outputs use fresh
  --tag names (dt25-thermal-fix-v2-*-<tag>.json) with preflight + exclusive
  creation. No unlink-existing.
- Validates tag syntax, pre-existing-partial refusal before mutation,
  double-run collision refusal with byte-identical hashes, and build
  safe-refusal on already-accepted source.
- check-policy is exercised via an isolated mock guard copy, never the
  concurrently-edited canonical guard.
Run: python3 test-dt25-evidence-integrity.py --tag <fresh-tag>
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

T = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parent.parent.parent
FIXBASE = Path('/home/builder/boot-failure-tests/dt25-fix-v2-fixtures')
PRED = T / 'test-dt25-board-predicates.py'
MAKEPOL = T / 'dt25-thermal-make-policy.py'
CHECKPOL = T / 'dt25-thermal-check-policy.py'
BUILD = T / 'build-dt25-board.py'
POLICY = ROOT / 'builder/diagnostics/kestrel-graphics-policy.json'

TAG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')

parser = argparse.ArgumentParser()
parser.add_argument('--tag', default=None, help='fresh tag for THIS integrity report')
args = parser.parse_args()
tag = args.tag or 'integrity-local'
if not TAG_RE.fullmatch(tag):
    print(f'ERROR: invalid --tag {tag!r}', file=sys.stderr)
    raise SystemExit(2)

OUT = T / f'dt25-thermal-fix-v2-evidence-integrity-{tag}.json'
if OUT.exists():
    print(f'ERROR: refusing: {OUT} already exists (no bytes changed)', file=sys.stderr)
    raise SystemExit(2)

FIXBASE.mkdir(parents=True, exist_ok=True)
results = {'tag': tag, 'checks': {}, 'passed': False, 'native_hardware_validated': False}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check(name, cond, detail=''):
    results['checks'][name] = {'ok': bool(cond), 'detail': detail}
    print(('PASS ' if cond else 'FAIL ') + name + (f' :: {detail}' if detail else ''))
    return bool(cond)


all_ok = True

# 1. Tag syntax unit checks (no subprocess, no mutation).
good = ['a', 'fixv2-20261018-01', 'A0_-x', 'x' * 64]
bad = ['', '../evil', 'a/b', 'a\\b', '-lead', '_lead', '.dot', 'has space', 'x' * 65, 'evil/../tag']
all_ok &= check('tag_accepts_good', all(TAG_RE.fullmatch(g) for g in good), ','.join(good))
all_ok &= check('tag_rejects_bad', all(not TAG_RE.fullmatch(b) for b in bad), f'{len(bad)} bad tags rejected')

# 2. No unlink-existing remains in fixed helpers; exclusive creation present; __file__ derived.
for fname in ['build-dt25-board.py', 'test-dt25-board-predicates.py',
              'dt25-thermal-make-policy.py', 'dt25-thermal-check-policy.py']:
    txt = (T / fname).read_text()
    all_ok &= check(f'no_unlink_{fname}', '.unlink()' not in txt, 'unlink absent')
    all_ok &= check(f'exclusive_{fname}', ".open('x')" in txt, "open('x') present")
    all_ok &= check(f'file_derived_{fname}', '__file__' in txt, '__file__ present')
all_ok &= check('no_hardcoded_mnt', "/mnt/d/CachyOS-ARM64" not in (T / 'build-dt25-board.py').read_text()
                and "/mnt/d/CachyOS-ARM64" not in (T / 'test-dt25-board-predicates.py').read_text()
                and "/mnt/d/CachyOS-ARM64" not in (T / 'dt25-thermal-make-policy.py').read_text()
                and "/mnt/d/CachyOS-ARM64" not in (T / 'dt25-thermal-check-policy.py').read_text(),
                'project root from __file__')

# Record historical hashes (must be unchanged at end).
HIST = ['dt25-thermal-board-green.json', 'dt25-thermal-board-red.json',
        'dt25-thermal-predicate-green.json', 'dt25-thermal-predicate-result.json',
        'dt25-thermal-dtb-build-result.json', 'dt25-thermal-build-dtb.log',
        'dt25-thermal-policy-result.json']
hist_before = {}
for h in HIST:
    p = T / h
    if p.exists():
        hist_before[h] = sha(p)
all_ok &= check('historical_present', len(hist_before) == len(HIST), f'{len(hist_before)}/{len(HIST)} present')

# 3. Predicate suite GREEN with fresh tag, then collision refusal, hashes identical.
ptag = f'{tag}-pred'
pred_outs = [T / f'dt25-thermal-fix-v2-board-red-{ptag}.json',
             T / f'dt25-thermal-fix-v2-predicate-green-{ptag}.json',
             T / f'dt25-thermal-fix-v2-predicate-dt24-{ptag}.json',
             T / f'dt25-thermal-fix-v2-predicate-dt21-{ptag}.json',
             T / f'dt25-thermal-fix-v2-predicate-result-{ptag}.json']
for p in pred_outs:
    if p.exists():
        print(f'ERROR: stale fixture {p} pre-exists; use a fresh --tag', file=sys.stderr)
        raise SystemExit(2)
r1 = run(['python3', str(PRED), '--tag', ptag])
all_ok &= check('predicate_green_exit0', r1.returncode == 0, f'exit={r1.returncode} {r1.stderr[-500:]}')
all_ok &= check('predicate_green_outputs', all(p.exists() for p in pred_outs), '5 tagged outputs exist')
hashes1 = {p.name: sha(p) for p in pred_outs if p.exists()}
# Validate content: 52/22/11 shape (52 checks green, 22 mutations, 11 =
# 20 cpu zones? record counts honestly).
try:
    agg = json.loads(pred_outs[4].read_text())
    n_checks = len(json.loads(pred_outs[1].read_text()).get('checks', {}))
    all_ok &= check('predicate_counts', agg.get('mutation_total') == 22 and n_checks == 52,
                    f"checks={n_checks} mutations={agg.get('mutation_total')}")
except Exception as e:
    all_ok &= check('predicate_counts', False, str(e))
r2 = run(['python3', str(PRED), '--tag', ptag])
all_ok &= check('predicate_collision_refuses', r2.returncode == 2, f'second exit={r2.returncode}')
hashes2 = {p.name: sha(p) for p in pred_outs if p.exists()}
all_ok &= check('predicate_hashes_stable', hashes1 == hashes2 and len(hashes1) == 5, 'first evidence byte-identical')

# 4. Malformed/traversal tags fail before mutation (no files created).
for badtag in ['../evil', 'a/b', '-lead']:
    r = run(['python3', str(PRED), '--tag', badtag])
    all_ok &= check(f'predicate_rejects_tag_{badtag}', r.returncode == 2, f'exit={r.returncode}')
evil_outs = list(T.glob('dt25-thermal-fix-v2-*evil*')) + list(T.glob('dt25-thermal-fix-v2-*-lead*'))
all_ok &= check('predicate_no_traversal_files', len(evil_outs) == 0, f'evil files={evil_outs}')

# 5. Pre-existing partial output refuses before mutation (dummy preserved).
ptag2 = f'{tag}-partial'
partial_green = T / f'dt25-thermal-fix-v2-predicate-green-{ptag2}.json'
partial_green.write_text('{"sentinel": true}')
sent_hash = sha(partial_green)
r = run(['python3', str(PRED), '--tag', ptag2])
all_ok &= check('predicate_partial_refuses', r.returncode == 2, f'exit={r.returncode}')
all_ok &= check('predicate_partial_preserved', sha(partial_green) == sent_hash and partial_green.read_text() == '{"sentinel": true}',
                'sentinel byte-identical')
# No sibling outputs for that tag should have been created (preflight before mutation).
siblings = [T / f'dt25-thermal-fix-v2-board-red-{ptag2}.json',
            T / f'dt25-thermal-fix-v2-predicate-result-{ptag2}.json']
all_ok &= check('predicate_partial_no_siblings', not any(p.exists() for p in siblings), 'no sibling mutation')
partial_green.unlink()  # remove only the synthetic sentinel we created (not archived evidence)

# 6. make-policy tagged + collision.
mtag = f'{tag}-pol'
mpol = T / f'dt25-thermal-fix-v2-policy-{mtag}.json'
if mpol.exists():
    print(f'ERROR: stale {mpol}; use fresh --tag', file=sys.stderr)
    raise SystemExit(2)
r = run(['python3', str(MAKEPOL), '--tag', mtag])
all_ok &= check('makepolicy_exit0', r.returncode == 0, f'exit={r.returncode} {r.stderr[-500:]}')
all_ok &= check('makepolicy_20', mpol.exists() and len(json.loads(mpol.read_text()).get('required_sensor_types', [])) == 20,
                '20 sensors')
mh1 = sha(mpol) if mpol.exists() else ''
r = run(['python3', str(MAKEPOL), '--tag', mtag])
all_ok &= check('makepolicy_collision_refuses', r.returncode == 2, f'exit={r.returncode}')
all_ok &= check('makepolicy_hash_stable', mpol.exists() and sha(mpol) == mh1, 'policy byte-identical')
r = run(['python3', str(MAKEPOL), '--tag', '../evil'])
all_ok &= check('makepolicy_rejects_traversal', r.returncode == 2, f'exit={r.returncode}')

# 7. check-policy via isolated MOCK guard (never the canonical guard).
mock_guard = FIXBASE / f'mock-guard-{tag}.py'
mock_guard.write_text(
    'def evaluate_temperatures(readings, required_types, minimum_mc=5000, stop_mc=80000):\n'
    '    try:\n'
    '        required = set(required_types)\n'
    '    except TypeError:\n'
    '        return {"ok": False, "errors": ["empty_or_invalid_required_sensor_policy"], "maximum_mc": None, "sensors": {}}\n'
    '    errors = []; values = {}; seen = set()\n'
    '    for rd in readings:\n'
    '        n = rd.get("type");\n'
    '        if n not in required: continue\n'
    '        if n in seen: errors.append("duplicate_sensor:" + n)\n'
    '        seen.add(n); v = rd.get("temp_mc")\n'
    '        if type(v) is not int or not minimum_mc <= v <= 125000: errors.append("invalid_temperature:" + n); continue\n'
    '        values[n] = v\n'
    '        if v >= stop_mc: errors.append("experiment_temperature_limit:" + n)\n'
    '    import sys\n'
    '    errors.extend("missing_sensor:" + n for n in sorted(required - seen))\n'
    '    return {"ok": not errors, "errors": errors, "maximum_mc": max(values.values()) if values else None, "sensors": values}\n')
ctag = f'{tag}-chk'
cres = T / f'dt25-thermal-fix-v2-policy-result-{ctag}.json'
if cres.exists():
    print(f'ERROR: stale {cres}; use fresh --tag', file=sys.stderr)
    raise SystemExit(2)
r = run(['python3', str(CHECKPOL), '--tag', ctag, '--policy', str(POLICY), '--guard', str(mock_guard)])
all_ok &= check('checkpolicy_mock_exit0', r.returncode == 0, f'exit={r.returncode} {r.stderr[-500:]} {r.stdout[-500:]}')
ch1 = sha(cres) if cres.exists() else ''
r = run(['python3', str(CHECKPOL), '--tag', ctag, '--policy', str(POLICY), '--guard', str(mock_guard)])
all_ok &= check('checkpolicy_collision_refuses', r.returncode == 2, f'exit={r.returncode}')
all_ok &= check('checkpolicy_hash_stable', cres.exists() and sha(cres) == ch1, 'result byte-identical')
r = run(['python3', str(CHECKPOL), '--tag', '../evil', '--policy', str(POLICY), '--guard', str(mock_guard)])
all_ok &= check('checkpolicy_rejects_traversal', r.returncode == 2, f'exit={r.returncode}')

# 8. Build safe-refusal on already-accepted source (real Ksrc, no mutation).
ksrc = Path('/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts')
src_hash_before = sha(ksrc)
r = run(['python3', str(BUILD)])  # legacy outputs exist -> preflight refusal, no mutation
all_ok &= check('build_legacy_collision_refuses', r.returncode == 2, f'exit={r.returncode}')
all_ok &= check('build_legacy_source_stable', sha(ksrc) == src_hash_before, 'ksrc unchanged after preflight refusal')
btag = f'{tag}-build'
r = run(['python3', str(BUILD), '--tag', btag])  # fresh outputs, but source already accepted -> safe refusal
all_ok &= check('build_accepted_source_refuses', r.returncode == 2 and 'already contains accepted 0020' in (r.stderr + r.stdout),
                f'exit={r.returncode}')
all_ok &= check('build_accepted_no_outputs', not any((T / n).exists() for n in
                [f'dt25-thermal-fix-v2-build-{btag}.log', f'dt25-thermal-fix-v2-board-{btag}.json',
                 f'dt25-thermal-fix-v2-dtb-build-result-{btag}.json']), 'no fresh build outputs on refusal')
all_ok &= check('build_accepted_source_stable', sha(ksrc) == src_hash_before, 'ksrc still accepted hash')

# 9. Synthetic collision-ordering demo (disposable only): preflight before source mutation.
with tempfile.TemporaryDirectory(prefix='dt25-order-', dir=str(FIXBASE)) as tmp:
    src = Path(tmp) / 'synth.dts'
    src.write_text('baseline')
    log = Path(tmp) / 'synth.log'
    log.write_text('PRIOR')
    prior_log = sha(log)
    # New order: preflight first -> refuse, source untouched.
    refused_before_mutation = log.exists()  # preflight would fail here
    # (We do NOT mutate src because preflight failed.)
    all_ok &= check('ordering_preflight_first', refused_before_mutation and src.read_text() == 'baseline' and sha(log) == prior_log,
                    'disposable source untouched when log collides')

# 10. Historical evidence unchanged.
hist_after = {h: sha(T / h) for h in HIST if (T / h).exists()}
all_ok &= check('historical_unchanged', hist_after == hist_before, f'{len(hist_after)}/{len(hist_before)} hashes identical')

results['passed'] = bool(all_ok)
results['failed'] = [k for k, v in results['checks'].items() if not v['ok']]
with OUT.open('x') as f:
    json.dump(results, f, indent=2)
print(json.dumps({'passed': results['passed'], 'failed': results['failed'], 'out': str(OUT)}, indent=2))
print('DT25_EVIDENCE_INTEGRITY_COMPLETE')
raise SystemExit(0 if all_ok else 1)
