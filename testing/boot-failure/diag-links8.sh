#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
sed -n '933,948p' "$F"
echo "=== pcie_south_anoc nodes array ==="
sed -n '2242,2272p' "$F"
