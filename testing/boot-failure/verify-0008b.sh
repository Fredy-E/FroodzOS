#!/bin/bash
# 0008 verify: compile already proved all labels resolve; spot-check statuses.
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
ls -l "$DTB"
sha256sum "$DTB"
fdtdump "$DTB" 2>/dev/null | grep -A2 -E 'pcie@1c00000|regulator-wcn-1p9|thermal-sensor@c273000' | grep -E '\{|status' | head -12
echo ---
fdtdump "$DTB" 2>/dev/null | grep -c 'status = "disabled"'
