#!/bin/bash
set -u
echo "=== dispcc in config ==="
grep -i "DISPCC\|DISP_CC\|MMSS\|QCOM.*CLK" /home/builder/src/ksrc/.config 2>&1 | head -20
echo "=== clk qcom dispcc source ==="
ls /home/builder/src/ksrc/drivers/clk/qcom/ 2>/dev/null | grep -i "disp\|x1e" | head -20
echo "=== dispcc compatible in live dtb ==="
dtc -I dtb -O dts /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>/dev/null | grep -i -B2 -A4 "dispcc\|display.*clock\|clock-controller@af" | head -40
echo "=== what provides clock-controller af? ==="
dtc -I dtb -O dts /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>/dev/null | grep -A3 "clock-controller@" | head -40
echo "=== pstore modules in dt14 initramfs ==="
lsinitcpio -l /home/builder/uki-v2-dt14/live-initramfs.img 2>/dev/null | grep -i "pstore\|efi_vars\|efivars" || echo "no pstore/efi var modules in initramfs"
echo "=== pstore in dt14 kernel modules dir? ==="
find /home/builder/uki-v2-dt14 -name "*pstore*" 2>/dev/null | head; echo "(modules ship in squashfs, checked separately)"
echo "=== a600000 interconnects ==="
dtc -I dtb -O dts /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb 2>/dev/null | grep -A25 "usb@a600000 {" | grep -i "interconnect\|apps-usb\|usb-ddr\|status" | head -10
