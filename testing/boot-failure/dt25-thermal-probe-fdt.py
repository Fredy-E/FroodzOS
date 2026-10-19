#!/usr/bin/env python3
"""Probe fdtput mutation behavior on dtb copy (temp only)."""
import shutil
import subprocess
import tempfile
from pathlib import Path

SRC = Path('/home/builder/boot-failure-tests/dt25-baseline/board.dtb')
with tempfile.TemporaryDirectory(prefix='dt25-thermal-probe-', dir='/home/builder/boot-failure-tests') as tmp:
    dst = Path(tmp) / 'probe.dtb'
    shutil.copyfile(SRC, dst)
    def get(node, prop, kind='s'):
        r = subprocess.run(['fdtget', '-t', kind, str(dst), node, prop], capture_output=True, text=True)
        return (r.stdout.strip(), r.returncode)
    def put(node, prop, typ, val):
        r = subprocess.run(['fdtput', '-t', typ, str(dst), node, prop] + val, capture_output=True, text=True)
        return (r.stdout.strip(), r.stderr.strip(), r.returncode)
    print('STATUS', get('/soc@0/thermal-sensor@c271000', 'status'))
    print('PUT status', put('/soc@0/thermal-sensor@c271000', 'status', 's', ['okay']))
    print('STATUS2', get('/soc@0/thermal-sensor@c271000', 'status'))
    print('COMPAT', get('/soc@0/thermal-sensor@c271000', 'compatible'))
    print('REG', get('/soc@0/thermal-sensor@c271000', 'reg', 'x'))
    print('ZONESENS', get('/thermal-zones/cpu0-0-top-thermal', 'thermal-sensors', 'x'))
    print('ZONESENS TSENS2?', get('/thermal-zones/nsp0-thermal', 'thermal-sensors', 'x'))
    print('TSENS0 PH', get('/soc@0/thermal-sensor@c271000', 'phandle', 'x'))
    print('TSENS2 PH', get('/soc@0/thermal-sensor@c273000', 'phandle', 'x'))
    # try corrupting a zone supplier to tsens2 phandle
    tsens2ph = get('/soc@0/thermal-sensor@c273000', 'phandle', 'x')[0]
    print('TRY zone corrupt', put('/thermal-zones/cpu0-0-top-thermal', 'thermal-sensors', 'x', [tsens2ph, '1']))
    print('ZONESENS_AFTER', get('/thermal-zones/cpu0-0-top-thermal', 'thermal-sensors', 'x'))
print('PROBE_DONE')
