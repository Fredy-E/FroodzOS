#!/usr/bin/env python3
"""Find consumer driver init symbols, fixed matching (v2)."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
names = set()
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and parts[2].endswith('driver_init'):
        low = parts[2].lower()
        if re.search(r'mdss|msm_|adreno|qcom_pas|q6v5|dwc3|xhci|pcie|qmp|remoteproc|pil', low):
            names.add((parts[2], parts[0]))
for n, a in sorted(names):
    print(n, a)
print('=== registration lines ===')
jobs = {
    'msm_drv.c': 'drivers/gpu/drm/msm/msm_drv.c',
    'qcom_q6v5.c': 'drivers/remoteproc/qcom_q6v5.c',
    'xhci-plat.c': 'drivers/usb/host/xhci-plat.c',
    'pcie-qcom.c': 'drivers/pci/controller/dwc/pcie-qcom.c',
    'phy-qcom-qmp.c': 'drivers/phy/qualcomm/phy-qcom-qmp.c',
}
for label, f in jobs.items():
    r = subprocess.run(['grep', '-nE', 'module_platform_driver|builtin_platform_driver|module_init|late_initcall|arch_initcall',
                        f'{KSRC}/{f}'], capture_output=True, text=True)
    print(f'{label}:', (r.stdout.strip().splitlines() or ['?'])[:4])
