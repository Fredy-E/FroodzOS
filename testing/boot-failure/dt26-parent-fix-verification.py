#!/usr/bin/env python3
"""Independent Linux session rerun and isolated source-path counterexamples.

Never starts the shipped logger's mount/device gate, never creates /run fixtures,
FAT, VM, real sessions or USB writes. Every injected command is a private stub.
"""
import contextlib
import datetime
import errno
import hashlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
T = Path(__file__).resolve().parent
P = T.parents[1]
tag = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = T / ('dt26-parent-fix-verification-' + tag)
OUT.mkdir(exist_ok=False)
REPORT = OUT / 'result.json'
LOG = OUT / 'session.log'
assert not REPORT.exists() and not LOG.exists()
report_stream = REPORT.open('x')
log_stream = LOG.open('x')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_owned(argv, *, env=None, timeout=20):
    start = time.monotonic()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, start_new_session=True)
    killed = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        killed = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    return {'rc': proc.returncode, 'elapsed_s': round(time.monotonic() - start, 4),
            'stdout': stdout[-5000:], 'stderr': stderr[-2000:], 'outer_killed': killed}


try:
    names = ['test-dt25-graphics-supervisor.py', 'test-dt26-session-supervisor.py',
             'test-dt26-session-fix.py']
    source_files = [P / 'builder/diagnostics/kestrel-graphics-supervisor.py',
                    P / 'builder/diagnostics/kestrel-root-log.sh',
                    P / 'builder/diagnostics/kestrel-text-proof.sh']
    before = {str(f): sha(f) for f in source_files}
    session_results = []
    for i, name in enumerate(names):
        mod = load('dt26_parent_session_%s' % i, T / name)
        suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
        expected = suite.countTestCases()
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            result = unittest.TextTestRunner(stream=log_stream, verbosity=2).run(suite)
        session_results.append({'suite': name, 'discovered': expected,
                                'run': result.testsRun, 'failures': len(result.failures),
                                'errors': len(result.errors), 'skips': len(result.skipped),
                                'passed': result.wasSuccessful() and result.testsRun == expected
                                          and result.testsRun > 0 and not result.skipped})
    supervisor = load('dt26_parent_atomic_probe', source_files[0])
    root_source = source_files[1].read_text()
    func_start = root_source.index('persist_whitelisted_file() {')
    func_end = root_source.index('\npersist_graphics_journal() {', func_start)
    persist_function = root_source[func_start:func_end]
    loop_body = root_source[root_source.index('graphics_requested=0'):]
    with tempfile.TemporaryDirectory(prefix='dt26-parent-fix-probe-') as tmp:
        base = Path(tmp)
        dest = base / 'snapshot-dest'
        src = base / 'snapshot-src'
        dest.mkdir()
        src.mkdir()
        leaf = dest / '08-graphics-preflight.json'
        original = b'{"passed":false,"detail":{"reason":"last-good"}}'
        leaf.write_bytes(original)
        (src / 'preflight.json').write_text('{"passed":true,"detail":null}')
        shell = base / 'persist.sh'
        shell.write_text('set -u\ndest=$1\ngraphics_src_dir=$2\n' + persist_function
                         + '\npersist_whitelisted_file "$graphics_src_dir/preflight.json" '
                           '08-graphics-preflight.json 65536\n')
        null_run = run_owned(['/usr/bin/bash', str(shell), str(dest), str(src)])
        null_snapshot = {'scope': 'actual persist function isolated, not whole logger',
                         'process': null_run, 'last_good_preserved': leaf.read_bytes() == original,
                         'result': json.loads(leaf.read_text())}

        leaf.write_bytes(original)
        (src / 'preflight.json').write_bytes(original)
        spy_dir = base / 'spy'
        spy_dir.mkdir()
        spy_log = base / 'read-spy.jsonl'
        (spy_dir / 'sitecustomize.py').write_text('''import builtins, json, os
_original_open = builtins.open
_target = os.environ.get("DT26_SPY_TARGET")
_log = os.environ.get("DT26_SPY_LOG")
class Spy:
    def __init__(self, inner): self.inner = inner
    def __enter__(self): self.inner.__enter__(); return self
    def __exit__(self, *args): return self.inner.__exit__(*args)
    def __getattr__(self, name): return getattr(self.inner, name)
    def read(self, *args, **kwargs):
        with _original_open(_log, "a") as handle:
            handle.write(json.dumps({"args": list(args), "kwargs": kwargs}) + "\\n")
        return self.inner.read(*args, **kwargs)
def _open(file, mode="r", *args, **kwargs):
    inner = _original_open(file, mode, *args, **kwargs)
    return Spy(inner) if str(file) == _target and "r" in mode else inner
builtins.open = _open
''')
        spy_env = dict(os.environ, PYTHONPATH=str(spy_dir), DT26_SPY_TARGET=str(leaf),
                       DT26_SPY_LOG=str(spy_log))
        spy_run = run_owned(['/usr/bin/bash', str(shell), str(dest), str(src)], env=spy_env)
        old_reads = [json.loads(line) for line in spy_log.read_text().splitlines()] if spy_log.exists() else []

        atomic = base / 'preflight.json'
        atomic.write_bytes(original)
        with patch.object(supervisor.os, 'fsync', side_effect=OSError(errno.EIO, 'injected fixture fsync failure')):
            atomic_return = supervisor._atomic_write_json(atomic, {'passed': True, 'detail': {'new': True}})
        fsync_probe = {'scope': 'actual atomic writer, injected EIO only in this process',
                       'returned_success': atomic_return,
                       'last_good_preserved': atomic.read_bytes() == original,
                       'result': json.loads(atomic.read_text())}

        loops = []
        for kind in ['stale_timeout', 'term_resistant', 'missing_timeout']:
            case = base / kind
            case.mkdir()
            bins = case / 'bin'
            bins.mkdir()
            for name in ['cat', 'sync', 'python3', 'mktemp', 'mv', 'cmp', 'sleep', 'wc', 'rm', 'cp']:
                real = shutil.which(name)
                assert real, name
                (bins / name).symlink_to(real)
            if kind != 'missing_timeout':
                (bins / 'timeout').symlink_to(shutil.which('timeout'))
            j_sleep = '10' if kind == 'stale_timeout' else ('4' if kind == 'term_resistant' else '3')
            j_trap = "trap '' TERM\n" if kind == 'term_resistant' else ''
            (bins / 'journalctl').write_text('#!/usr/bin/bash\n' + j_trap + '/usr/bin/sleep ' + j_sleep + '\nprintf "fixture-journal\\n"\n')
            (bins / 'systemctl').write_text('#!/usr/bin/bash\n' + ('/usr/bin/sleep 10\n' if kind == 'stale_timeout' else '') + 'printf "running\\n"\n')
            for executable in ['journalctl', 'systemctl']:
                (bins / executable).chmod(0o755)
            data = case / 'dest'
            data.mkdir()
            graphs = case / 'graphics'
            graphs.mkdir()
            (graphs / 'preflight.json').write_text('{"passed":false,"detail":{}}')
            (graphs / 'status.json').write_text('{"reason":"fixture","bounded_cleanup":true}')
            cmdline = case / 'cmdline'
            cmdline.write_text('kestrel_graphics=1\n')
            program = case / 'loop.sh'
            program.write_text('set -u\ndest=$1\n' + loop_body)
            env = dict(os.environ, PATH=str(bins), KESTREL_CMDLINE_FILE=str(cmdline),
                       KESTREL_GRAPHICS_STATUS_DIR=str(graphs), KESTREL_LOGGER_BUDGET_S='2',
                       KESTREL_LOGGER_CALL_TIMEOUT_S='2', KESTREL_LOGGER_MAX_ITER='1')
            result = run_owned(['/usr/bin/bash', str(program), str(data)], env=env, timeout=15)
            result.update({'case': kind, 'budget_s': 2,
                           'scope': 'exact shipped post-validation logger loop, private command stubs, no /run fixture',
                           'finished_marker': (data / '00-status.txt').read_text() if (data / '00-status.txt').exists() else ''})
            loops.append(result)
        bash_features = run_owned(['/usr/bin/bash', '--noprofile', '--norc', '-c',
                                   'declare -p BASH_VERSION BASH_MONOSECONDS SECONDS'])
    report = {'session_suites': session_results,
              'session_total_run': sum(x['run'] for x in session_results),
              'session_all_pass_no_skips': all(x['passed'] for x in session_results),
              'detail_null_snapshot': null_snapshot,
              'old_destination_read': {'process': spy_run, 'observed_reads': old_reads},
              'supervisor_fsync_eio': fsync_probe, 'isolated_loop_cases': loops,
              'builder_bash_features_only': bash_features,
              'source_sha256': before,
              'sources_unchanged': all(sha(Path(f)) == digest for f, digest in before.items()),
              'no_vm_fat_usb_or_run_fixture': True, 'accepted_for_build': False}
    json.dump(report, report_stream, indent=2)
    print(str(REPORT))
    print(json.dumps(report, indent=2))
finally:
    report_stream.close()
    log_stream.close()
