#!/usr/bin/env python3
"""Verify every initcall_blacklist name used on the USB menu exists in System.map."""
import re
USED = ['qnoc_driver_init', 'msm_drm_register', 'dwc3_qcom_driver_init',
        'qcom_pcie_driver_init', 'xhci_plat_init', 'qcom_pas_driver_init',
        'snps_eusb2_hsphy_driver_init', 'qcom_snps_hsphy_driver_init',
        'qmp_usbc_driver_init', 'qmp_usb_driver_init', 'qmp_combo_driver_init',
        'arm_smmu_init', 'qcom_smmu_module_init', 'qcom_pdc_driver_init']
table = {}
for line in open('/home/builder/src/ksrc/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3:
        table.setdefault(parts[2], parts[0])
print('=== blacklist name check ===')
for name in USED:
    hit = [k for k in table if k == name or k.endswith('__' + name) or name in k]
    print(('VALID ' if hit else 'VOID  ') + name +
          ('' if hit else '  <-- NEVER MATCHED, test was VOID'))
print('=== qnoc/pas initcall entries ===')
for k in sorted(table):
    if 'initcall' in k and re.search(r'qnoc|pas_driver|q6v5', k):
        print('   ', k)
