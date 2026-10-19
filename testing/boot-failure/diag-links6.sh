#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== owner of llcc_mc ==="
grep -n "llcc_mc" "$F" | head
echo "=== qns_aggre_usb_snoc full ==="
sed -n '1597,1606p' "$F"
