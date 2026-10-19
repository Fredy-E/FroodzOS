#!/bin/bash
# Where do icc_path_ddr / icc_path_apps get acquired (probe)?
KSRC=/home/builder/src/ksrc
grep -n -B4 -A4 'icc_path_ddr\s*=\|icc_path_apps\s*=' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c" | head -30
