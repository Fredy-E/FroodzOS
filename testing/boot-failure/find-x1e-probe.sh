#!/bin/bash
# Find the x1e80100 probe function and list every HW-touching call in it.
KSRC=/home/builder/src/ksrc
grep -n 'platform_driver\|->probe\|_probe(' "$KSRC/drivers/interconnect/qcom/x1e80100.c" | head -10
