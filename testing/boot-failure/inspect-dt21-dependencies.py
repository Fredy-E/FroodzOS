#!/usr/bin/env python3
"""Read-only current DT/provider audit; no source or firmware modifications."""
import json
import re
import subprocess
from pathlib import Path

K = Path('/home/builder/src/ksrc')
D = K / 'arch/arm64/boot/dts/qcom'
for relative, lo, hi in [
    ('drivers/i2c/busses/i2c-qcom-geni.c', 350, 420),
    ('drivers/soc/qcom/qcom-geni-se.c', 995, 1055),
    ('drivers/interconnect/core.c', 400, 450),
]:
    lines = (K / relative).read_text().splitlines()
    print('\nSOURCE', relative)
    print('\n'.join(f'{i+1}:{lines[i]}' for i in range(lo-1, min(hi, len(lines)))))
text = (D / 'hamoa.dtsi').read_text().splitlines()
for token in ('i2c5:', 'gpi_dma0:', 'gpi_dma1:', 'gpi_dma2:'):
    for i, line in enumerate(text):
        if token in line:
            print('\nHAMOA', token)
            print('\n'.join(f'{j+1}:{text[j]}' for j in range(max(0,i-8), min(len(text),i+45))))
dtb = D / 'x126100-lenovo-ideapad-slim3.dtb'
flat = subprocess.check_output(['dtc','-I','dtb','-O','dts',str(dtb)], stderr=subprocess.DEVNULL, text=True)
lines = flat.splitlines()
for token in ('i2c@b94000 {', 'dma-controller@', 'qup@b00000 {'):
    for i, line in enumerate(lines):
        if token in line:
            print('\nCOMPILED', line.strip())
            print('\n'.join(lines[i:min(len(lines),i+32)]))
listed = subprocess.check_output(['lsinitcpio','-l','/home/builder/uki-v2-dt20/live-initramfs.img'], text=True)
print('\nDMA ARCHIVE', [line for line in listed.splitlines() if 'gpi' in line.lower() and '.ko' in line])
print('\nMODULE METADATA')
for name in ('gpi','gpi-dma','i2c-qcom-geni'):
    r = subprocess.run(['modinfo','-k','7.3.0-rc3',name], text=True, capture_output=True)
    print(name,r.returncode, '\n'.join(line for line in r.stdout.splitlines() if line.startswith(('filename:','depends:','alias:'))))
