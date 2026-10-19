#!/bin/bash
# All EPROBE_DEFER paths in dwc3-qcom (what can keep it deferring?).
KSRC=/home/builder/src/ksrc
grep -n -B4 'EPROBE_DEFER' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c" | head -60
