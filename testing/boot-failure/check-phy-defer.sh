#!/bin/bash
# Bare -517 sources in the eusb2 PHY drivers (no dev_err_probe = silent defer).
KSRC=/home/builder/src/ksrc
for f in drivers/phy/qualcomm/phy-qcom-snps-eusb2.c drivers/phy/qualcomm/phy-qcom-eusb2-repeater.c; do
  echo "=== $f"; grep -n -B6 'return -EPROBE_DEFER' "$KSRC/$f" | head -30
done
