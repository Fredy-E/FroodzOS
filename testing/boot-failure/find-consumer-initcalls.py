#!/usr/bin/env python3
"""Find driver initcall symbols for consumer-blacklist rounds."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
want = ['mdss', 'adreno', 'q6v5', 'dwc3', 'xhci.*plat', 'pcie.*qcom\|qcom.*pcie',
        'phy.*qmp\|qmp.*phy', 'ehci', 'uas', 'usb_storage']
seen = {}
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) != 3:
        continue
    addr, typ, name = parts
    if not name.endswith('driver_init'):
        continue
    low = name.lower()
    for w in want:
        if re.search(w, low):
            seen.setdefault(w, []).append((addr, typ, name))
for w in want:
    print('##', w)
    for addr, typ, name in seen.get(w, [])[:12]:
        print('   ', addr, typ, name)
# also show the registration macro per driver file for the top suspects
for f in ['drivers/gpu/drm/msm/msm_drv.c', 'drivers/gpu/drm/adreno/adreno_device.c',
          'drivers/remoteproc/qcom_q6v5.c', 'drivers/remoteproc/qcom_q6v5_pas.c',
          'drivers/usb/host/xhci-plat.c', 'drivers/usb/dwc3/dwc3-qcom.c',
          'drivers/pci/controller/dwc/pcie-qcom.c']:
    r = subprocess.run(['grep', '-n', 'module_platform_driver\|builtin_platform_driver\|module_pci_driver',
                        f'{KSRC}/{f}'], capture_output=True, text=True)
    print(f, '->', (r.stdout.strip().splitlines() or ['?'])[:3])
