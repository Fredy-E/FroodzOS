#!/bin/bash
# Context around all icc_path_apps uses for the patch.
KSRC=/home/builder/src/ksrc
sed -n '125,230p' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c"
