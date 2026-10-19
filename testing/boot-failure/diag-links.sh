#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== ebi nodes ==="
grep -n "ebi" "$F" | head -20
echo "=== usb south slave links ==="
grep -n -A6 "qns_aggre_usb_south_snoc" "$F" | head -30
