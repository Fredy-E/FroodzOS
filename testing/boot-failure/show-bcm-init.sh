#!/bin/bash
# qcom_icc_bcm_init: does it touch HW?
KSRC=/home/builder/src/ksrc
grep -n -B2 -A25 'qcom_icc_bcm_init(struct qcom_icc_bcm' "$KSRC/drivers/interconnect/qcom/icc-rpmh.c" | head -40
