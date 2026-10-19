#!/bin/bash
# What is phandle 0x1d (bcm-voters target)? Which driver binds virt descs?
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n 'phandle = <0x1d>;' "$DTS" | head -3
echo '=== virt probe fn ==='
grep -n -B2 -A12 'x1e80100_clk_virt\s*=\|x1e80100_mc_virt\s*=' /home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c | grep -E 'icc_rpmh_probe|icc_provider|platform_driver|of_match|compatible' | head -8
grep -n 'compatible.*virt\|VIRT.*compatible\|of_device_id.*virt' /home/builder/src/ksrc/drivers/interconnect/qcom/x1e80100.c | head -8
