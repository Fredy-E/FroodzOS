#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the firmware-free public-build root from the pinned private candidate SFS without unpacking it to disk:
# loop-mount (read-only) -> tar stream -> public-root-filter.py -> sqfstar. Output goes to D:\FroodzOS-build (D: is tight).
set -euo pipefail
B=/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110
IN=$B/input/airootfs.sfs
OUTDIR=/mnt/d/FroodzOS-build
M=/home/builder/mnt-cand
PIN=972f1ffd763e123bad6094d938c75878c57f69a4bdbb85698f9eb3dafba1c805   # touchpad driver image r5 (candidate + 6 added entries)
mkdir -p "$OUTDIR" "$M"
echo "pin check $(date -u +%T)"
test "$(sha256sum "$B/tp-auto/output/airootfs-tp.sfs" | cut -d' ' -f1)" = "$PIN" || { echo "candidate SFS does not match the pin"; exit 2; }
mountpoint -q "$M" && sudo umount "$M"
sudo mount -t squashfs -o loop,ro "$B/tp-auto/output/airootfs-tp.sfs" "$M"
trap 'sudo umount "$M" 2>/dev/null || true' EXIT
echo "build start $(date -u +%T)"
EPOCH=${FZ_EPOCH:-1794400000}
sudo tar --numeric-owner --xattrs --acls --sort=name -C "$M" -cf - . \
  | python3 -B "$B/tools/public-root-filter.py" "$M" "$OUTDIR/filter-report.json" \
  | sqfstar -comp xz -b 131072 -root-mode 555 -root-uid 0 -root-gid 0 -no-progress -processors 4 -mkfs-time "$EPOCH" "$OUTDIR/airootfs-public.sfs"
echo "build done $(date -u +%T)"
ls -l "$OUTDIR/airootfs-public.sfs"
sha256sum "$OUTDIR/airootfs-public.sfs" | tee "$OUTDIR/airootfs-public.sfs.sha256"
echo BUILD_OK
