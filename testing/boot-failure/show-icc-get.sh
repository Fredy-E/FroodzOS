#!/bin/bash
# of_icc_get_by_index + of_icc_get_from_provider: exact failure conditions.
KSRC=/home/builder/src/ksrc
grep -n -B5 -A30 '^struct icc_path \*of_icc_get_by_index' "$KSRC/drivers/interconnect/core.c" | head -60
