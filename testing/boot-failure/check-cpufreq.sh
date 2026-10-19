#!/bin/bash
# What node owns line 762's interconnects? Is qcom-cpufreq-hw built in?
DTS=/home/builder/boot-failure-tests/slim3.dts
awk 'NR<=762 && /^\t*[a-z0-9_]+:?[ \t]+[a-z0-9_.-]+(@[0-9a-fx,]+)? *\{/ {last=NR": "$0} END{}' "$DTS" >/dev/null
sed -n '700,762p' "$DTS" | grep -E '^\t*[a-z0-9_]+:' | tail -5
echo '=== cpufreq-hw ==='
grep -E '^CONFIG_(ARM_QCOM_CPUFREQ_HW|QCOM_CPUFREQ_HW)' /home/builder/src/ksrc/.config
grep -c 'qcom_cpufreq_hw_driver_init' /home/builder/src/ksrc/System.map
