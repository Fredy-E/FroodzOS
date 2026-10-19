#!/bin/bash
# Where is the gem_noc node body defined?
KSRC=/home/builder/src/ksrc
grep -rn 'gem_noc: interconnect@26400000' "$KSRC/arch/arm64/boot/dts/qcom/" | head -5
