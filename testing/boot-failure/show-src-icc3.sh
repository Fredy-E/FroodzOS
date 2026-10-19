#!/bin/bash
KSRC=/home/builder/src/ksrc
awk 'NR>=5083 && NR<=5420 && (/interconnects ?=|interconnect-names|usb@[a-f0-9]+ \{/)' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi"
