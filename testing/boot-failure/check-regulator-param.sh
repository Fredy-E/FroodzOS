#!/bin/bash
# Does regulator_ignore_unused exist as a cmdline param?
KSRC=/home/builder/src/ksrc
grep -rn 'regulator_ignore_unused\|ignore_unused' "$KSRC/drivers/regulator/core.c" | head -5
echo '=== regulator_init_complete body ==='
grep -n -A15 'static int __init regulator_init_complete' "$KSRC/drivers/regulator/core.c" | head -25
