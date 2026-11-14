#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Phase 1 root: add file-handling applications to the firmware-free public root without unpacking it to disk.
#   public root squashfs (read-only) + overlay (upper layer in a loop-mounted file) -> pacman installs the packages -> mksquashfs of the merged view.
# Output: D:\FroodzOS-build\airootfs-phase1.sfs. Needs sudo, an ARM64 builder, network access to the Arch Linux ARM mirror.
set -euo pipefail
OUTDIR=/mnt/d/FroodzOS-build
LOWERSFS=${LOWERSFS:-$OUTDIR/airootfs-public.sfs}
PINSHA=${PINSHA:-e6f4a596a99e215eb39000a46a8ab512b7af2f7136533c431b235b92cceba981}
PKGS="falkon ark 7zip unrar unzip zip cabextract lhasa unshield squashfs-tools erofs-utils dosfstools exfatprogs ntfs-3g mtools okular gwenview kimageformats libheif libjxl libavif haruna mpv elisa kate ffmpegthumbs kdegraphics-thumbnailers libreoffice-fresh"
VER_ID=${VER_ID:-0.1.0-dev.2}
BUILD_ID=${BUILD_ID:-maverick-public-dev-20261111.3}
test "$(sha256sum "$LOWERSFS" | cut -d' ' -f1)" = "$PINSHA" || { echo "input root does not match the pin"; exit 2; }
BASE=/home/builder/ovl-$(date +%s); mkdir -p "$BASE"/{lower,tmp,merged,gnupg}
cleanup() {
  for m in merged/dev merged/proc merged/sys merged; do sudo umount "$BASE/$m" 2>/dev/null || true; done
  sudo umount "$BASE/tmp" 2>/dev/null || true
  sudo umount "$BASE/lower" 2>/dev/null || true
}
trap cleanup EXIT
sudo mount -t squashfs -o loop,ro "$LOWERSFS" "$BASE/lower"
# upper layer: a sparse ext4 image on C: (keeps the builder's VHDX on D: from growing); delete the file afterwards
UPPERIMG=$OUTDIR/upper-layer-$(date +%s).img
test ! -e "$UPPERIMG" || { echo "$UPPERIMG exists: delete it first"; exit 3; }
truncate -s 8G "$UPPERIMG"; mkfs.ext4 -q -O ^has_journal "$UPPERIMG"
sudo mount -o loop "$UPPERIMG" "$BASE/tmp"
sudo mkdir -p "$BASE/tmp/upper" "$BASE/tmp/work"
sudo chown root:root "$BASE/tmp/upper"; sudo chmod 555 "$BASE/tmp/upper"
sudo mount -t overlay overlay -o lowerdir="$BASE/lower",upperdir="$BASE/tmp/upper",workdir="$BASE/tmp/work" "$BASE/merged"
sudo mount --bind /dev "$BASE/merged/dev"; sudo mount -t proc proc "$BASE/merged/proc"; sudo mount -t sysfs sysfs "$BASE/merged/sys"
# pacman configuration: the image's repositories with the builder's working mirrors
cat > "$BASE/pacman.conf" <<'EOF'
[options]
HoldPkg     = pacman glibc
Architecture = aarch64
CheckSpace
ParallelDownloads = 5
SigLevel    = Required DatabaseOptional
LocalFileSigLevel = Required
[core]
Server = http://mirror.archlinuxarm.org/$arch/$repo
Server = https://de3.mirror.archlinuxarm.org/$arch/$repo
[extra]
Server = http://mirror.archlinuxarm.org/$arch/$repo
Server = https://de3.mirror.archlinuxarm.org/$arch/$repo
[alarm]
Server = http://mirror.archlinuxarm.org/$arch/$repo
Server = https://de3.mirror.archlinuxarm.org/$arch/$repo
[aur]
Server = http://mirror.archlinuxarm.org/$arch/$repo
Server = https://de3.mirror.archlinuxarm.org/$arch/$repo
EOF
mkdir -p "$OUTDIR/pkgcache"
PAC="sudo pacman --config $BASE/pacman.conf --root $BASE/merged --dbpath $BASE/merged/var/lib/pacman --gpgdir $BASE/merged/etc/pacman.d/gnupg --cachedir $OUTDIR/pkgcache"
if [ -n "${FZ_PLAN_ONLY:-}" ]; then
  # refresh the sync databases (the image's are older than the mirror) and show what a full upgrade plus the packages would do
  $PAC -Sy --noconfirm > /dev/null 2>&1 || true
  $PAC -Su --needed --print --print-format '%n %v %s' $PKGS > "$OUTDIR/phase1-plan.txt" 2>&1 || true
  $PAC -Qu 2>/dev/null | wc -l | sed 's/^/upgradable installed packages: /'
  awk '{n++; s+=$3} END {printf "plan: %d packages, download %.0f MB\n", n, s/1e6}' "$OUTDIR/phase1-plan.txt"
  for p in $PKGS; do
    if $PAC -Su --needed --print --print-format '%n' $p 2>/dev/null | grep -qx 'qt6-webengine'; then echo "pulls qt6-webengine: $p"; fi
  done
  exit 0
fi
echo "install start $(date -u +%T)"
# full system upgrade together with the new packages: a partial upgrade is not supported on Arch
$PAC -Syu --needed --noconfirm --ignore linux-firmware $PKGS 2>&1 | tail -n 60
echo "install done $(date -u +%T)"
# identity: development increment of the same series
sudo sed -i -e "s/^VERSION=.*/VERSION=\"$VER_ID (Maverick)\"/" -e "s/^VERSION_ID=.*/VERSION_ID=\"$VER_ID\"/" -e "s/^BUILD_ID=.*/BUILD_ID=$BUILD_ID/" "$BASE/merged/etc/os-release" "$BASE/merged/usr/lib/os-release"
grep -E "^(VERSION|VERSION_ID|BUILD_ID)=" "$BASE/merged/etc/os-release"
pacman --root "$BASE/merged" --dbpath "$BASE/merged/var/lib/pacman" -Q > "$OUTDIR/phase1-installed.txt"
wc -l < "$OUTDIR/phase1-installed.txt"
# release the bind mounts before squashing
for m in merged/dev merged/proc merged/sys; do sudo umount "$BASE/$m"; done
echo "mksquashfs start $(date -u +%T)"
sudo mksquashfs "$BASE/merged" "$OUTDIR/airootfs-phase1.sfs" -comp xz -b 131072 -noappend -no-progress -processors 4 -mkfs-time 1794400000 > /dev/null
echo "mksquashfs done $(date -u +%T)"
sudo chown "$(id -u):$(id -g)" "$OUTDIR/airootfs-phase1.sfs"
ls -l "$OUTDIR/airootfs-phase1.sfs"
sha256sum "$OUTDIR/airootfs-phase1.sfs" | tee "$OUTDIR/airootfs-phase1.sfs.sha256"
echo PHASE1_ROOT_OK
