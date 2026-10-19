#!/bin/bash
# Every icc acquisition in dwc3-qcom + dwc3 core (who re-gets post-bind?).
KSRC=/home/builder/src/ksrc
grep -n 'icc_get\|icc_set_bw\|icc_enable\|icc_disable' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c" | head -20
echo '=== core ==='
grep -n 'icc_get\|icc_set_bw' "$KSRC/drivers/usb/dwc3/core.c" | head -10
