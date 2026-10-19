#!/bin/bash
# eusb2 repeater chain: what does smb2360_0 need?
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n -B2 -A14 'smb2360_0_eusb2_repeater:' "$DTS" | head -25
