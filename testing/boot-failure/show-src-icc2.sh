#!/bin/bash
# interconnects + names lines for the four nodes in current hamoa.dtsi.
KSRC=/home/builder/src/ksrc
for ln in 5083 5151 5230 5321; do
  echo "== node at $ln:"; sed -n "$ln,$((ln+40))p" "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" | grep -E 'interconnects ?=|interconnect-names' | head -2
done
