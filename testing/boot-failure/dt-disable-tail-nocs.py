#!/usr/bin/env python3
"""Append diagnostic DT overrides disabling the 5 tail NoCs (0007).

Rationale: native resets land right after 1770000/1780000 probes in every
config; the only qnoc nodes left untested are gem/nsp/lpass. One edit
disables all five; if boot moves, bisect by re-enabling.
"""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BLOCK = '''
/* DIAGNOSTIC 2026-10-11 (0007): disable the five tail NoCs (gem, nsp,
 * lpass ag/lpiaon/lpicx) to test whether a late qnoc probe is the
 * silent-reset site observed after the 1770000/1780000 probes.
 * Local-only experiment, not for publication. */
&gem_noc { status = "disabled"; };
&nsp_noc { status = "disabled"; };
&lpass_ag_noc { status = "disabled"; };
&lpass_lpiaon_noc { status = "disabled"; };
&lpass_lpicx_noc { status = "disabled"; };
'''
text = open(BOARD, errors='replace').read()
assert '&gem_noc' not in text, '0007 block already present'
assert '&pcie_south_anoc' in text, '0006 block missing?'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0007')
