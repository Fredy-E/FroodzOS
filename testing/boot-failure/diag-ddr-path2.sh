#!/bin/bash
set -u
DTS=/tmp/slim3-full.dts
echo "=== node with phandle 0xe5 ==="
grep -n "phandle = <0xe5>" "$DTS"
echo "=== status of interconnect@1770000 ==="
awk '/interconnect@1770000 \{/,/^\t\t\};/' "$DTS" | grep -E "status|compatible" | head -5
echo "=== x1e80100 interconnect driver in config ==="
grep -E "X1E80100|SM8650|X1P42100" /home/builder/src/ksrc/.config
echo "=== mc-virt driver source ==="
grep -rn "x1e80100-mc-virt\|mc_virt" /home/builder/src/ksrc/drivers/interconnect/qcom/*.c 2>/dev/null | grep -i "compatible\|driver\|match" | head -5
ls /home/builder/src/ksrc/drivers/interconnect/qcom/ | grep -iE "x1e|sm8|clk-virt" | head
echo "=== is 1770000 referenced in any disable patch? ==="
grep -rn "1770000\|usb_south_anoc" /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/*.patch 2>/dev/null | head -10
grep -rn "1770000" /mnt/d/CachyOS-ARM64/builder/*.sh 2>/dev/null | head -5
