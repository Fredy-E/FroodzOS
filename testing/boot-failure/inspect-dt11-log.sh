#!/bin/bash
# Inspect dt11 build log for validation + hook evidence.
LOG=/mnt/d/CachyOS-ARM64/testing/boot-failure/build-uki-v2-dt11.log
grep -E 'passed|kestrel_log|board_firmware|LIVE_UKI_DONE|UKI_BUILD_EXIT' "$LOG" | head -12
