#!/usr/bin/env python3
"""Append 0015: apps-usb via config_noc (distinct endpoints, no duplicate)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
PORTS = {
    'usb_1_ss2': ('usb_south_anoc', 'MASTER_USB3_2', 'SLAVE_USB3_2'),
    'usb_2': ('usb_north_anoc', 'MASTER_USB2', 'SLAVE_USB2'),
    'usb_mp': ('usb_north_anoc', 'MASTER_USB3_MP', 'SLAVE_USB3_MP'),
    'usb_1_ss0': ('usb_south_anoc', 'MASTER_USB3_0', 'SLAVE_USB3_0'),
    'usb_1_ss1': ('usb_south_anoc', 'MASTER_USB3_1', 'SLAVE_USB3_1'),
}
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0015): apps-usb via config_noc. The 0014
 * duplicate-pair is rejected by the icc core (same route twice).
 * Point apps-usb at config_noc instead (stock shape, gem
 * replaced). If the graph lacks that link it still defers, and
 * the fallback is making apps-usb optional in dwc3-qcom.
 * Local-only, not for publication. */
'''
for label, (noc, master, slave) in PORTS.items():
    BLOCK += (f'&{label} {{ interconnects = <&{noc} {master} QCOM_ICC_TAG_ALWAYS '
              f'&mc_virt SLAVE_EBI1 QCOM_ICC_TAG_ALWAYS>, '
              f'<&{noc} {master} QCOM_ICC_TAG_ALWAYS '
              f'&config_noc {slave} QCOM_ICC_TAG_ALWAYS>; }};\n')
text = open(BOARD, errors='replace').read()
assert '(0014)' in text, '0014 block missing?'
assert '(0015)' not in text, '0015 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0015')
