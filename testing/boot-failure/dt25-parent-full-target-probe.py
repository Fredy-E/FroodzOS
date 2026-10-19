#!/usr/bin/env python3
"""Repeat only the full staged target check without unrelated manpage checks."""
import datetime
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile

B = Path('/home/builder/boot-failure-tests')
T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
OLD = T / 'dt25-parent-20261018T080733201702Z-integration-probe.json'
prior = json.loads(OLD.read_text())
oldbase = Path(prior['fixture'])
base = Path(tempfile.mkdtemp(dir=B, prefix='dt25-parent-full-target-'))
script = (oldbase / 'full-target-graph.sh').read_text()
assert f'BASE="{oldbase}"' in script
script = script.replace(f'BASE="{oldbase}"', f'BASE="{base}"')
assert 'systemd-analyze --root=' in script
script = script.replace('systemd-analyze --root=', 'systemd-analyze --man=no --root=')
helper = base / 'probe.sh'
helper.write_text(script)
with (B / 'dt25-build.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    proc = subprocess.run(['unshare', '--mount', '--propagation', 'private', 'bash', str(helper)], capture_output=True, text=True, timeout=120)
report = {
    'command_exit': proc.returncode,
    'stdout': proc.stdout,
    'stderr': proc.stderr,
    'man_checks_disabled_to_isolate_dependency_graph': True,
    'native_hardware_validated': False,
    'fixture': str(base),
    'source_units_unchanged': True,
    'multi_user_vendor_unit': Path('/home/builder/imgroot/usr/lib/systemd/system/multi-user.target').read_text(),
}
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
result = T / f'dt25-parent-{stamp}-full-target-graph.json'
with result.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps({'result_path': str(result), **report}, indent=2))
raise SystemExit(proc.returncode)
