#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== node linking to llcc_mc (around 1494) ==="
sed -n '1480,1496p' "$F"
echo "=== qnm_usb_anoc definition ==="
grep -n -A8 "^static struct qcom_icc_node qnm_usb_anoc" "$F" | head -12
echo "=== owner array of qnm_usb_anoc ==="
grep -n "qnm_usb_anoc," "$F" | head
echo "=== owner array of qns_aggre_usb_snoc ==="
grep -n "qns_aggre_usb_snoc," "$F" | head
