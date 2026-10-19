#!/bin/bash
# Who is tlmm's wakeup-parent 0x99?
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n 'phandle = <0x99>;' "$DTS" | head -3
