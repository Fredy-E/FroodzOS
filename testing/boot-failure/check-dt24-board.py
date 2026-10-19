#!/usr/bin/env python3
"""Fail closed on the configured keyboard's known supplier dependencies."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('dtb', type=Path)
parser.add_argument('--result', type=Path, required=True)
args = parser.parse_args()


def get(node, prop, kind='s'):
    proc = subprocess.run(['fdtget', '-t', kind, str(args.dtb), node, prop], text=True, capture_output=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def symbol(name):
    node = get('/__symbols__', name)
    assert node, 'Missing compiled label: ' + name
    return node


i2c = symbol('i2c9')
rail = symbol('vreg_misc_3p3')
gpi = symbol('gpi_dma1')
keyboard = i2c + '/keyboard@3a'
dmas = (get(i2c, 'dmas', 'x') or '').split()
gpi_phandle = get(gpi, 'phandle', 'x')
checks = {
    'keyboard_bus_enabled': get(i2c, 'status') == 'okay',
    'keyboard_hid_binding_retained': get(keyboard, 'compatible') == 'hid-over-i2c',
    'keyboard_irq_retained': bool(get(keyboard, 'interrupts-extended', 'x')),
    'keyboard_power_rail_enabled': get(rail, 'status') == 'okay',
    'keyboard_power_supply_resolves': get(keyboard, 'vdd-supply', 'x') == get(rail, 'phandle', 'x'),
    'keyboard_power_voltage_unchanged': get(rail, 'regulator-min-microvolt', 'u') == '3300000' and get(rail, 'regulator-max-microvolt', 'u') == '3300000',
    'i2c9_no_dead_gem_icc_reference': get(i2c, 'interconnects', 'x') is None,
    'i2c9_no_stale_icc_names': get(i2c, 'interconnect-names') is None,
    'keyboard_dma_provider_enabled': get(gpi, 'status') == 'okay',
    'keyboard_dma_reference_retained': len(dmas) == 8 and dmas[0] == gpi_phandle and dmas[4] == gpi_phandle and dmas[1:4] == ['0', '1', '3'] and dmas[5:8] == ['1', '1', '3'],
    'gpi1_existing_channel1_allowed': bool(int(get(gpi, 'dma-channel-mask', 'x') or '0', 16) & (1 << 1)),
    'gem_remains_disabled': get(symbol('gem_noc'), 'status') == 'disabled',
}
for label in ['pcie3', 'pcie6a', 'pcie5', 'pcie4', 'gpu', 'gmu', 'mdss', 'vreg_pcie3_nvme']:
    checks[label + '_stays_disabled'] = get(symbol(label), 'status') == 'disabled'
report = {'passed': all(checks.values()), 'checks': checks, 'dtb': str(args.dtb),
          'skips_i2c9_bus_voting_diagnostic_only': True, 'native_hardware_validated': False}
with args.result.open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
