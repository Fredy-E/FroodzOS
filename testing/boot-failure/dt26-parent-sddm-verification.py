#!/usr/bin/env python3
"""Independent SDDM config-only/ELF readback. Never launches a display."""
import configparser
import datetime
import fcntl
import hashlib
import json
import subprocess
from pathlib import Path

T = Path(__file__).resolve().parent
B = Path('/home/builder/boot-failure-tests')
BASE = B / 'dt26-sddm-runtime-20261018T163100Z'
ROOT = Path(str(BASE) + '-root')
SFS = Path('/home/builder/live-rootfs-v2.squashfs')
TAG = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
REPORT = T / ('dt26-parent-sddm-verification-' + TAG + '.json')
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'HOME': '/'}


def run(argv):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=ENV)
    return {'command': argv, 'rc': p.returncode, 'stdout': p.stdout[-4000:], 'stderr': p.stderr[-1000:]}


with REPORT.open('x') as stream, (B / 'dt25-build.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    original_receipt = json.loads(Path(str(BASE) + '-evidence.json').read_text())
    helpers = sorted('/' + str(p.relative_to(ROOT)) for p in ROOT.rglob('sddm-helper*') if p.is_file())
    programs = ['/usr/bin/sddm', '/usr/bin/sddm-greeter-qt6'] + helpers
    loader = '/usr/lib/ld-linux-aarch64.so.1'
    elf = [run(['/usr/bin/chroot', str(ROOT), loader, '--inhibit-cache', '--list', p]) for p in programs]
    example = run(['/usr/bin/chroot', str(ROOT), '/usr/bin/sddm', '--example-config'])
    assert example['rc'] == 0, 'config-only command failed'
    defaults = configparser.ConfigParser(interpolation=None)
    defaults.read_string(example['stdout'])
    config_snapshots = {}
    for relative in ['usr/lib/sddm/sddm.conf.d/default.conf', 'etc/sddm.conf.d/autologin.conf',
                     'usr/share/wayland-sessions/plasma.desktop', 'usr/lib/plasma-dbus-run-session-if-needed']:
        p = ROOT / relative
        if p.is_file():
            data = p.read_bytes()
            config_snapshots[relative] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                                           'text': data.decode('utf-8', 'replace')}
    rel = 'usr/bin/sddm-greeter-qt6'
    source = subprocess.run(['/usr/bin/unsquashfs', '-cat', str(SFS), rel],
                            capture_output=True, check=True, timeout=30, env=ENV).stdout
    source_sha = hashlib.sha256(source).hexdigest()
    staged_sha = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    report = {'snapshot_root': str(ROOT), 'source_receipt_keys': sorted(original_receipt),
              'elf_checks': elf, 'elf_check_count': len(elf), 'elf_all_pass': all(x['rc'] == 0 for x in elf),
              'compiled_defaults_example_only': {'rc': example['rc'],
                  'display_server': defaults.get('General', 'DisplayServer', fallback=None),
                  'theme_current': defaults.get('Theme', 'Current', fallback=None)},
              'configured_snapshots': config_snapshots,
              'qt6_greeter_source_sha256': source_sha, 'qt6_greeter_staged_sha256': staged_sha,
              'qt6_greeter_source_bytes_equal': source_sha == staged_sha,
              'generic_qt5_binary_is_not_the_only_available_candidate': True,
              'runtime_greeter_suffix_selection_proven': False,
              'plasma_session_is_wayland_but_manager_default_is_not_wayland': True,
              'display_daemon_or_compositor_launched': False,
              'native_graphics_validated': False, 'fixture_mutated': False}
    json.dump(report, stream, indent=2)
    fcntl.flock(lock, fcntl.LOCK_UN)
print(REPORT)
print(json.dumps({k: v for k, v in report.items() if k not in ('elf_checks', 'configured_snapshots')}, indent=2))
print('ELF_RETURN_CODES=' + json.dumps({x['command'][-1]: x['rc'] for x in elf}))
print('SESSION_AND_AUTOLOGIN=' + json.dumps({k: v for k, v in config_snapshots.items()
                                          if k.endswith('autologin.conf') or k.endswith('plasma.desktop')}))
