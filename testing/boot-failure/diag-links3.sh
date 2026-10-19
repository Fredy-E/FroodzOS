#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
echo "=== gem_noc desc: nodes range ==="
grep -n "gem_noc_nodes\|x1e80100_gem_noc\b" "$F" | head
echo "=== gem nodes with mem/ebi links ==="
grep -n -A4 "qns_gemnoc\|qnm_gemnoc\|gemnoc.*ebi\|ebi.*gem" "$F" | head -30
echo "=== qnm_aggre_usb_south_snoc owner+links ==="
grep -n -A8 "^static struct qcom_icc_node qnm_aggre_usb_south_snoc" "$F" | head -12
echo "=== nodes arrays containing qnm_aggre_usb_south_snoc ==="
grep -n "qnm_aggre_usb_south_snoc" "$F" | head
