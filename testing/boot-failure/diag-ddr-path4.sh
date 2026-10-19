#!/bin/bash
set -u
DT=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
DTS=/tmp/slim3b.dts
dtc -I dtb -O dts "$DT" -o "$DTS"
echo "decompiled: $(wc -l < "$DTS") lines"
for a in 1500000 1680000 16e0000 1700000 1770000 1780000; do
  echo "=== @$a ==="
  grep -A25 "interconnect@$a {" "$DTS" | grep -E "compatible|status =|clocks =|power-domains" | head -6
done
echo "=== virt-0/virt-1 ==="
grep -A8 "^	mc_virt: interconnect-1 {" "$DTS" | head -10
grep -A8 "^	clk_virt: interconnect-0 {" "$DTS" | head -10
echo "=== rpmhpd node + driver ==="
grep -n "rpmhpd" "$DTS" | head -5
grep -E "CONFIG_QCOM_RPMHPD|CONFIG_INTERCONNECT_QCOM_X1E80100" /home/builder/src/ksrc/.config
