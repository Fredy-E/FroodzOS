#!/bin/bash
# Promote the v2-dt2 UKI into the private staging tree.
SRC=/home/builder/uki-v2-dt2/vmlinuz-live.efi
DST=/mnt/d/CachyOS-ARM64/live-staging-v2/EFI/Linux/kestrel-live.efi
cp "$SRC" "$DST"
sha256sum "$DST"
ls -l "$DST"
