#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
sed -n '595,615p' "$F"
echo "=== qns_aggre_usb_snoc links ==="
grep -n -A8 "^static struct qcom_icc_node qns_aggre_usb_snoc" "$F" | head -12
echo "=== owner of that qns node (which desc nodes[] has it) ==="
grep -n "qns_aggre_usb_snoc," "$F" | head
