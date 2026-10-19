#!/bin/bash
set -u
DTS=/tmp/slim3-full.dts
for a in 1500000 1600000 1680000 16e0000 1700000 1740000 1780000 1770000; do
  echo "=== interconnect@$a ==="
  awk "/interconnect@$a \{/,/^\t\t\} failure/" "$DTS" 2>/dev/null | grep -E "compatible|status" | head -3
done
echo "=== top-level virt nodes ==="
awk '/^	clk_virt: interconnect-0 \{/,/^\t\};/' "$DTS" | head -8
awk '/^	mc_virt: interconnect-1 \{/,/^\t\};/' "$DTS" | head -8
echo "=== 1770000 clocks/power ==="
awk '/interconnect@1770000 \{/,/^\t\t\};/' "$DTS" | grep -E "clocks|power-domains|required-opps|operating-points|status" | head -8
echo "=== which nodes do 0006/0007/0008 disable ==="
grep -h "^[+-].*status" /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/0006*.patch /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/0007*.patch /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/0008*.patch 2>/dev/null | sort | uniq -c | head -20
grep -h "^[+-]&" /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/0008*.patch 2>/dev/null | head -30
