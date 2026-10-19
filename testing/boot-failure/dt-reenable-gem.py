#!/usr/bin/env python3
"""Append 0010: re-enable gem_noc (dwc3 apps-usb path needs it)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0010): re-enable gem_noc. dwc3's apps-usb
 * icc path runs gem->config_noc, so the 0007 disable stalls USB
 * forever (no rootfs). If the 0.51s reset returns, gem was the
 * crasher and USB needs another route. Local-only, not for
 * publication. */
&gem_noc { status = "okay"; };
'''
text = open(BOARD, errors='replace').read()
assert 'delete-property/ interconnects' in text, '0009 block missing?'
assert '(0010)' not in text, '0010 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0010')
