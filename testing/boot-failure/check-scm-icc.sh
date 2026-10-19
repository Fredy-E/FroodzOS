#!/bin/bash
# Is SCM's interconnect optional? Check its probe path handling.
KSRC=/home/builder/src/ksrc
grep -n -B3 -A8 'of_icc_get\|icc_path\|devm_of_icc' "$KSRC/drivers/firmware/qcom/qcom_scm.c" | head -40
