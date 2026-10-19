#!/bin/bash
# qcom_icc_rpmh_probe body: every step, looking for HW access.
KSRC=/home/builder/src/ksrc
grep -n -A60 '^int qcom_icc_rpmh_probe' "$KSRC/drivers/interconnect/qcom/icc-rpmh.c" | head -75
