#!/bin/bash
# Task 3.4: local-only Qualcomm firmware staging for the Lenovo 83N3 (ADR-5).
# Copies firmware from the machine's OWN Windows installation (read-only) into
# the live session's firmware path. NEVER uploads or redistributes anything.
#
# Usage (in a live session or from the builder with the Windows drive mounted):
#   sudo ./setup-local-firmware.sh [--source <driverstore-dir>] [--dry-run]
set -euo pipefail

DEST="/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3"
# DTS firmware names (x126100-lenovo-ideapad-slim3.dts) [design 2.3]
FILES=(
  qcadsp8380.mbn qccdsp8380.mbn qcdxkmsuc8380.mbn qcdxkmsucpurwa.mbn
  adsp_dtbs.elf cdsp_dtbs.elf
  adspr.jsn adsps.jsn adspua.jsn battmgr.jsn
)

DRY_RUN=0
SOURCE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --source) SOURCE="$2"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

# locate the Windows DriverStore (read-only)
if [ -z "$SOURCE" ]; then
  for root in /mnt/c /mnt/win /media/*; do
    cand="$root/Windows/System32/DriverStore/FileRepository"
    [ -d "$cand" ] && SOURCE="$cand" && break
  done
fi
[ -n "$SOURCE" ] && [ -d "$SOURCE" ] || { echo "ERROR: Windows DriverStore not found; pass --source" >&2; exit 1; }
echo "Source: $SOURCE (read-only search)"

# refuse to run against a BitLocker volume we cannot read
if ! ls "$SOURCE" >/dev/null 2>&1; then
  echo "ERROR: cannot read DriverStore (BitLocker locked?). Unlock/read-only-mount first." >&2
  exit 1
fi

mkdir -p "$DEST"
FOUND=0; MISSING=0
for f in "${FILES[@]}"; do
  # newest match wins (mirrors qcom-firmware-extract behavior)
  path=$(find "$SOURCE" -name "$f" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
  if [ -n "$path" ]; then
    echo "STAGE $f  <-  $path"
    if [ "$DRY_RUN" -eq 0 ]; then install -m 0644 "$path" "$DEST/$f"; fi
    FOUND=$((FOUND+1))
  else
    echo "MISS $f"
    MISSING=$((MISSING+1))
  fi
done

echo "staged=$FOUND missing=$MISSING dest=$DEST"
[ "$DRY_RUN" -eq 1 ] && echo "(dry-run: nothing written)"
echo "$FOUND files staged locally; these are NOT redistributable (see design ADR-5)."
