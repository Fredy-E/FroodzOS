#!/bin/bash
# The driver's probe entry (around line 2386) + its callees.
KSRC=/home/builder/src/ksrc
sed -n '2375,2400p' "$KSRC/drivers/interconnect/qcom/x1e80100.c"
echo '=== qcom_icc_probe location ==='
grep -rn 'int qcom_icc_probe\|EXPORT.*qcom_icc_probe' "$KSRC/drivers/interconnect/qcom/"*.c | head -3
