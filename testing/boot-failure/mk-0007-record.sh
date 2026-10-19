#!/bin/bash
# Emit tail context of the board DTS for the 0007 patch record.
BOARD=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts
wc -l "$BOARD"
tail -n 20 "$BOARD"
