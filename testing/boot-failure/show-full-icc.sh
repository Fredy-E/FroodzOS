#!/bin/bash
# Full source interconnects lines (need the mc_virt half too).
KSRC=/home/builder/src/ksrc
grep -n -A3 'interconnects = <&usb_' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" | head -20
