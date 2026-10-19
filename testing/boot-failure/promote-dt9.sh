#!/bin/bash
# Promote v2-dt9 UKI into staging; report hashes.
SRC=/home/builder/uki-v2-dt9/vmlinuz-live.efi
DST=/mnt/d/CachyOS-ARM64/live-staging-v2/EFI/Linux/kestrel-live.efi
cp "$SRC" "$DST"
sha256sum "$DST"
ls -l "$DST"
