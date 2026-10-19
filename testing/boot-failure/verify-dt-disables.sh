#!/bin/bash
# Verify the six diagnostic DT disables in the rebuilt Slim 3 DTB.
DTB=/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb
ls -l "$DTB"
sha256sum "$DTB"
for spec in "pcie_south_anoc:interconnect@16c0000" "gem_noc:interconnect@26400000" \
  "nsp_noc:interconnect@320c0000" "lpass_ag_noc:interconnect@7e40000" \
  "lpass_lpiaon_noc:interconnect@7400000" "lpass_lpicx_noc:interconnect@7430000"; do
  label="${spec%%:*}"
  node="${spec##*:}"
  st="$(fdtget "$DTB" "/soc/$node" status 2>/dev/null)"
  echo "$label = $st"
done
