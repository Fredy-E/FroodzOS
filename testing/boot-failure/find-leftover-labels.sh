#!/bin/bash
# Find labels for leftover minimal-boot targets.
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -nE '^\s*([a-z0-9_]+:\s*)?(pcie@1b0000|hdmi-bridge|aux_bridge|gpio-keys)\s*\{' "$DTS" | head -20
echo ---
grep -nE 'pcie@1b00000' "$DTS" | head -5
