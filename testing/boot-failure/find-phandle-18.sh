#!/bin/bash
# Find the node carrying phandle 0x18 (decimal 24 also possible).
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n 'phandle = <0x18>\|phandle = <24>' "$DTS" | head -5
