#!/bin/bash
set -u
echo "=== config module vs builtin ==="
grep -E "^(CONFIG_QCOM_DISPCC|CONFIG_ARM_SMMU|CONFIG_QCOM_IOMMU|CONFIG_USB_DWC3_QCOM|CONFIG_EFIVAR_FS|CONFIG_EFI_VARS_PSTORE)" /home/builder/src/ksrc/.config 2>&1 || echo "config not found"
echo "=== blacklist symbol check ==="
for s in arm_smmu_init qcom_smmu_module_init dispcc_x1e80100; do
  if grep -qw "$s" /home/builder/src/ksrc/System.map 2>/dev/null; then echo "$s: IN System.map (builtin initcall, blacklist valid)"; else echo "$s: NOT in System.map"; fi
done
echo "=== dispcc module file? ==="
find /home/builder/src/ksrc -name "dispcc-x1e80100*" 2>/dev/null | head -5
echo "=== 0016 patch present? ==="
grep -c "continuing without it" /home/builder/src/ksrc/drivers/usb/dwc3/dwc3-qcom.c 2>&1
echo "=== kernel image ==="
stat -c %s /home/builder/src/ksrc/arch/arm64/boot/Image 2>&1
sha256sum /home/builder/src/ksrc/arch/arm64/boot/Image 2>&1 | cut -c1-64
echo "=== dtb ==="
stat -c %s /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>&1
sha256sum /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>&1 | cut -c1-64
echo "=== dwc3 a600000 in live dtb ==="
dtc -I dtb -O dts /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>/dev/null | grep -A6 "a600000" | head -30 || echo "dtc unavailable"
echo "=== live-staging tree ==="
ls -la /mnt/d/CachyOS-ARM64/live-staging-v2/ /mnt/d/CachyOS-ARM64/live-staging-v2/boot/grub/ 2>&1 | head -20
