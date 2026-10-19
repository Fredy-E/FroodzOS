#!/bin/bash
# mc_virt's actual phandle in the current DTB + the usb_2 full lines.
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -B5 -A2 'mc-virt' | head -20
