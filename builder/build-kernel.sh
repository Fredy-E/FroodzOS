#!/bin/bash
# Task 2.2: build the hardware-enablement kernel from pinned jglathe tree (2026-10-08)
# Tree: linux_ms_dev_kit @ 3f0d8691afa098ba378d7d5a3968f03219887719
set -euo pipefail
cd /home/builder/src/ksrc

echo "=== config lines ==="
wc -l arch/arm64/configs/* || true

if grep -q '^CONFIG_ARCH_QCOM=y' arch/arm64/configs/ubuntu_x1e_defconfig 2>/dev/null || \
   grep -q '^CONFIG_ARM64=y' arch/arm64/configs/ubuntu_x1e_defconfig 2>/dev/null; then
    echo "=== ubuntu_x1e_defconfig is a full config; using it as target ==="
    make ARCH=arm64 ubuntu_x1e_defconfig
else
    echo "=== ubuntu_x1e_defconfig looks like a fragment; merging ==="
    make ARCH=arm64 defconfig
    ./scripts/kconfig/merge_config.sh -m .config arch/arm64/configs/ubuntu_x1e_defconfig arch/arm64/configs/qcom_laptops.config
    make ARCH=arm64 olddefconfig
fi

echo "=== key config values ==="
grep -E '^CONFIG_(ARCH_QCOM|ARCH_QCOM_SOC|ARM64|ACPI|EFI_STUB|DRM_MSM|DRM_ADRENO|ATH12K|QCOM_Q6V5|SOUNDWIRE|I2C_HID_ACPI|PCIE_QCOM)=' .config | sort | head -25

echo "=== BUILD START $(date --iso-8601=seconds) ==="
make ARCH=arm64 -j4 Image modules dtbs > /home/builder/src/kernel-build.log 2>&1
echo "=== BUILD END $(date --iso-8601=seconds) ==="
tail -5 /home/builder/src/kernel-build.log
ls -la arch/arm64/boot/Image
ls -la arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
echo KERNEL_BUILD_DONE
