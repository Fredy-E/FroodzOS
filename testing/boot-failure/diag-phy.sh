#!/bin/bash
set -u
DTS=/tmp/slim3b.dts
echo "=== node with phandle 0xee ==="
grep -n "phandle = <0xee>" "$DTS"
echo "=== a600000 phys property ==="
grep -n -A3 'phys = ' "$DTS" | grep -B1 -A3 "a600000" | head; grep -n "phys = " "$DTS" | awk -F: '$1>8600 && $1<8750'
echo "=== qusb2/usb2 phy nodes status ==="
grep -n "qusb2\|usb2-phy\|eusb" "$DTS" | head -10
