#!/usr/bin/env python3
"""Read-only production probes; fixture writes and fresh receipts only."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
TAG = 'dt26-parent-probe-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
OUT = T / (TAG + '.json')
FIX = B / TAG
SFS = Path('/home/builder/live-rootfs-v2.squashfs')
assert not OUT.exists() and not FIX.exists(), 'preserve existing evidence'
FIX.mkdir(parents=True)
results = {'tag': TAG, 'fixtures': str(FIX), 'usb_writes': False, 'native_graphics_validated': False}


def func(text, name):
    match = re.search(r'(?ms)^' + re.escape(name) + r'\(\) \{\n.*?^\}', text)
    assert match, name
    return match.group(0)


def bash(code):
    return subprocess.run(['bash', '-c', code], capture_output=True, text=True, timeout=10, env=dict(os.environ, TMPDIR=str(FIX)))


log = (P / 'builder/diagnostics/kestrel-root-log.sh').read_text()
proof = (P / 'builder/diagnostics/kestrel-text-proof.sh').read_text()
persist = func(log, 'persist_whitelisted_file')
readout = func(proof, 'kestrel_cpu_thermal_readout')
dest = FIX / 'dest'
dest.mkdir()
source = FIX / 'status.json'
target = dest / '09-graphics-status.json'
valid = '{"reason":"last-good"}\n'
source.write_text('{"reason":')
target.write_text(valid)
run = bash('dest=' + str(dest) + '\nsync(){ :; }\n' + persist + '\npersist_whitelisted_file ' + str(source) + ' 09-graphics-status.json 65536\n')
results['partial_json_probe'] = {'exit': run.returncode, 'stderr': run.stderr, 'prior_valid_preserved': target.read_text() == valid, 'observed_bytes': target.read_text()}

# Fixture-only symlink escape; no real private data is read.
outside = FIX / 'outside-whitelist.txt'
outside.write_text('FIXTURE_NOT_A_GRAPHICS_STATUS')
link = FIX / 'linked-status.json'
link.symlink_to(outside)
target.write_text(valid)
run = bash('dest=' + str(dest) + '\nsync(){ :; }\n' + persist + '\npersist_whitelisted_file ' + str(link) + ' 09-graphics-status.json 65536\n')
results['source_symlink_probe'] = {'exit': run.returncode, 'prior_valid_preserved': target.read_text() == valid, 'outside_fixture_copied': target.read_text() == outside.read_text()}

# Deterministically grow a fixture after the size check, before the real copy.
source.write_text('{}')
target.write_text(valid)
run = bash('dest=' + str(dest) + '\nsync(){ :; }\nwc(){ command wc "$@"; printf "%0128d" 0 >> "$src"; }\n' + persist + '\npersist_whitelisted_file ' + str(source) + ' 09-graphics-status.json 32\n')
results['size_growth_probe'] = {'exit': run.returncode, 'configured_cap': 32, 'destination_bytes': target.stat().st_size, 'prior_valid_preserved': target.read_text() == valid}

thermal = FIX / 'thermal'
zone = thermal / 'thermal_zone0'
zone.mkdir(parents=True)
(zone / 'type').write_text('cpu0-0-top-thermal')
results['thermal_parse_probes'] = []
for value in ['42000', '08000', '-', '--1', '1-2']:
    (zone / 'temp').write_text(value)
    run = bash('thermal_root=' + str(thermal) + '\n' + readout + '\nkestrel_cpu_thermal_readout || true\n')
    results['thermal_parse_probes'].append({'input': value, 'exit': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr})

results['logger_clock_mechanism_present'] = bool(re.search(r'\bSECONDS\b|clock_gettime|time\.monotonic|date\s+\+%s', log))
results['logger_samples_not_seconds'] = 'total_samples=260' in log
show = subprocess.run(['systemctl', 'show', 'systemd-logind.service', '-p', 'ActiveState,SubState,Result'], capture_output=True, text=True, timeout=10)
results['systemctl_comma_properties_genuine'] = {'exit': show.returncode, 'stdout': show.stdout, 'stderr': show.stderr}

# The real frozen SFS listing is presence evidence, not a runtime-closure claim.
lock = B / 'dt25-build.lock'
with lock.open('a+') as handle:
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    listing = subprocess.run(['unsquashfs', '-ll', str(SFS)], capture_output=True, text=True, timeout=60)
    assert listing.returncode == 0, listing.stderr
    paths = {}
    for line in listing.stdout.splitlines():
        if 'squashfs-root/' in line:
            path = line.split('squashfs-root/', 1)[1].split(' -> ', 1)[0]
            paths[path] = line
    wanted = ['usr/bin/chvt', 'usr/bin/timeout', 'usr/bin/loginctl', 'usr/bin/systemctl', 'usr/bin/sddm', 'usr/bin/kwin_wayland', 'usr/bin/startplasma-wayland', 'usr/bin/dbus-run-session', 'etc/pam.d/sddm-autologin', 'usr/share/wayland-sessions/plasma.desktop', 'usr/lib/systemd/libsystemd-shared-262.so']
    results['frozen_sfs_presence'] = {name: paths.get(name) for name in wanted}
    comparisons = []
    for name in ['usr/bin/loginctl', 'usr/bin/systemctl', 'usr/lib/systemd/libsystemd-shared-262.so']:
        if name not in paths:
            comparisons.append({'path': name, 'present': False})
            continue
        data = subprocess.run(['unsquashfs', '-cat', str(SFS), name], capture_output=True, timeout=30)
        assert data.returncode == 0, (name, data.stderr)
        frozen_sha = hashlib.sha256(data.stdout).hexdigest()
        builder_file = Path('/') / name
        with builder_file.open('rb') as stream:
            builder_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        comparisons.append({'path': name, 'frozen_bytes': len(data.stdout), 'frozen_sha256': frozen_sha, 'builder_sha256': builder_sha, 'equal': frozen_sha == builder_sha})
    results['frozen_client_comparison'] = comparisons
    results['frozen_full_runtime_closure_proven'] = False

with OUT.open('x') as stream:
    json.dump(results, stream, indent=2)
    stream.write('\n')
print(json.dumps(results, indent=2))
print('PARENT_PROBE_RECEIPT', OUT)
