#!/usr/bin/env python3
"""Stage the Slim 3 DTB for the fixed Ubuntu control entry (GRUB devicetree)."""
import hashlib
import os
import shutil

SRC = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
DST = '/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/boot/slim3-x126100.dtb'
data = open(SRC, 'rb').read()
print('DTB_BYTES', len(data), 'SHA256', hashlib.sha256(data).hexdigest())
os.makedirs(os.path.dirname(DST), exist_ok=True)
shutil.copyfile(SRC, DST)
print('STAGED_CONTROL_DTB')
