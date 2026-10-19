#!/usr/bin/env python3
"""Initcall symbols for round 2: USB/DP PHYs, SMMU, PDC."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
seen = {}
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and parts[2].endswith('init'):
        low = parts[2].lower()
        if re.search(r'smmu|pdc|eusb|snps|combo_phy|usbc|dp_phy|edp|dsi_phy', low):
            seen.setdefault(parts[2], parts[0])
for n in sorted(seen):
    print(n, seen[n])
print('=== registration lines ===')
for label, f in {
    'eusb2': 'drivers/phy/qualcomm/phy-qcom-snps-eusb2.c',
    'qmp-combo': 'drivers/phy/qualcomm/phy-qcom-qmp-combo.c',
    'smmu': 'drivers/iommu/arm/arm-smmu/arm-smmu.c',
    'pdc': 'drivers/irqchip/qcom-pdc.c',
}.items():
    r = subprocess.run(['grep', '-nE', 'driver_init|module_init|builtin_platform_driver|IRQCHIP_DECLARE',
                        f'{KSRC}/{f}'], capture_output=True, text=True)
    print(f'{label}:', (r.stdout.strip().splitlines() or ['?'])[:5])
