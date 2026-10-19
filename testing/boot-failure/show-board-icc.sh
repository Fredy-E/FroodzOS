#!/bin/bash
# Board-level USB interconnect overrides (source of apps-usb?).
KSRC=/home/builder/src/ksrc
grep -n -B2 -A4 'interconnects' "$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts" | head -40
