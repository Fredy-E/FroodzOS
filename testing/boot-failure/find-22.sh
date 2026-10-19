#!/bin/bash
# What provides power-domain 0x22 (needed by apps_rsc)?
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n 'phandle = <0x22>;' "$DTS" | head -3
