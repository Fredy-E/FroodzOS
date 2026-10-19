#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== qnm_gemnoc_sf owner ==="
grep -n "qnm_gemnoc_sf" "$F" | head
echo "=== qns_gemnoc_sf def ==="
grep -n -A8 "^static struct qcom_icc_node qns_gemnoc_sf" "$F" | head -12
echo "=== node at 900-908 ==="
sed -n '895,908p' "$F"
