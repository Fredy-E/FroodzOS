#!/usr/bin/env python3
"""Append diagnostic DT overrides for the minimal-boot round (0008).

Disables: 4x PCIe + 4x PCIe PHYs, 7x WLAN/WWAN/display/NVMe rails,
4x thermal sensors, 2x display PHYs, UFS PHY. Keeps: USB, core
clocks/regulators/pinctrl/SCM, all interconnects except the six
already disabled. If boot walks past 9.45s, re-enable round follows.
"""
BOARD = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
NODES = ['pcie3', 'pcie6a', 'pcie5', 'pcie4',
         'pcie3_phy', 'pcie6a_phy', 'pcie5_phy', 'pcie4_phy',
         'vreg_edp_3p3', 'vreg_misc_3p3', 'vreg_pcie3_nvme',
         'vreg_wcn_0p95', 'vreg_wcn_1p9', 'vreg_wcn_3p3', 'vreg_wwan',
         'tsens0', 'tsens1', 'tsens2', 'tsens3',
         'mdss_dp2_phy', 'mdss_dp3_phy', 'ufs_mem_phy']
BLOCK = '''
/* DIAGNOSTIC 2026-10-15 (0008): minimal-boot round. Disable PCIe,
 * WLAN/WWAN/display/NVMe rails, thermal sensors, display and UFS
 * PHYs. Boot hung-on-reset right after the 9.45s regulator retry
 * burst; cut every non-essential pending family at once. USB and
 * core (clocks/pinctrl/SCM/PMIC) stay enabled. Local-only, not for
 * publication. */
'''
for n in NODES:
    BLOCK += f'&{n} {{ status = "disabled"; }};\n'
text = open(BOARD, errors='replace').read()
assert '&lpass_lpicx_noc' in text, '0007 block missing?'
assert 'minimal-boot round. Disable PCIe' not in text, '0008 block already present'
open(BOARD, 'a').write(BLOCK)
print('APPENDED_0008', len(NODES), 'nodes')
