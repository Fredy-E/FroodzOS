#!/bin/bash
# All icc use sites in dwc3-qcom.c (quoting-safe).
KSRC=/home/builder/src/ksrc
grep -n 'icc_path_apps' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c"
echo '=== total icc mentions ==='
grep -c 'icc_' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c"
