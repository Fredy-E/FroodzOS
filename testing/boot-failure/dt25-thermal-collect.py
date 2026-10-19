#!/usr/bin/env python3
"""Collect dt25 CPU-thermal source evidence (read-only). Writes dt25-thermal-source-evidence.json."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

K = Path('/home/builder/src/ksrc')
P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
BASE = Path('/home/builder/boot-failure-tests/dt25-baseline')
DTB = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
SRC = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
OUT = T / 'dt25-thermal-source-evidence.json'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def fdt(node, prop=None, kind='s', listing=None):
    cmd = ['fdtget']
    if listing:
        cmd += [listing, str(DTB), node]
    else:
        cmd += ['-t', kind, str(DTB), node, prop]
    out, _, rc = run(cmd)
    return out if rc == 0 else None


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# frozen baseline check
baseline_dts = (BASE / 'board.dts').read_bytes()
current_dts = SRC.read_bytes()
frozen_match = baseline_dts == current_dts

sensors = []
for label in ['tsens0', 'tsens1', 'tsens2', 'tsens3']:
    node = fdt('/__symbols__', label)
    props = {}
    plist = (fdt(node, listing='-p') or '').splitlines()
    for prop in plist:
        kind = 's' if prop in ('compatible', 'status', 'reg-names', 'interrupt-names', 'clock-names') else 'x'
        props[prop] = fdt(node, prop, kind)
    # prove no ICC/clock/regulator refs in compiled nodes
    for extra in ('interconnects', 'interconnect-names', 'clocks', 'clock-names', 'power-domains', 'required-opps', 'operating-points-v2'):
        v = fdt(node, extra, 'x')
        props['check_absent:' + extra] = v  # None means absent
    sensors.append({'label': label, 'path': node, 'properties': props})

# thermal zones with provider resolution
ph = {}
for s in sensors:
    phandle = s['properties'].get('phandle')
    if phandle:
        ph[phandle] = s['label']
zones = []
for name in (fdt('/thermal-zones', listing='-l') or '').splitlines():
    node = '/thermal-zones/' + name
    ref = (fdt(node, 'thermal-sensors', 'x') or '').split()
    if not ref or ref[0] not in ph:
        continue
    zones.append({'name': name, 'provider': ph[ref[0]], 'sensor_id': ref[1:]})

# 20 CPU target zones
cpu_targets = [z for z in zones if z['provider'] in ('tsens0', 'tsens1') and (
    z['name'].startswith('cpu0-') or z['name'].startswith('cpu1-') or z['name'].startswith('cpuss0') or z['name'].startswith('cpuss1'))]
cpu_names = sorted(z['name'] for z in cpu_targets)

# kernel config
cfg = (K / '.config').read_text(errors='replace').splitlines()
cfg_hits = [l for l in cfg if l.startswith('CONFIG_QCOM_TSENS=') or l.startswith('CONFIG_THERMAL=') or l.startswith('CONFIG_HWMON=') or l.startswith('CONFIG_THERMAL_OF=')]

# tsens driver source inspection (bounded)
snips = {}
for rel, pat, pad in [
    ('drivers/thermal/qcom/tsens.c', r'tsens_probe|data_tsens_v2|fallback|thermal_zone_of_sensor|devm_thermal', 6),
    ('drivers/thermal/qcom/tsens-v2.c', r'tsens_v2_data|hw_ids|init_tsens|ver_major|crit_int|sensors', 4),
]:
    path = K / rel
    lines = path.read_text(errors='replace').splitlines()
    sel = set()
    for i, line in enumerate(lines):
        if re.search(pat, line):
            for j in range(max(0, i - pad), min(len(lines), i + pad + 1)):
                sel.add(j)
    snips[rel] = {'sha256': sha(path), 'bytes': path.stat().st_size,
                  'selected': [f"{i+1}:{lines[i]}" for i in sorted(sel)][:220]}

report = {
    'frozen_match_baseline': frozen_match,
    'baseline_board_dts_sha256': sha(BASE / 'board.dts'),
    'current_board_dts_sha256': sha(SRC),
    'baseline_board_dtb_sha256': sha(BASE / 'board.dtb'),
    'current_board_dtb_sha256': sha(DTB),
    'source_pin': '3f0d8691afa098ba378d7d5a3968f03219887719',
    'sensor_nodes': sensors,
    'thermal_zones_cpu_targets': cpu_targets,
    'cpu_target_names_sorted': cpu_names,
    'cpu_target_count': len(cpu_names),
    'all_zones_count': len(zones),
    'kernel_config_hits': cfg_hits,
    'driver_snippets': snips,
    'read_only': True,
    'native_tsens_validated': False,
}
with OUT.open('x') as f:
    json.dump(report, f, indent=2)
print(json.dumps({k: report[k] for k in ('frozen_match_baseline', 'cpu_target_count', 'cpu_target_names_sorted', 'kernel_config_hits')}, indent=2))
print('WROTE ' + str(OUT))
