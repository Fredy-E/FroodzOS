#!/bin/bash
set -u
DTS=/tmp/slim3c.dts
echo "=== phy@fd3000 (ss0 HS) ==="
grep -n -A10 "phy@fd3000 {" "$DTS" | grep -E "compatible|status|reg " | head -5
echo "=== phy@fd5000 (ss0 SS/QMP) ==="
grep -n -A10 "phy@fd5000 {" "$DTS" | grep -E "compatible|status|reg " | head -5
echo "=== phy drivers in config ==="
grep -E "CONFIG_PHY_QCOM.*(EUSB2|QMP|SNPS|COMBO)|CONFIG_PHY_QCOM_USB_HS" /home/builder/src/ksrc/.config | head
echo "=== what is f4f000? ==="
grep -n -B1 -A3 "f4f000" "$DTS" | grep -E "phy@|compatible|status" | head -6
