#!/bin/bash
# Status lines for gem vs nsp (wider window).
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
D=$(dtc -I dtb -O dts "$DTB" 2>/dev/null)
echo "$D" | grep -A10 'gem_noc: interconnect@26400000' | grep -E 'status|clock' | head -3
echo "$D" | grep -A10 'nsp_noc: interconnect@320c0000' | grep -E 'status|clock' | head -3
