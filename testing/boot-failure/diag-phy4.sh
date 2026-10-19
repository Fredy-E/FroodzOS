#!/bin/bash
set -u
DT=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
DTS=/home/builder/slim3-keep.dts
[ -f "$DTS" ] || dtc -I dtb -O dts "$DT" -o "$DTS" 2>/dev/null
echo "=== eusb2/snps phy driver in config ==="
grep -E "SNPS_EUSB2|EUSB2" /home/builder/src/ksrc/.config
echo "=== phy@fd5000 full ==="
awk '/phy@fd5000 \{/,/^\t\t\};/' "$DTS" | head -25
echo "=== phy@fd3000 status ==="
awk '/phy@fd3000 \{/,/^\t\t\};/' "$DTS" | grep -E "status|clocks|vdda|vddq" | head -6
echo "=== f4f000 node ==="
grep -n -A6 "f4f000" "$DTS" | grep -E "phy|compatible|status" | head -8
