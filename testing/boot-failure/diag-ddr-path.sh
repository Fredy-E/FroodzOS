#!/bin/bash
set -u
DT=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
DTS=/tmp/slim3-full.dts
dtc -I dtb -O dts "$DT" -o "$DTS" 2>/dev/null
echo "=== a600000 interconnects raw ==="
grep -A4 'usb@a600000 {' "$DTS" | head -8
echo "=== endpoint nodes: usb_south_anoc / mc_virt ==="
grep -n -i "usb_south_anoc\|mc_virt" "$DTS" | head -20
echo "=== status of those nodes ==="
grep -n -B2 -A8 "usb-anoc\|mc-virt\|mc_virt" "$DTS" | grep -iE "status|compatible|{|interconnect-cells|#" | head -30
echo "=== which drivers provide them (compatible) ==="
grep -n -B6 'interconnect-cells' "$DTS" | grep -E "compatible|{|: " | head -20
echo "=== provider drivers in config ==="
grep -E "CONFIG_INTERCONNECT_QCOM_X1E80100|CONFIG_INTERCONNECT_QCOM_SM8650|CONFIG_INTERCONNECT_QCOM" /home/builder/src/ksrc/.config | head -20
echo "=== a600000 full node ==="
awk '/usb@a600000 \{/,/^\t\};/' "$DTS" | head -40
