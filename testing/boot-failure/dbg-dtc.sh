#!/bin/bash
# Debug: does dtc emit the nodes, and in what form?
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -nE 'pcie@1c00000|regulator-wcn-1p9' | head -6
echo "exit=$?"
