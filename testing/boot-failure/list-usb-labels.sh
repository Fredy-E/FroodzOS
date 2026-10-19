#!/bin/bash
# Labels + current interconnects of the four dwc3 nodes.
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n -B1 'usb@a[2468]00000' "$DTS" | grep -E '^[0-9]+[-:]\s*[a-z0-9_]+: usb@' | head -6
echo '=== a400000/a600000/a800000 interconnects (first 120 chars) ==='
for a in a400000 a600000 a800000; do
  echo "-- $a:"; grep -n -A12 "usb@$a" "$DTS" | grep -E 'interconnects ?=|interconnect-names' | head -2
done
