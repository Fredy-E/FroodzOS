#!/usr/bin/env python3
"""Definitive 0008 check: decompile DTB, report status of every 0008 node."""
import re
import subprocess
DTB = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', DTB],
                     capture_output=True, text=True).stdout
want = {'pcie@1bd0000': 'pcie3', 'pcie@1bf8000': 'pcie6a',
        'pcie@1c00000': 'pcie5', 'pcie@1c08000': 'pcie4',
        'phy@1bd4000': 'pcie3_phy', 'phy@1bfc000': 'pcie6a_phy',
        'phy@1c06000': 'pcie5_phy', 'phy@1c0e000': 'pcie4_phy',
        'regulator-edp-3p3': 'vreg_edp_3p3',
        'regulator-misc-3p3': 'vreg_misc_3p3',
        'regulator-pcie3-nvme': 'vreg_pcie3_nvme',
        'regulator-wcn-0p95': 'vreg_wcn_0p95',
        'regulator-wcn-1p9': 'vreg_wcn_1p9',
        'regulator-wcn-3p3': 'vreg_wcn_3p3', 'regulator-wwan': 'vreg_wwan',
        'thermal-sensor@c271000': 'tsens0',
        'thermal-sensor@c272000': 'tsens1',
        'thermal-sensor@c273000': 'tsens2',
        'thermal-sensor@c274000': 'tsens3',
        'phy@aec2a00': 'mdss_dp2_phy', 'phy@aec5a00': 'mdss_dp3_phy',
        'phy@1d80000': 'ufs_mem_phy'}
bad = []
for node, label in want.items():
    m = re.search(r'\n(\s*)' + re.escape(node) + r'\s*\{(.*?)\n\1\};', dts, re.S)
    if not m:
        print('NOTFOUND', label, node)
        bad.append(label)
        continue
    st = re.search(r'status\s*=\s*"([^"]+)"', m.group(2))
    print(('OK  ' if st and st.group(1) == 'disabled' else 'FAIL'), label, '->',
          st.group(1) if st else 'no-status')
    if not st or st.group(1) != 'disabled':
        bad.append(label)
print('BAD:', bad if bad else 'none')
