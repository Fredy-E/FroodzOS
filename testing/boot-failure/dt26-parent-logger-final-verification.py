#!/usr/bin/env python3
"""Parent independent rerun: 9+9+9+6 logger suites, fresh receipt, no main."""
import datetime, hashlib, json, os, subprocess, sys
from pathlib import Path
T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = T / ('dt26-parent-logger-final-' + TAG)
OUT.mkdir(exist_ok=False)
suites = ['test-dt26-observability.py', 'test-dt26-observability-fix.py',
          'test-dt26-observability-bounds.py', 'test-dt26-logger-watchdog.py']
logger = T.parents[1] / 'builder/diagnostics/kestrel-root-log.sh'
before = {n: hashlib.sha256((T/n).read_bytes()).hexdigest() for n in suites}
before['kestrel-root-log.sh'] = hashlib.sha256(logger.read_bytes()).hexdigest()
runs = []
for s in suites:
    prefix = str(OUT / s.replace('.py','-parent'))
    env = {k: v for k, v in os.environ.items() if k != 'TMPDIR'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.run([sys.executable, str(T/s), '--out-prefix', prefix],
                       capture_output=True, text=True, timeout=300, env=env)
    runs.append({'suite': s, 'rc': p.returncode, 'stdout_tail': p.stdout[-500:],
                 'stderr_tail': p.stderr[-500:]})
    try:
        r = json.loads(Path(prefix + '.json').read_text() if not Path(prefix+'.json').is_dir() else '{}')
    except Exception as e:
        r = {'read_error': str(e)}
    runs[-1]['result'] = r
after = {n: hashlib.sha256((T/n).read_bytes()).hexdigest() for n in suites}
after['kestrel-root-log.sh'] = hashlib.sha256(logger.read_bytes()).hexdigest()
total_pass = sum(int(r['result'].get('passed', -1)) for r in runs if isinstance(r.get('result'), dict) and 'passed' in r['result'])
total_fail = sum(int(r['result'].get('failed', 0)) + int(r['result'].get('errors', 0)) for r in runs if isinstance(r.get('result'), dict))
total_skip = sum(int(r['result'].get('skipped', 0)) for r in runs if isinstance(r.get('result'), dict))
report = {'tag': TAG, 'before': before, 'after': after, 'unchanged': before == after,
          'runs': runs, 'total_passed': total_pass, 'total_failed': total_fail,
          'total_skipped': total_skip,
          'passed': before == after and all(r['rc'] == 0 for r in runs) and total_fail == 0 and total_skip == 0,
          'fixture_only': True, 'native_graphics_validated': False}
(OUT / 'result.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
