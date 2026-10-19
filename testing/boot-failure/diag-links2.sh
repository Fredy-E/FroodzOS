#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== qns_aggre_usb_south_snoc definition ==="
grep -n -A10 "^static struct qcom_icc_node qns_aggre_usb_south_snoc" "$F" | head -14
echo "=== which desc arrays contain ebi (context) ==="
for ln in 612 1625 1694; do
  echo "--- around $ln ---"
  sed -n "$((ln-14)),$((ln+2))p" "$F" | grep -E "static const|_desc|nodes|ebi" | head -6
done
echo "=== ebi node definition ==="
sed -n '1529,1545p' "$F"
