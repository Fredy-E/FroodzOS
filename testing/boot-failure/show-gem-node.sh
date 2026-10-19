#!/bin/bash
# Full gem_noc node from source DTS.
grep -n -A25 'gem_noc: interconnect@26400000' /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x1e80100.dtsi 2>/dev/null | head -30
echo '=== board overrides for gem ==='
grep -n -A8 '&gem_noc' /home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts | head -20
