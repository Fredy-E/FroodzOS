#!/bin/bash
# What is phandle 0x1b (gem/nsp bcm-voters target)?
DTS=/home/builder/boot-failure-tests/slim3.dts
ln=$(grep -n 'phandle = <0x1b>;' "$DTS" | head -1 | cut -d: -f1)
echo "line $ln:"; sed -n "$((ln-5)),$((ln+2))p" "$DTS"
