#!/bin/bash
# What are 0xe5 / 0x18 in the CURRENT tree? What is mailbox@17430000?
KSRC=/home/builder/src/ksrc
for ph in 0xe5 0x18; do
  ln=$(grep -n "phandle = <$ph>;" "$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts" "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" 2>/dev/null | head -1)
  echo "== $ph: $ln"
done
echo '=== mailbox node ==='
grep -n -B3 -A8 'mailbox@17430000' "$KSRC/arch/arm64/boot/dts/qcom/hamoa.dtsi" 2>/dev/null | head -16
