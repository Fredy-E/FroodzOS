#!/usr/bin/env python3
"""Append 0012: disable gpu + gmu (GPU-SMMU interaction kills display ~9.26s)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0012): disable gpu + gmu. GPU binding to
 * its IOMMU group at ~9.26s is immediately followed by display
 * death (without SMMU the same boot lived to 19.4s+). Keep the
 * console on the firmware framebuffer until GPU/SMMU is properly
 * brought up. Local-only, not for publication. */
&gpu { status = "disabled"; };
&gmu { status = "disabled"; };
'''
text = open(BOARD, errors='replace').read()
assert '(0011)' in text, '0011 block missing?'
assert '(0012)' not in text, '0012 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0012')
