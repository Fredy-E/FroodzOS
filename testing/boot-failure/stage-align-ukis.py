#!/usr/bin/env python3
"""Stage the alignment-fix UKIs into the file-only delta source dir."""
import hashlib
import os
import shutil

DST = '/mnt/d/CachyOS-ARM64/testing/boot-failure/log-option/EFI/Linux'
pairs = [
    ('/home/builder/uki-v2-align1/vmlinuz-live.efi', 'kestrel-live.efi',
     244385792, 'b9730ea275848fcea2cd3e73e2806dc3682c9256a88b8820b9b9a94ee31b8550'),
    ('/home/builder/uki-v2-log7/vmlinuz-live.efi', 'kestrel-live-log.efi',
     244916224, 'b92eeb3d49ca7a0fbc3f95c4ba774155a5ee2e69e861834ecbcaca69932566d2'),
]
os.makedirs(DST, exist_ok=True)
for src, name, size, sha in pairs:
    data = open(src, 'rb').read()
    assert len(data) == size, (name, len(data))
    digest = hashlib.sha256(data).hexdigest()
    assert digest == sha, (name, digest)
    shutil.copyfile(src, os.path.join(DST, name))
    print('STAGED', name, len(data), digest)
