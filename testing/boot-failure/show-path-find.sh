#!/bin/bash
# path_find: duplicate (src,dst) handling.
KSRC=/home/builder/src/ksrc
grep -n -B3 -A25 '^static struct icc_path \*path_find' "$KSRC/drivers/interconnect/core.c" | head -45
