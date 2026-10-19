#!/bin/bash
set -u
DTS=/tmp/slim3b.dts
grep -n 'status = "disabled"' "$DTS" | cut -d: -f1 | while read -r L; do
  awk -v L="$L" 'NR<=L && $0 ~ /^[ \t]*[a-zA-Z0-9_,.-]+(@[0-9a-fxA-F]+)?:.*\{/ {line=NR": "$0} NR==L {print line; exit}' "$DTS"
done | sort | uniq -c | sort -rn
