#!/usr/bin/env python3
"""Independent final session/IO suites: real Linux, fresh receipt, no main()."""
import contextlib
import datetime
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
T = Path(__file__).resolve().parent
SUP = T.parents[1] / 'builder/diagnostics/kestrel-graphics-supervisor.py'
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = T / ('dt26-parent-session-final-' + TAG)
OUT.mkdir(exist_ok=False)
files = ['test-dt25-graphics-supervisor.py', 'test-dt26-session-supervisor.py',
         'test-dt26-session-fix.py', 'test-dt26-preflight-io.py']
with (OUT / 'result.json').open('x') as receipt, (OUT / 'tests.log').open('x') as log:
    source_sha = hashlib.sha256(SUP.read_bytes()).hexdigest()
    runs = []
    for i, leaf in enumerate(files):
        spec = importlib.util.spec_from_file_location('dt26_final_session_%s' % i, T / leaf)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        expected = suite.countTestCases()
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        runs.append({'suite': leaf, 'discovered': expected, 'run': result.testsRun,
                     'failures': len(result.failures), 'errors': len(result.errors),
                     'skipped': len(result.skipped), 'passed': result.wasSuccessful()
                     and expected > 0 and result.testsRun == expected and not result.skipped})
    report = {'source': str(SUP), 'sha256': source_sha,
              'source_unchanged': hashlib.sha256(SUP.read_bytes()).hexdigest() == source_sha,
              'suites': runs, 'total_run': sum(r['run'] for r in runs),
              'total_failures': sum(r['failures'] + r['errors'] for r in runs),
              'total_skipped': sum(r['skipped'] for r in runs),
              'passed': all(r['passed'] for r in runs), 'fixture_only': True,
              'native_graphics_validated': False, 'supervisor_main_executed': False}
    json.dump(report, receipt, indent=2)
print(OUT / 'result.json')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] and report['source_unchanged'] else 1)
