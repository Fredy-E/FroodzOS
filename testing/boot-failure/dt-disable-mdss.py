#!/usr/bin/env python3
"""Append 0013: disable mdss display-subsystem (keeps simplefb console)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BLOCK = '''
/* DIAGNOSTIC 2026-10-16 (0013): disable the display subsystem. The
 * mdss driver (from initramfs modules) binds the subsystem and takes
 * over the firmware framebuffer, but the panel never lights, so the
 * screen goes black-with-backlight and all later text is invisible.
 * Keep the console on simplefb until panel bring-up is solved.
 * Local-only, not for publication. */
&mdss { status = "disabled"; };
'''
text = open(BOARD, errors='replace').read()
assert '(0012)' in text, '0012 block missing?'
assert '(0013)' not in text, '0013 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0013')
