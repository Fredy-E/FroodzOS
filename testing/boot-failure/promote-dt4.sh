#!/bin/bash
# Promote v2-dt4 UKI into staging; report hashes.
SRC=/home/builder/uki-v2-dt4/vmlinuz-live.efi
DST=/mnt/d/CachyOS-ARM64/live-staging-v2/EFI/Linux/kestrel-live.efi
cp "$SRC" "$DST"
sha256sum "$DST"
ls -l "$DST"
