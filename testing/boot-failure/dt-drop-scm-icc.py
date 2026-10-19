#!/usr/bin/env python3
"""Append 0009: drop SCM's interconnects property (unblocks PDC->TLMM->GPIO->USB)."""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BLOCK = '''
/* DIAGNOSTIC 2026-10-15 (0009): delete firmware:scm interconnects.
 * SCM's icc path (aggre2 + mc_virt) never resolves on this machine,
 * so SCM defers forever; the X1E PDC quirk hard-requires SCM, and
 * TLMM (wakeup-parent PDC), GPIO, USB PHYs and USB storage hang
 * behind it. devm_of_icc_get treats a missing property as no-vote
 * (NULL path), so SCM probes without bus voting. Local-only, not
 * for publication. */
&scm {
	/delete-property/ interconnects;
};
'''
text = open(BOARD, errors='replace').read()
assert '&ufs_mem_phy' in text, '0008 block missing?'
assert 'delete-property/ interconnects' not in text, '0009 already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0009')
