#!/bin/bash
# dr_mode on the four dwc3 nodes (OTG switching would yank the host).
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n -A20 'usb_2: usb@a200000' "$DTS" | grep -E 'dr_mode|usb-role-switch|role-switch' | head -4
echo '=== child dwc3 nodes ==='
grep -n -B1 -A6 'compatible = "snps,dwc3"' "$DTS" | grep -E 'dr_mode|usb@|dwc3@' | head -12
