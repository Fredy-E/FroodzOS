#!/usr/bin/env python3
"""Verify the 0016 warn string is inside the dt12 kernel Image."""
data = open('/home/builder/src/ksrc/arch/arm64/boot/Image', 'rb').read()
hits = data.count(b'continuing without it')
print('SIZE', len(data), 'WARN_HITS', hits, 'PATCH_IN_IMAGE' if hits >= 1 else 'PATCH_MISSING')
