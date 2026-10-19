#!/usr/bin/env python3
"""Inspect builder prerequisites without shell-layer ambiguity."""
import json,subprocess
from pathlib import Path
out={}
for root in ['/usr/share','/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share']:
 out[root]=[str(p) for p in Path(root).rglob('*.fd') if 'efi' in str(p).lower() or 'edk' in str(p).lower()]
out['qemu']=subprocess.run(['qemu-system-aarch64','--version'],capture_output=True,text=True,check=True).stdout
out['config']=[l for l in Path('/home/builder/src/ksrc/.config').read_text().splitlines() if any(x in l for x in ['CONFIG_EFIVAR','CONFIG_EFI_VARS','CONFIG_QCOM_DISPCC','CONFIG_ARM_SMMU','CONFIG_USB_DWC3_QCOM'])]
print(json.dumps(out,indent=2))
