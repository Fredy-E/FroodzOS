#!/usr/bin/env python3
"""Stage the DT-disable test UKI into the file-only delta source dir."""
import hashlib
import os
import shutil

SRC = '/home/builder/uki-v2-dt1/vmlinuz-live.efi'
DST = '/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/EFI/Linux/kestrel-live.efi'
SIZE = 244385792
SHA = 'ed8b5c93642f3931af62c13916e7cebb0991b0a577b9470ab59be90646d9f696'
data = open(SRC, 'rb').read()
assert len(data) == SIZE, len(data)
assert hashlib.sha256(data).hexdigest() == SHA
shutil.copyfile(SRC, DST)
print('STAGED_DT1', len(data))
