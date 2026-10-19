#!/bin/bash
# Confirm 0008 nodes carry status=disabled (wider context).
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
fdtdump "$DTB" 2>/dev/null | grep -A6 -E 'pcie@1c00000 \{|regulator-wcn-1p9 \{|thermal-sensor@c273000 \{|phy@1d80000 \{' | grep -E '\{|status'
