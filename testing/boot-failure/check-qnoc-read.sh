#!/bin/bash
# Does the x1e80100/qnoc probe path MMIO-read the region?
KSRC=/home/builder/src/ksrc
grep -n 'readl\|regmap_read\|ioread\|revision\|qcom_icc_get_revision' "$KSRC/drivers/interconnect/qcom/x1e80100.c" | head -10
echo '=== common probe ==='
ls "$KSRC/drivers/interconnect/qcom/" | grep -iE 'common|qnoc' | head -5
grep -rn 'readl\|regmap_read' "$KSRC/drivers/interconnect/qcom/icc-common.c" 2>/dev/null | head -5
