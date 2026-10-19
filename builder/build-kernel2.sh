#!/bin/bash
# Task 2.2 rebuild (targeted): Image + modules + ONLY the Slim 3 DTB (2026-10-08)
set -euo pipefail
cd /home/builder/src/ksrc
echo "== VPH_PWR definitions (sanity) =="
grep -n "VPH_PWR" arch/arm64/boot/dts/qcom/qcom-adc5-gen3.h || echo "not in local header (object-like 0x8e comes from spmi-vadc.h)"
echo "=== BUILD START $(date --iso-8601=seconds) ==="
make ARCH=arm64 -j4 Image modules > /home/builder/src/kernel-build2.log 2>&1
echo "=== IMAGE+MODULES OK ==="
make ARCH=arm64 qcom/x126100-lenovo-ideapad-slim3.dtb >> /home/builder/src/kernel-build2.log 2>&1
echo "=== DTB OK ==="
ls -la arch/arm64/boot/Image
ls -la arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
echo KERNEL_BUILD2_DONE
