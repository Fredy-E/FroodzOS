#!/usr/bin/env python3
"""Fixture-only fail-closed session probes; no systemd actions are executed."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
tag = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out = T / ('dt26-parent-session-probe-' + tag + '.json')
assert not out.exists()
spec = importlib.util.spec_from_file_location('dt26_supervisor_probe', P / 'builder/diagnostics/kestrel-graphics-supervisor.py')
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


def runner_empty_detail(command, timeout=None):
    if command[:2] == ['loginctl', 'list-sessions']:
        return SimpleNamespace(returncode=0, stdout='c1 1001 builder seat0 tty1\n', stderr='')
    if command[:2] == ['loginctl', 'show-session']:
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    raise RuntimeError('fixture refuses unexpected command: ' + str(command))


def runner_partial_detail(command, timeout=None):
    if command[:2] == ['loginctl', 'list-sessions']:
        return SimpleNamespace(returncode=0, stdout='c1 1001 builder seat0 tty1\n', stderr='')
    if command[:2] == ['loginctl', 'show-session']:
        return SimpleNamespace(returncode=0, stdout='Id=c1\nUser=1001\nName=builder\n', stderr='')
    raise RuntimeError('fixture refuses unexpected command: ' + str(command))


valid_shape = {'Id': 'c9', 'User': '1000', 'Name': 'live', 'Seat': 'seat0', 'Type': 'wayland', 'Class': 'user', 'State': 'active', 'Service': 'sddm-autologin', 'Display': '', 'Remote': 'no', 'TTY': 'tty2'}
missing_remote = {k: v for k, v in valid_shape.items() if k != 'Remote'}
results = {
    'fixture_only': True,
    'native_graphics_validated': False,
    'real_schema_shaped_identity_accepted': supervisor.is_owned_session_detail(valid_shape, set()),
    'empty_success_detail': supervisor.get_session_detail(runner_empty_detail, 'c1'),
    'empty_detail_refuses_gui': supervisor.existing_gui_present(runner_empty_detail),
    'partial_detail_refuses_gui': supervisor.existing_gui_present(runner_partial_detail),
    'missing_remote_identity_accepted': supervisor.is_owned_session_detail(missing_remote, set()),
    'no_systemd_or_usb_writes': True,
}
with out.open('x') as stream:
    json.dump(results, stream, indent=2)
    stream.write('\n')
print(json.dumps(results, indent=2))
print('PARENT_SESSION_PROBE_RECEIPT', out)
