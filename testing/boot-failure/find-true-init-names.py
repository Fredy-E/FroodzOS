#!/usr/bin/env python3
"""Find true initcall names for msm display and qcom PAS remoteproc."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
print('=== map hits: msm/pas/remoteproc/adreno ===')
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and re.search(r'msm_drm|adreno|qcom_pas|remoteproc.*init|pil.*init', parts[2]):
        print('   ', parts[1], parts[2], parts[0])
print('=== registration macros ===')
for f in ['drivers/gpu/drm/msm/msm_drv.c',
          'drivers/remoteproc/qcom_q6v5_pas.c',
          'drivers/gpu/drm/adreno/adreno_device.c']:
    r = subprocess.run(['grep', '-nE', 'module_init|module_platform_driver|builtin_platform_driver|subsys_initcall|arch_initcall|late_initcall',
                        f'{KSRC}/{f}'], capture_output=True, text=True)
    print(f, '->', (r.stdout.strip().splitlines() or ['?'])[:4])
