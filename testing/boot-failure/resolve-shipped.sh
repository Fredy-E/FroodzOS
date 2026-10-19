#!/bin/bash
# In the SHIPPED dtb (dt8), what nodes own phandles 0xe8/0xe5/0x18/0x36?
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
D=$(dtc -I dtb -O dts "$DTB" 2>/dev/null)
for ph in 0xe8 0xe5 0x18 0x36 0x37; do
  ln=$(echo "$D" | grep -n "phandle = <$ph>;" | head -1 | cut -d: -f1)
  if [ -n "$ln" ]; then echo "== $ph:"; echo "$D" | sed -n "$((ln-6)),$((ln))p" | grep -E ':|compatible' | head -3; else echo "== $ph: NOT FOUND"; fi
done
