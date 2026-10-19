#!/usr/bin/env python3
"""Independent harness unit reruns + real-lock/private-mock safety probes.

Never allocates/formats media or starts QEMU; the launch-error probe uses an
explicit in-memory fake process and makes no real external state claim.
"""
import contextlib
import datetime
import errno
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
T = Path(__file__).resolve().parent
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = T / ('dt26-parent-harness-fix-verification-' + TAG)
OUT.mkdir(exist_ok=False)
REPORT = OUT / 'result.json'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with REPORT.open('x') as stream:
    files = ['dt26-prepare-efi-fixture.py', 'dt26-efi-harness.py',
             'dt26-efi-parser.py', 'dt26-efi-parser-test.py', 'dt26-harness-fix-test.py',
             'dt26-harness-lock-lifecycle-test.py']
    before = {name: sha(T / name) for name in files}
    runs = []
    for suite in ['dt26-efi-parser-test.py', 'dt26-harness-fix-test.py',
                  'dt26-harness-lock-lifecycle-test.py']:
        result_path = OUT / (suite + '.json')
        log_path = OUT / (suite + '.log')
        assert not result_path.exists() and not log_path.exists()
        with log_path.open('x') as log:
            proc = subprocess.run([sys.executable, str(T / suite), '--result', str(result_path)],
                                  stdout=log, stderr=subprocess.STDOUT, timeout=120,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                           PYTHONPYCACHEPREFIX=str(OUT / 'pycache')))
        data = json.loads(result_path.read_text())
        runs.append({'suite': suite, 'returncode': proc.returncode, 'result': data,
                     'log': str(log_path), 'path': str(result_path)})
    prep = load('dt26_parent_prepare_lock', T / files[0])
    harness = load('dt26_parent_harness_safety', T / files[1])
    with tempfile.TemporaryDirectory(prefix='dt26-parent-harness-lock-') as temp:
        base = Path(temp)
        lock = base / 'private-test.lock'
        prep.LOCK = lock
        holder_code = ('import fcntl,sys,time; f=open(sys.argv[1],"a+"); '
                       'fcntl.flock(f,fcntl.LOCK_EX); print("LOCKED",flush=True); time.sleep(20)')
        holder = subprocess.Popen([sys.executable, '-c', holder_code, str(lock)],
                                  stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            assert holder.stdout.readline().strip() == 'LOCKED'
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                try:
                    handle = prep.acquire_dt25_lock(lock_path=lock)
                except Exception as exc:
                    lock_result = {'refused': True, 'error': str(exc)}
                else:
                    lock_result = {'refused': False, 'returned_none': handle is None}
                    if handle is not None:
                        prep.release_dt25_lock(handle)
            lock_result.update({'scope': 'REAL fcntl contention on private fixture lock',
                                'holder_is_separate_child_not_parent_or_inherited_fd': True,
                                'stdout': captured.getvalue()})
        finally:
            if holder.poll() is None:
                os.killpg(holder.pid, signal.SIGKILL)
            holder.wait()

        fake_usage = types.SimpleNamespace(free=12 * 1024**3)
        with patch.object(harness.shutil, 'disk_usage', return_value=fake_usage):
            capacity_ok, observed = harness.disk_free_ok(pending_runtime=0, future_fixture_bytes=0)
            before_prepare_ok, _ = harness.disk_free_ok(pending_runtime=0, future_fixture_bytes=harness.FIXTURE_BYTES)
        incremental = {'scope': 'actual capacity function under BC already-allocated-FAT scenario',
                       'free_d_bytes': observed, 'pending_runtime_bytes': 0,
                       'future_fat_allocations': 0, 'accepted': capacity_ok,
                       'actual_free_above_reserve': observed > 10 * 1024**3,
                       'before_prepare_accepts_same_free': before_prepare_ok,
                       'formula_function': list(harness.capacity_plan(observed, 0, future_fixture_bytes=0))}

        host = base / 'T'
        guest = base / 'B'
        host.mkdir()
        guest.mkdir()
        harness.T, harness.B = host, guest
        prefix = 'dt26-efi-parent-log-failure'
        # Small non-FAT placeholder; all filesystem-tool calls are mocked.
        (guest / (prefix + '.fat')).write_bytes(b'NOT-A-FAT; PRIVATE PROBE ONLY\n')
        cfg = host / (prefix + '-grub.cfg')
        cfg.write_text('fixture-only menu bytes\n')
        log_target = host / (prefix + '-a.log')
        created = []
        class FakeProcess:
            def __init__(self):
                self.returncode = None
                self.terminated = False
                self.killed = False
                self.stdin = io.BytesIO()
                self.stdout = io.BytesIO()
            def poll(self): return self.returncode
            def terminate(self): self.terminated = True; self.returncode = 0
            def kill(self): self.killed = True; self.returncode = -9
            def wait(self, timeout=None): return self.returncode
        def fake_popen(*args, **kwargs):
            obj = FakeProcess()
            created.append(obj)
            return obj
        harness.fat_offset = lambda image: ({'partitions': [{'start': 2048}]}, 'PRIVATE-MOCK-NO-FAT')
        harness.mtype_hash = lambda fs, leaf: ('a' * 64 if leaf.endswith('.efi') else 'b' * 64)
        harness.check_guest_phases = lambda *args: None
        harness.subprocess = types.SimpleNamespace(Popen=fake_popen, PIPE=subprocess.PIPE,
                                                   STDOUT=subprocess.STDOUT,
                                                   check_output=lambda argv: cfg.read_bytes())
        real_open = Path.open
        def failing_log_open(path, *args, **kwargs):
            if path == log_target:
                raise OSError(errno.ENOSPC, 'injected private log-open failure')
            return real_open(path, *args, **kwargs)
        try:
            with patch.object(Path, 'open', failing_log_open), contextlib.redirect_stdout(io.StringIO()):
                harness.run_qemu(prefix, 'a', [], 60,
                                 {'uki_sha256': 'a' * 64, 'sfs_sha256': 'b' * 64}, None)
            failure = None
        except OSError as exc:
            failure = str(exc)
        launch = {'scope': 'actual run_qemu control path, FAKE process only, injected log ENOSPC',
                  'error': failure, 'fake_processes_created': len(created),
                  'fake_process_cleanup': [{'terminated': p.terminated, 'killed': p.killed,
                                            'returncode': p.returncode} for p in created]}
    report = {'unit_runs': runs,
              'unit_passed_total': sum(r['result']['passed'] for r in runs),
              'unit_failed_total': sum(r['result']['failed'] for r in runs),
              'unit_skipped_total': sum(r['result']['skipped'] for r in runs),
              'lock_contention': lock_result, 'bc_incremental_capacity': incremental,
              'log_open_failure_control_path': launch, 'source_sha256': before,
              'sources_unchanged': all(sha(T / leaf) == digest for leaf, digest in before.items()),
              'no_real_vm_or_fat': True, 'accepted_for_vm': False}
    json.dump(report, stream, indent=2)
print(REPORT)
print(json.dumps(report, indent=2))
