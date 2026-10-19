#!/usr/bin/env python3
"""Append 0011: gem back off; dwc3 apps-usb rerouted onto each port's own pair0."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
PAIR0 = {
    'usb_2': '0xe8 0x00 0x07 0x18 0x01 0x07',
    'usb_mp': '0xe8 0x01 0x07 0x18 0x01 0x07',
    'usb_1_ss0': '0xe5 0x00 0x07 0x18 0x01 0x07',
    'usb_1_ss1': '0xe5 0x01 0x07 0x18 0x01 0x07',
}
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0011): gem back off (its probe resets the
 * machine in 4s wall); reroute each dwc3 apps-usb path onto the
 * port's own usb-ddr pair so USB can bind without gem. Votes land
 * on the same working path twice (harmless for live boot).
 * Local-only, not for publication. */
&gem_noc { status = "disabled"; };
'''
for label, pair0 in PAIR0.items():
    BLOCK += f'&{label} {{ interconnects = <{pair0} {pair0}>; }};\n'
text = open(BOARD, errors='replace').read()
assert '(0010)' in text, '0010 block missing?'
assert '(0011)' not in text, '0011 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0011')
