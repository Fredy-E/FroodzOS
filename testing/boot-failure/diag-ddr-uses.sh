#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/usb/dwc3/dwc3-qcom.c
grep -n "icc_path_ddr" "$F"
