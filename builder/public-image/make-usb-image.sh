#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Assemble a raw GPT disk image (one FAT32 partition labelled KESTREL_A64) from pre-built parts, without root:
#   standalone GRUB (own build from the Arch Linux ARM grub package), UKI(s), grub.cfg, fonts, and the live root squashfs.
#
#   make-usb-image.sh <out.img> <airootfs.sfs> <basedir> <grub.cfg> <uki.efi> [<uki.efi> ...]
#
# Layout written:  /EFI/BOOT/BOOTAA64.EFI  /EFI/Linux/<uki>  /boot/grub/grub.cfg  /boot/grub/arm64-efi/*.mod
#                  /<basedir>/aarch64/airootfs.sfs
# Environment: FZ_FONT_DIR (optional dir of .pf2 fonts copied to /boot/grub/fonts).
set -euo pipefail
OUT=$1; SFS=$2; BASE=$3; CFG=$4; shift 4
W=$(mktemp -d /tmp/mkimg.XXXXXX)
trap 'rm -rf "$W"' EXIT
GRUBDIR=/usr/lib/grub/arm64-efi
test -d "$GRUBDIR" || { echo "no $GRUBDIR (install the grub package)"; exit 2; }

# embedded config: find the partition by label, then load the real menu from it
cat > "$W/embedded.cfg" <<'EOF'
search --no-floppy --label KESTREL_A64 --set=root
set prefix=($root)/boot/grub
configfile $prefix/grub.cfg
EOF
MODS="mmap part_gpt part_msdos fat ext2 search search_label normal configfile linux chain gfxterm all_video efi_gop font echo test regexp smbios loadenv gzio terminal"
grub-mkstandalone -O arm64-efi -o "$W/BOOTAA64.EFI" --modules="$MODS" "boot/grub/grub.cfg=$W/embedded.cfg" >/dev/null

# size: payload + 5 percent + 64 MiB slack, rounded up to whole MiB, plus 2 MiB for the partition table and alignment
BYTES=$(stat -c %s "$SFS" "$CFG" "$W/BOOTAA64.EFI" "$@" | awk '{s+=$1} END {print s}')
MOD_BYTES=$(du -sb "$GRUBDIR" | cut -f1)
TOTAL=$(( (BYTES + MOD_BYTES) * 105 / 100 + 64*1024*1024 ))
MIB=$(( (TOTAL + 1048575) / 1048576 + 2 ))
rm -f "$OUT"; truncate -s "${MIB}M" "$OUT"
printf 'label: gpt\nstart=2048, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="KESTREL_A64"\n' | sfdisk --quiet "$OUT"
PART_SECT=$(( (MIB * 2048) - 2048 - 2048 ))          # leave the GPT backup area at the end
mkfs.vfat -F 32 -n KESTREL_A64 --offset 2048 "$OUT" $(( PART_SECT / 2 )) >/dev/null
MNT=$(mktemp -d /tmp/mkimg-mnt.XXXXXX)
sudo mount -t vfat -o loop,offset=1048576,uid="$(id -u)",gid="$(id -g)",umask=022 "$OUT" "$MNT"
trap 'sudo umount "$MNT" 2>/dev/null || true; rm -rf "$W" "$MNT"' EXIT
mkdir -p "$MNT/EFI/BOOT" "$MNT/EFI/Linux" "$MNT/boot/grub/arm64-efi" "$MNT/boot/grub/fonts" "$MNT/$BASE/aarch64"
cp "$W/BOOTAA64.EFI" "$MNT/EFI/BOOT/BOOTAA64.EFI"
for u in "$@"; do cp "$u" "$MNT/EFI/Linux/$(basename "$u")"; done
cp "$CFG" "$MNT/boot/grub/grub.cfg"
cp "$GRUBDIR"/*.mod "$GRUBDIR"/*.lst "$MNT/boot/grub/arm64-efi/" 2>/dev/null || true
if [ -n "${FZ_FONT_DIR:-}" ]; then cp "$FZ_FONT_DIR"/*.pf2 "$MNT/boot/grub/fonts/"; fi
cp "$SFS" "$MNT/$BASE/aarch64/airootfs.sfs"
sync
echo "image: $OUT ($MIB MiB)"
find "$MNT" -type f | head -n 12 || true
df -h "$MNT" | tail -1
sudo umount "$MNT"
sha256sum "$OUT" | cut -d' ' -f1 > "$OUT.sha256"
