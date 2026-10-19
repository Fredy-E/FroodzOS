#!/bin/bash
set -u
DT=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
DTS=/tmp/slim3c.dts
dtc -I dtb -O dts "$DT" -o "$DTS" 2>/dev/null
echo "=== node with phandle 0xee ==="
grep -n "phandle = <0xee>" "$DTS"
echo "=== phys near a600000 ==="
grep -n "phys = " "$DTS" | head -20
echo "=== usb2 phy nodes ==="
grep -n -i "qusb2\|eusb2\|usb2.*phy\|phy.*usb2" "$DTS" | grep -iv "phy@" | head -10
grep -n "phy@fde000\|phy@fda000\|phy@fd5000" "$DTS" | head
echo "=== status of providers around phys ==="
for n in $(grep -n "phandle = <0xee>" "$DTS" | cut -d: -f1); do
  awk -v L="$n" 'NR<=L && /^[ \t]*[a-zA-Z0-9_,.-]+(@[0-9a-fxA-F]+)?:.*\{/ {line=NR": "$0} NR==L {print line; exit}' "$DTS"
done
