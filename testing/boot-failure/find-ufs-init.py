#!/usr/bin/env python3
"""UFS + related storage/consumer init names and their CONFIG state."""
import re
import subprocess
KSRC = '/home/builder/src/ksrc'
print('=== map: ufs/venus/cam/wlan/iris/npu ===')
for line in open(KSRC + '/System.map', errors='replace'):
    parts = line.split()
    if len(parts) == 3 and parts[2].endswith('init') and re.search(
            r'ufs|venus|iris|camss|wlan|ath|npu|hlos|compute', parts[2]):
        print('   ', parts[1], parts[2])
print('=== CONFIG ===')
for line in open(KSRC + '/.config', errors='replace'):
    s = line.strip()
    if re.search(r'UFS|QCOM_PAS|Q6V5|REMOTE_PROC|DRM_MSM|ATH11K|ATH12K|VENUS|CAMSS|QRTR|IPA', s) and ('=' in s):
        print('   ', s)
