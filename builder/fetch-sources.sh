#!/bin/bash
# Phase 2 Task 2.1: pin + fetch kernel/stubble sources (2026-10-08)
set -e
SRC=/home/builder/src
mkdir -p "$SRC/pins"
cd "$SRC"

SHA=$(curl -fsSL 'https://api.github.com/repos/jglathe/linux_ms_dev_kit/branches/jg%2Fubuntu-qcom-x1e-7.3rc' | grep -o '"sha": *"[0-9a-f]\{40\}"' | head -1 | grep -o '[0-9a-f]\{40\}')
echo "jglathe branch head sha: $SHA (research pin was bc513d262c8d)"
STUBBLE_SHA=9f11278e080a5c4a77db6acf4c8f75c14412087a

if [ ! -f "linux-ms-dev-kit-$SHA.tar.gz" ]; then
    curl -fL --retry 3 -o "linux-ms-dev-kit-$SHA.tar.gz" "https://codeload.github.com/jglathe/linux_ms_dev_kit/tar.gz/$SHA"
fi
if [ ! -f "stubble-$STUBBLE_SHA.tar.gz" ]; then
    curl -fL --retry 3 -o "stubble-$STUBBLE_SHA.tar.gz" "https://codeload.github.com/ubuntu/stubble/tar.gz/$STUBBLE_SHA"
fi

sha256sum ./*.tar.gz | tee "$SRC/pins/SHA256SUMS"
echo "== stubble HWID json present? =="
tar tzf "stubble-$STUBBLE_SHA.tar.gz" | grep 'x126100-lenovo-ideapad-slim3.json'
echo "== Slim 3 DTS present? =="
tar tzf "linux-ms-dev-kit-$SHA.tar.gz" | grep 'x126100-lenovo-ideapad-slim3.dts'
echo "== tree config candidates =="
tar tzf "linux-ms-dev-kit-$SHA.tar.gz" | grep -E 'arch/arm64/configs/[^/]+$' | head -10
echo FETCH_SOURCES_OK
