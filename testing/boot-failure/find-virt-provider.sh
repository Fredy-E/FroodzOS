#!/bin/bash
# Which drivers provide clk-virt / mc-virt? Are they built in?
KSRC=/home/builder/src/ksrc
grep -rln 'x1e80100-clk-virt\|x1e80100-mc-virt\|qcom,clk-virt\|qcom,mc-virt' "$KSRC/drivers/interconnect/" | head -5
echo ---
grep -rn 'mc-virt\|clk-virt' "$KSRC/drivers/interconnect/qcom/icc-rpmh.c" 2>/dev/null | head -5
echo --- ; grep -rn 'OF_DECLARE\|of_match' "$KSRC/drivers/interconnect/qcom/qnoc-x1.c" | head -3
