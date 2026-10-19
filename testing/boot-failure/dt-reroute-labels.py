#!/usr/bin/env python3
"""Append 0014: label-based USB reroute (replaces stale-number 0011)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
PORTS = {
    'usb_1_ss2': ('usb_south_anoc', 'MASTER_USB3_2'),
    'usb_2': ('usb_north_anoc', 'MASTER_USB2'),
    'usb_mp': ('usb_north_anoc', 'MASTER_USB3_MP'),
    'usb_1_ss0': ('usb_south_anoc', 'MASTER_USB3_0'),
    'usb_1_ss1': ('usb_south_anoc', 'MASTER_USB3_1'),
}
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0014): label-based USB reroute. Replaces
 * 0011, which used stale raw phandle numbers (one now resolves to
 * the cpucp mailbox, breaking path parsing). Each dwc3 apps-usb
 * path rerouted onto its own usb-ddr pair via &labels, which dtc
 * resolves at compile time. gem stays off. Local-only, not for
 * publication. */
'''
for label, (noc, master) in PORTS.items():
    BLOCK += (f'&{label} {{ interconnects = <&{noc} {master} QCOM_ICC_TAG_ALWAYS '
              f'&mc_virt SLAVE_EBI1 QCOM_ICC_TAG_ALWAYS>, '
              f'<&{noc} {master} QCOM_ICC_TAG_ALWAYS '
              f'&mc_virt SLAVE_EBI1 QCOM_ICC_TAG_ALWAYS>; }};\n')
text = open(BOARD, errors='replace').read()
assert '(0013)' in text, '0013 block missing?'
assert '(0014)' not in text, '0014 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0014')
