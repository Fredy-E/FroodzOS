#!/bin/bash
# Label header just above line 5036.
KSRC=/home/builder/src/ksrc
awk 'NR<5036 && /usb@[a-f0-9]+ \{/ {last=$0} END{}' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi"
grep -n 'usb@[a-f0-9]* *{' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" | head -8
