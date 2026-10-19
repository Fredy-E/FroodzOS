#!/bin/bash
# Is the BCM voter (needed by clk-virt/mc-virt, needed by SCM) built in?
KSRC=/home/builder/src/ksrc
grep -E 'INTERCONNECT_QCOM(_BCM_VOTER|_OSM_L3)?=' "$KSRC/.config"
echo ---
grep -rn 'bcm-voter\|bcm voter' "$KSRC/drivers/interconnect/qcom/icc-rpmh.c" 2>/dev/null | head -3
echo --- ; ls "$KSRC/drivers/interconnect/qcom/" | head -30
