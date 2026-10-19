#!/bin/bash
# Label of the usb node at ~5036 + its pair0 master macro.
KSRC=/home/builder/src/ksrc
sed -n '5025,5045p' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" | grep -E 'usb@[a-f0-9]+ \{|MASTER_'
