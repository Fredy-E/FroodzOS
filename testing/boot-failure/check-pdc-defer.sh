#!/bin/bash
# Why would qcom-pdc defer? Check its probe's -EPROBE_DEFER paths.
KSRC=/home/builder/src/ksrc
grep -n 'EPROBE_DEFER\|defer' "$KSRC/drivers/irqchip/qcom-pdc.c" | head -10
