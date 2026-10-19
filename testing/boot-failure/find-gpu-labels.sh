#!/bin/bash
# Labels for gpu + gmu nodes.
DTS=/home/builder/boot-failure-tests/slim3.dts
grep -n -E '^\s*[a-z0-9_]+:\s*(gpu@3d00000|gmu@3d6a000)' "$DTS" | head -4
