#!/usr/bin/env bash
# Compile the USB log streamer statically, then build the log-capture UKI.
set -euo pipefail
mkdir -p /home/builder/diag
gcc -static -Os -s /mnt/d/CachyOS-ARM64/builder/diagnostics/kestrel-kmsg.c -o /home/builder/diag/kestrel-kmsg
file /home/builder/diag/kestrel-kmsg
ls -la /home/builder/diag/kestrel-kmsg
python3 /mnt/d/CachyOS-ARM64/testing/boot-failure/build-log-uki.py
