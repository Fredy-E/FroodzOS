#!/bin/bash
# How do mc-virt/clk-virt probe, and is apps_bcm present/enabled?
KSRC=/home/builder/src/ksrc
grep -n 'mc-virt\|clk-virt\|mc_virt\|clk_virt' "$KSRC/drivers/interconnect/qcom/x1e80100.c" | head -10
echo '=== apps_bcm node ==='
grep -n -A6 'apps_bcm:' /home/builder/boot-failure-tests/slim3.dts | head -12
