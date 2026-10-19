#!/bin/bash
# What are repeater supplies 0x11e / 0x11f?
DTS=/home/builder/boot-failure-tests/slim3.dts
for ph in 0x11e 0x11f 0xe0 0xb6; do
  ln=$(grep -n "phandle = <$ph>;" "$DTS" | head -1 | cut -d: -f1)
  if [ -n "$ln" ]; then echo "== $ph:"; sed -n "$((ln-4)),$((ln))p" "$DTS" | grep -E ':|regulator-name' | head -3; else echo "== $ph: NOT FOUND"; fi
done
