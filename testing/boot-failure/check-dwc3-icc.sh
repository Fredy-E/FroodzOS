#!/bin/bash
# How many icc paths does dwc3-qcom acquire, by name or index?
KSRC=/home/builder/src/ksrc
grep -n -B2 -A6 'icc_get\|icc_path\|icc_bulk\|icc_enable\|icc_set' "$KSRC/drivers/usb/dwc3/dwc3-qcom.c" | head -40
