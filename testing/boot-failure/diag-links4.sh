#!/bin/bash
set -u
F=/home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c
sed -n '949,962p' "$F"
echo "=== system_noc nodes around 2286 ==="
sed -n '2273,2300p' "$F"
echo "=== gem_noc nodes ==="
sed -n '1984,2010p' "$F"
