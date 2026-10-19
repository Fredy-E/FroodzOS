#!/usr/bin/env python3
"""Read exact local TSENS/zone DT resources and bounded relevant source text."""
import json
import re
import subprocess
from pathlib import Path

K = Path('/home/builder/src/ksrc')
P = Path('/mnt/d/CachyOS-ARM64')
DTB = K / 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'


def fdt(node, prop=None, kind='s', listing=None):
    command = ['fdtget']
    if listing:
        command += [listing, str(DTB), node]
    else:
        command += ['-t', kind, str(DTB), node, prop]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


sensors = []
for label in ['tsens0', 'tsens1', 'tsens2', 'tsens3']:
    node = fdt('/__symbols__', label)
    assert node, label
    properties = {}
    for prop in (fdt(node, listing='-p') or '').splitlines():
        kind = 's' if prop in ['compatible', 'status', 'reg-names', 'interrupt-names', 'clock-names', 'nvmem-cell-names'] else 'x'
        properties[prop] = fdt(node, prop, kind)
    sensors.append({'label': label, 'path': node, 'properties': properties})
phandles = {row['properties']['phandle']: row['label'] for row in sensors}
zones = []
for name in (fdt('/thermal-zones', listing='-l') or '').splitlines():
    node = '/thermal-zones/' + name
    reference = (fdt(node, 'thermal-sensors', 'x') or '').split()
    if not reference or reference[0] not in phandles:
        continue
    zones.append({'name': name, 'provider': phandles[reference[0]], 'sensor_id': reference[1:],
                  'status': fdt(node, 'status'),
                  'polling_delay': fdt(node, 'polling-delay', 'u'),
                  'polling_delay_passive': fdt(node, 'polling-delay-passive', 'u'),
                  'children': fdt(node, listing='-l')})
report = {'sensor_nodes': sensors, 'thermal_zones': zones, 'source_pin': '3f0d8691afa098ba378d7d5a3968f03219887719',
          'read_only_audit': True, 'native_tsens_validated': False}
with (P / 'testing/boot-failure/dt25-thermal-audit.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
for relative, pattern, padding in [
    ('drivers/thermal/qcom/tsens.c', r'tsens_probe|devm_|icc_|clk_|power|qcom,tsens|thermal_zone_of_sensor|devm_thermal', 10),
    ('drivers/thermal/qcom/tsens-v2.c', r'init_tsens|tsens_v2_data|sensors|hw_ids', 8),
    ('drivers/thermal/qcom/Makefile', r'TSENS', 2),
    ('drivers/thermal/qcom/Kconfig', r'config QCOM_TSENS|THERMAL_OF|NVMEM|select|depends', 5),
]:
    path = K / relative
    lines = path.read_text().splitlines()
    selected = set()
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            selected.update(range(max(0, i - padding), min(len(lines), i + padding + 1)))
    print('SOURCE', relative)
    for i in sorted(selected):
        print(str(i + 1) + ':' + lines[i])
print('DT25_THERMAL_AUDIT_COMPLETE')
