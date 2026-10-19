#!/bin/bash
# Verify the 0008 minimal-boot disables (sample + count).
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
ls -l "$DTB"
sha256sum "$DTB"
for n in pcie3 pcie5 vreg_wcn_1p9 vreg_wwan tsens2 ufs_mem_phy mdss_dp2_phy; do
  echo "$n = $(fdtget "$DTB" --plist 2>/dev/null | tr ' ' '\n' | grep -c . >/dev/null; fdtget -t s "$DTB" "/soc/$n" status 2>/dev/null || fdtget -t s "$DTB" "/$n" status 2>/dev/null || echo MISSING)"
done
