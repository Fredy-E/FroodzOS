#!/usr/bin/env python3
"""Run artifact-gate tests and isolated literal/receipt-commit probes only."""
import ast
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
T = Path(__file__).resolve().parent
TAG = 'parent-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
REPORT = T / ('dt26-parent-artifact-gates-' + TAG + '.json')


def load(name, leaf):
    spec = importlib.util.spec_from_file_location(name, T / leaf)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


with REPORT.open('x') as report_file:
    log_path = T / ('dt26-parent-artifact-gates-' + TAG + '.log')
    with log_path.open('x') as log:
        cmd = [sys.executable, str(T / 'test-dt26-artifact-gates.py'), '--output-tag', TAG]
        suite = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=90,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    suite_result = T / ('dt26-artifact-gates-' + TAG + '-result.json')
    counts = json.loads(suite_result.read_text())
    build = load('dt26_parent_build_gates', 'build-dt26-live.py')
    audit = load('dt26_parent_audit_gates', 'audit-dt26-artifacts.py')
    parser = load('dt26_parent_artifact_parser', 'dt26-efi-parser.py')
    manifest = {'revision': 'v2-dt26', 'approved_for_build': True,
                'spec_review': 'PASS', 'quality_review': 'PASS',
                'sources': {rel: {'path': rel, 'sha256': 'a' * 64, 'bytes': 1}
                            for rel in build.REQUIRED_SOURCES}}
    def accepts_literal(obj):
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                build.validate_manifest_literal(obj)
            return True
        except (SystemExit, ValueError, TypeError):
            return False
    first = build.REQUIRED_SOURCES[0]
    bad_sha = json.loads(json.dumps(manifest))
    bad_sha['sources'][first]['sha256'] += '\n'
    bad_path = json.loads(json.dumps(manifest))
    bad_path['sources'][first]['path'] = 'wrong-prefix-' + first + '-wrong-suffix'
    literal_probes = {'sha_with_lf_accepted': accepts_literal(bad_sha),
                      'nonmatching_source_identifier_accepted': accepts_literal(bad_path)}
    reached = []
    class StopProbe(Exception):
        pass
    def loader_sentinel(_):
        reached.append('manifest-loader-after-invalid-tag')
        raise StopProbe()
    with patch.object(build, 'load_manifest', loader_sentinel):
        try:
            build.main(['--source-manifest', '/not-used-by-probe', '--tag', 'valid-name\n'])
        except StopProbe:
            pass
        except SystemExit:
            pass
    literal_probes['tag_lf_reaches_manifest_loader'] = bool(reached)
    fake_audit = {'passed': True, 'revision': 'v2-dt26', 'uki_sha256': 'a' * 64,
                  'initramfs_sha256': 'b' * 64, 'sfs_sha256': 'c' * 64,
                  'uki_bytes': 244424704, 'initramfs_bytes': 191570732, 'sfs_bytes': 1748525056,
                  'uki_path': '/home/builder/uki-v2-dt26-probe/vmlinuz-live.efi',
                  'initramfs_path': '/home/builder/uki-v2-dt26-probe/live-initramfs.img',
                  'sfs_path': str(audit.SFS), 'qemu_firmware': {'path': '/fixture/QEMU_EFI.fd',
                      'sha256': 'd' * 64, 'bytes': 3145728}, 'guard_policy': {'passed': True}}
    parser_ok, parser_errors, _ = parser.validate_audit_dict(fake_audit)
    with tempfile.TemporaryDirectory(prefix='dt26-parent-audit-commit-') as temp:
        tmp = Path(temp)
        receipt = tmp / 'dt26-artifact-audit.json'
        candidate = tmp / 'candidate-toy.efi'
        host_copy = tmp / 'host-copy-toy.efi'
        source_tree = ast.parse((T / 'audit-dt26-artifacts.py').read_text())
        fn = next(n for n in source_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_audit')
        nodes = [n for n in fn.body if 544 <= n.lineno <= 561]
        assert len(nodes) == 3, 'Commit code changed; re-read before probing'
        tail = compile(ast.Module(body=nodes, type_ignores=[]), str(T / 'audit-dt26-artifacts.py'), 'exec')
        real_open = Path.open
        def fail_host_open(path, *args, **kwargs):
            if path == host_copy:
                raise OSError('injected private host-copy write failure')
            return real_open(path, *args, **kwargs)
        ns = {'audit_json': receipt, 'candidate': candidate, 'data': b'NOT AN EFI: SYNTHETIC COMMIT TEST',
              'args': types.SimpleNamespace(host_copy=host_copy), 'json': json,
              'report': {'passed': True, 'uki_sha256': hashlib.sha256(b'NOT AN EFI: SYNTHETIC COMMIT TEST').hexdigest()},
              'sha_file': audit.sha_file, 'fail': audit.fail, 'Path': Path}
        try:
            with patch.object(Path, 'open', fail_host_open):
                exec(tail, ns)
            commit_error = None
        except OSError as exc:
            commit_error = str(exc)
        commit = {'scope': 'actual final commit AST, synthetic non-EFI bytes, injected copy error',
                  'error': commit_error, 'receipt_exists': receipt.exists(),
                  'receipt': json.loads(receipt.read_text()) if receipt.exists() else None}
    report = {'suite_rc': suite.returncode, 'suite_result': counts, 'suite_log': str(log_path),
              'literal_probes': literal_probes,
              'build_lock': str(build.LOCK), 'audit_lock': str(audit.LOCK),
              'required_shared_lock': '/home/builder/boot-failure-tests/dt25-build.lock',
              'sfs_path_integration': {'auditor_path': str(audit.SFS), 'synthetic_schema_fixture_only': True,
                                       'parser_accepted': parser_ok, 'errors': parser_errors},
              'premature_pass_receipt': commit, 'no_actual_build_extraction_or_vm': True,
              'accepted_for_build': False}
    json.dump(report, report_file, indent=2)
print(REPORT)
print(json.dumps(report, indent=2))
