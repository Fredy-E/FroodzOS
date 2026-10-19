#!/usr/bin/env python3
"""Mutate disposable DTB copies to prove keyboard/safety predicates load-bearing."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
DTB = Path('/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb')
OLD = Path('/home/builder/boot-failure-tests/dt24-baseline/dt23.dtb')
assert shutil.which('fdtput'), 'fdtput required'


def get(image, node, prop, kind='s'):
    return subprocess.check_output(['fdtget', '-t', kind, str(image), node, prop], text=True).strip()


def symbol(name):
    return get(DTB, '/__symbols__', name)


i2c = symbol('i2c9')
rail = symbol('vreg_misc_3p3')
gpi = symbol('gpi_dma1')
cases = [
    ('rail-disabled', rail, 'status', 's', ['disabled'], 'keyboard_power_rail_enabled'),
    ('icc-restored', i2c, 'interconnects', 'x', get(OLD, i2c, 'interconnects', 'x').split(), 'i2c9_no_dead_gem_icc_reference'),
    ('icc-names-restored', i2c, 'interconnect-names', 's', ['qup-core', 'qup-config', 'qup-memory'], 'i2c9_no_stale_icc_names'),
    ('dma-disabled', gpi, 'status', 's', ['disabled'], 'keyboard_dma_provider_enabled'),
    ('channel1-masked', gpi, 'dma-channel-mask', 'x', ['3c'], 'gpi1_existing_channel1_allowed'),
    ('voltage-changed', rail, 'regulator-min-microvolt', 'u', ['3299999'], 'keyboard_power_voltage_unchanged'),
    ('gpu-enabled', symbol('gpu'), 'status', 's', ['okay'], 'gpu_stays_disabled'),
    ('nvme-rail-enabled', symbol('vreg_pcie3_nvme'), 'status', 's', ['okay'], 'vreg_pcie3_nvme_stays_disabled'),
]
results = []
for name, node, prop, kind, values, expected in cases:
    with tempfile.TemporaryDirectory(prefix='dt24-predicate-', dir='/home/builder/boot-failure-tests') as temp:
        fixture = Path(temp) / 'fixture.dtb'
        result = Path(temp) / 'result.json'
        shutil.copyfile(DTB, fixture)
        subprocess.run(['fdtput', '-t', kind, str(fixture), node, prop] + values, check=True)
        run = subprocess.run(['python3', str(T / 'check-dt24-board.py'), str(fixture), '--result', str(result)], capture_output=True, text=True)
        data = json.loads(result.read_text())
        bad = [key for key, value in data['checks'].items() if not value]
        assert run.returncode == 1 and bad == [expected], (name, run.returncode, bad)
        results.append({'fixture': name, 'failed_only_expected_predicate': expected, 'passed': True})
report = {'passed': True, 'cases': results, 'fixture_only': True, 'native_hardware_validated': False}
with (T / 'dt24-board-predicate-unit-result.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
