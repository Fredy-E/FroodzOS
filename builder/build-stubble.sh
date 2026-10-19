#!/bin/bash
# Task 2.3 (part 1): build the stubble UKI stub from pinned ubuntu/stubble (2026-10-08)
set -euo pipefail
cd /home/builder/src
STUB_DIR=$(ls -d stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a | head -1)
cd "$STUB_DIR"
echo "== stubble tree =="
ls
echo "== build instructions in README =="
sed -n '/## Build/,/## /p' README.md | head -20
echo "== toolchain deps check =="
command -v meson && command -v ninja && echo MESON_OK || echo MESON_MISSING
echo STUBBLE_PREP_DONE
