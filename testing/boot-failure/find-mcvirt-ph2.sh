#!/bin/bash
# mc_virt phandle line itself.
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -A5 'mc_virt: interconnect-1' | head -7
