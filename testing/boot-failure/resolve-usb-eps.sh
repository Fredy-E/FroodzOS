#!/bin/bash
# Resolve dwc3 icc endpoints 0xe8, 0x36, 0x37 (0x18 = mc_virt known).
DTS=/home/builder/boot-failure-tests/slim3.dts
for ph in 0xe8 0x36 0x37 0xe9; do
  ln=$(grep -n "phandle = <$ph>;" "$DTS" | head -1 | cut -d: -f1)
  if [ -n "$ln" ]; then
    echo "== $ph (line $ln):"; sed -n "$((ln-6)),$((ln))p" "$DTS" | grep -E ':|compatible' | head -4
  else
    echo "== $ph: NOT FOUND"
  fi
done
