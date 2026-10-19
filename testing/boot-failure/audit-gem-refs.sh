#!/bin/bash
# gem_noc's phandle, then every node whose interconnects reference it.
DTS=/home/builder/boot-failure-tests/slim3.dts
GPH=$(grep -n -A6 'gem_noc: interconnect@26400000' "$DTS" | grep -oE 'phandle = <0x[0-9a-f]+>' | head -1 | grep -oE '0x[0-9a-f]+')
echo "gem phandle: $GPH"
grep -n "interconnects = <[^;]*$GPH" "$DTS" | head -20
