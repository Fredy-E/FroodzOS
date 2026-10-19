#!/bin/bash
# Confirm gem_noc is back to okay, others still disabled.
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
sha256sum "$DTB"
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -A3 'gem_noc: interconnect@26400000' | head -5
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -A3 'nsp_noc: interconnect@320c0000' | head -5
