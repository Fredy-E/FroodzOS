#!/bin/bash
# Incremental kernel build (dt17: 0017 usb-ddr optional) + Image check.
set -e
cd /home/builder/src/ksrc
make ARCH=arm64 -j4 Image 2>&1 | tail -5
echo "=== Image ==="
stat -c %s arch/arm64/boot/Image
if ! grep -c "usb-ddr path unavailable" arch/arm64/boot/Image >/dev/null; then
  echo "WARN_STRING_MISSING"; exit 1
fi
grep -c "usb-ddr path unavailable" arch/arm64/boot/Image
grep -c "continuing without it" arch/arm64/boot/Image
