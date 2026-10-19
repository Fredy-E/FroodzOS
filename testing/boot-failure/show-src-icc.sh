#!/bin/bash
# Current-source interconnects for all four dwc3 nodes (labels, not numbers).
KSRC=/home/builder/src/ksrc
grep -n -A3 'usb_2: usb@a200000\|usb_mp: usb@a400000\|usb_1_ss0: usb@a600000\|usb_1_ss1: usb@a800000' "$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts" "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" 2>/dev/null | grep -E 'usb@|interconnects|interconnect-names' | head -16
