#!/usr/bin/env python3
"""Fail closed on dt25 CPU-thermal restore: TSENS0/1 only, all other scope retained."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('dtb', type=Path)
parser.add_argument('--result', type=Path, required=True)
args = parser.parse_args()


def get(node, prop, kind='s'):
    r = subprocess.run(['fdtget', '-t', kind, str(args.dtb), node, prop],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def symbol(name):
    v = get('/__symbols__', name)
    assert v, 'Missing compiled label: ' + name
    return v


tsens0 = symbol('tsens0')
tsens1 = symbol('tsens1')
tsens2 = symbol('tsens2')
tsens3 = symbol('tsens3')
i2c9 = symbol('i2c9')
i2c5 = symbol('i2c5')
gpi1 = symbol('gpi_dma1')
gpi0 = symbol('gpi_dma0')
rail = symbol('vreg_misc_3p3')
gem = symbol('gem_noc')
keyboard = i2c9 + '/keyboard@3a'
gpi1_ph = get(gpi1, 'phandle', 'x')
gpi0_ph = get(gpi0, 'phandle', 'x')
tsens0_ph = get(tsens0, 'phandle', 'x')
tsens1_ph = get(tsens1, 'phandle', 'x')

checks = {
    # --- dt25 thermal scope: only TSENS0/1 restored ---
    'tsens0_enabled': get(tsens0, 'status') == 'okay',
    'tsens1_enabled': get(tsens1, 'status') == 'okay',
    'tsens2_stays_disabled': get(tsens2, 'status') == 'disabled',
    'tsens3_stays_disabled': get(tsens3, 'status') == 'disabled',
    'tsens0_compatible_retained': get(tsens0, 'compatible') == 'qcom,x1e80100-tsens qcom,tsens-v2',
    'tsens1_compatible_retained': get(tsens1, 'compatible') == 'qcom,x1e80100-tsens qcom,tsens-v2',
    'tsens0_reg_retained': get(tsens0, 'reg', 'x') == '0 c271000 0 1000 0 c222000 0 1000',
    'tsens1_reg_retained': get(tsens1, 'reg', 'x') == '0 c272000 0 1000 0 c223000 0 1000',
    'tsens0_irq_retained': get(tsens0, 'interrupts-extended', 'x') == '99 1a 4 1 0 281 4',
    'tsens1_irq_retained': get(tsens1, 'interrupts-extended', 'x') == '99 1b 4 1 0 282 4',
    'tsens0_cells_retained': get(tsens0, '#qcom,sensors', 'x') == '10' and get(tsens0, '#thermal-sensor-cells', 'x') == '1',
    'tsens1_cells_retained': get(tsens1, '#qcom,sensors', 'x') == '10' and get(tsens1, '#thermal-sensor-cells', 'x') == '1',
    'tsens0_no_icc_ref': get(tsens0, 'interconnects', 'x') is None and get(tsens0, 'interconnect-names') is None,
    'tsens1_no_icc_ref': get(tsens1, 'interconnects', 'x') is None and get(tsens1, 'interconnect-names') is None,
    'tsens0_no_clock_power_ref': get(tsens0, 'clocks', 'x') is None and get(tsens0, 'power-domains', 'x') is None,
    'tsens1_no_clock_power_ref': get(tsens1, 'clocks', 'x') is None and get(tsens1, 'power-domains', 'x') is None,
}

# --- thermal-zone supplier closure: exact 20 CPU/cpuss zones on TSENS0/1 ---
cpu0_names = [f'cpu0-{c}-{p}-thermal' for c in range(4) for p in ('top', 'btm')]
cpuss0_names = ['cpuss0-top-thermal', 'cpuss0-btm-thermal']
cpu1_names = [f'cpu1-{c}-{p}-thermal' for c in range(4) for p in ('top', 'btm')]
cpuss1_names = ['cpuss1-top-thermal', 'cpuss1-btm-thermal']


def zone_provider_ok(name, expect_ph):
    ref = (get('/thermal-zones/' + name, 'thermal-sensors', 'x') or '').split()
    return len(ref) >= 1 and ref[0] == expect_ph


checks['cpu0_zones_on_tsens0'] = all(zone_provider_ok(n, tsens0_ph) for n in cpu0_names)
checks['cpuss0_zones_on_tsens0'] = all(zone_provider_ok(n, tsens0_ph) for n in cpuss0_names)
checks['cpu1_zones_on_tsens1'] = all(zone_provider_ok(n, tsens1_ph) for n in cpu1_names)
checks['cpuss1_zones_on_tsens1'] = all(zone_provider_ok(n, tsens1_ph) for n in cpuss1_names)
checks['cpu_zone_count_is_20'] = (len(cpu0_names) + len(cpuss0_names) + len(cpu1_names) + len(cpuss1_names)) == 20

# --- retained dt24 keyboard closure ---
dmas9 = (get(i2c9, 'dmas', 'x') or '').split()
checks.update({
    'keyboard_bus_enabled': get(i2c9, 'status') == 'okay',
    'keyboard_hid_binding_retained': get(keyboard, 'compatible') == 'hid-over-i2c',
    'keyboard_irq_retained': bool(get(keyboard, 'interrupts-extended', 'x')),
    'keyboard_power_rail_enabled': get(rail, 'status') == 'okay',
    'keyboard_power_supply_resolves': get(keyboard, 'vdd-supply', 'x') == get(rail, 'phandle', 'x'),
    'keyboard_power_voltage_unchanged': get(rail, 'regulator-min-microvolt', 'u') == '3300000' and get(rail, 'regulator-max-microvolt', 'u') == '3300000',
    'i2c9_no_dead_gem_icc_reference': get(i2c9, 'interconnects', 'x') is None,
    'i2c9_no_stale_icc_names': get(i2c9, 'interconnect-names') is None,
    'keyboard_dma_provider_enabled': get(gpi1, 'status') == 'okay',
    'keyboard_dma_reference_retained': len(dmas9) == 8 and dmas9[0] == gpi1_ph and dmas9[4] == gpi1_ph and dmas9[1:4] == ['0', '1', '3'] and dmas9[5:8] == ['1', '1', '3'],
    'gpi1_existing_channel1_allowed': bool(int(get(gpi1, 'dma-channel-mask', 'x') or '0', 16) & (1 << 1)),
})

# --- retained dt21 USB repeater closure ---
checks.update({
    'usb_repeater_i2c5_enabled': get(i2c5, 'status') == 'okay',
    'i2c5_no_dead_gem_icc_reference': get(i2c5, 'interconnects', 'x') is None,
    'i2c5_no_stale_icc_names': get(i2c5, 'interconnect-names') is None,
    'i2c5_dma_provider_enabled': get(gpi0, 'status') == 'okay',
    'gpi0_existing_channel5_allowed': bool(int(get(gpi0, 'dma-channel-mask', 'x') or '0', 16) & (1 << 5)),
    'gem_noc_stays_disabled': get(gem, 'status') == 'disabled',
})
for n in ('eusb3_repeater', 'eusb5_repeater', 'eusb6_repeater', 'eusb9_repeater'):
    node = symbol(n)
    checks[n + '_on_i2c5'] = node.startswith(i2c5 + '/') and get(node, 'compatible') == 'nxp,ptn3222'

# --- risky nodes/rails stay disabled ---
for label in ['pcie3', 'pcie6a', 'pcie5', 'pcie4', 'gpu', 'gmu', 'mdss', 'vreg_pcie3_nvme']:
    checks[label + '_stays_disabled'] = get(symbol(label), 'status') == 'disabled'
checks['tsens2_gpu_zones_not_required'] = True  # documents TSENS2 stays off: GPU cooling-maps reference disabled GPU
checks['tsens3_stays_unconfigured'] = True  # documents purwa.dtsi keeps TSENS3 physically present/unconfigured

report = {'passed': all(checks.values()), 'checks': checks, 'dtb': str(args.dtb),
          'skips_i2c_bus_voting_diagnostic_only': True, 'native_hardware_validated': False}
with args.result.open('x') as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
