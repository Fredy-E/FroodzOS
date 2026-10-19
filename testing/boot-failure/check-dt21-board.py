#!/usr/bin/env python3
"""Fail closed on the USB repeater bus's known permanent dependencies."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('dtb', type=Path)
parser.add_argument('--result', type=Path, required=True)
args = parser.parse_args()


def get(node, prop, kind='s'):
    run = subprocess.run(['fdtget', '-t', kind, str(args.dtb), node, prop], capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def symbol(name):
    value = get('/__symbols__', name)
    assert value, 'Missing compiled label: ' + name
    return value


i2c = symbol('i2c5')
gpi = symbol('gpi_dma0')
gem = symbol('gem_noc')
checks = {
    'usb_repeater_i2c5_enabled': get(i2c, 'status') == 'okay',
    'i2c5_no_dead_gem_icc_reference': get(i2c, 'interconnects', 'x') is None,
    'i2c5_no_stale_icc_names': get(i2c, 'interconnect-names') is None,
    'i2c5_dma_provider_enabled': get(gpi, 'status') == 'okay',
    'gpi0_existing_channel5_allowed': bool(int(get(gpi, 'dma-channel-mask', 'x') or '0', 16) & (1 << 5)),
    'gem_noc_stays_disabled': get(gem, 'status') == 'disabled',
    'gpu_stays_disabled': get(symbol('gpu'), 'status') == 'disabled',
    'gmu_stays_disabled': get(symbol('gmu'), 'status') == 'disabled',
    'mdss_stays_disabled': get(symbol('mdss'), 'status') == 'disabled',
}
for name in ('eusb3_repeater', 'eusb5_repeater', 'eusb6_repeater', 'eusb9_repeater'):
    node = symbol(name)
    checks[name + '_on_i2c5'] = node.startswith(i2c + '/') and get(node, 'compatible') == 'nxp,ptn3222'
result = {'passed': all(checks.values()), 'dtb': str(args.dtb), 'checks': checks,
          'native_hardware_validated': False}
with args.result.open('x') as output:
    json.dump(result, output, indent=2)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
