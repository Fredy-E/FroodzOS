#!/bin/bash
# What is dwc3's phy 0xe9, and is it enabled?
DTS=/home/builder/boot-failure-tests/slim3.dts
ln=$(grep -n 'phandle = <0xe9>;' "$DTS" | head -1 | cut -d: -f1)
echo "line $ln:"; sed -n "$((ln-8)),$((ln+1))p" "$DTS" | grep -E ':|compatible|status' | head -6
