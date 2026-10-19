#!/bin/bash
# Bare -517 sources in the actual eusb2 PHY drivers.
KSRC=/home/builder/src/ksrc
for f in drivers/phy/qualcomm/phy-qcom-snps-femto-v2.c drivers/phy/qualcomm/phy-qcom-eusb2-repeater.c drivers/phy/qualcomm/phy-qcom-m31-eusb2.c; do
  echo "=== $f"; grep -n -B8 'return -EPROBE_DEFER' "$KSRC/$f" | head -25
done
