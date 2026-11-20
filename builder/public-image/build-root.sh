#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Root build of dev.2: Phase 1 root minus Falkon, plus the fixes from the first laptop test (rootfs-overlay/), without unpacking to disk.
#   public root squashfs (read-only) + overlay (upper layer in a loop-mounted file) -> pacman installs the packages -> mksquashfs of the merged view.
# Output: D:\FroodzOS-build\airootfs-${OUTNAME:-r4}.sfs. Needs sudo, an ARM64 builder, network access to the Arch Linux ARM mirror.
set -euo pipefail
OUTDIR=/mnt/d/FroodzOS-build
LOWERSFS=${LOWERSFS:-$OUTDIR/airootfs-phase1.sfs}
PINSHA=${PINSHA:-22dde19c5a9e0b2a6e00f30cce7d0866d08159e1127871793553cd0478d1aacf}
PKGS="${PKGS:-}"
VER_ID=${VER_ID:-0.1.0-dev.2}
BUILD_ID=${BUILD_ID:-maverick-public-dev-20261113.3}
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
  $PAC -Su --needed --print --print-format '%n %v %s' $PKGS > "$OUTDIR/${OUTNAME:-r4}-plan.txt" 2>&1 || true
  $PAC -Qu 2>/dev/null | wc -l | sed 's/^/upgradable installed packages: /'
  awk '{n++; s+=$3} END {printf "plan: %d packages, download %.0f MB\n", n, s/1e6}' "$OUTDIR/${OUTNAME:-r4}-plan.txt"
  for p in $PKGS; do
    if $PAC -Su --needed --print --print-format '%n' $p 2>/dev/null | grep -qx 'qt6-webengine'; then echo "pulls qt6-webengine: $p"; fi
  done
  exit 0
fi
echo "install start $(date -u +%T)"
# Falkon aborts under the kernel's user-namespace restriction and the project chose Chromium instead; -s also removes dependencies nothing else needs
$PAC -Rns --noconfirm falkon 2>&1 | tail -n 8 || true   # already gone when the input root is a later build (r10 and newer)
# full system upgrade together with the new packages: a partial upgrade is not supported on Arch
$PAC -Syu --needed --noconfirm --ignore linux-firmware $PKGS 2>&1 | tail -n 60
echo "install done $(date -u +%T)"
OVL=${OVL:-/mnt/d/CachyOS-ARM64/publication/20261110-revamp/repository/builder/public-image/rootfs-overlay}
for f in etc/mpv/mpv.conf etc/sysctl.d/90-froodzos-userns.conf usr/local/bin/fz-mount-image usr/share/applications/fz-mount-image.desktop usr/local/sbin/fz-smartlog etc/systemd/system/fz-smartlog.service etc/xdg/powerdevilrc usr/share/applications/fz-smartlog-now.desktop usr/local/sbin/fz-backlight-max usr/local/sbin/fz-kexec-uki usr/local/sbin/fz-stick-autorun etc/systemd/system/fz-stick-autorun.service usr/local/sbin/fz-persist etc/systemd/system/fz-persist.service usr/local/sbin/fz-bootmnt-ro etc/systemd/system/fz-bootmnt-ro.service usr/local/sbin/fz-sound-setup etc/systemd/system/fz-sound-setup.service usr/share/applications/fz-sound-setup.desktop etc/udev/rules.d/90-froodzos-internal-ro.rules etc/systemd/system/fz-touchpad.service.d/10-native-driver.conf etc/environment.d/90-froodzos.conf etc/systemd/system/fz-backlight-max.service etc/modules-load.d/90-froodzos-dsp.conf usr/local/bin/helium usr/local/bin/zen usr/share/applications/helium.desktop usr/share/applications/zen.desktop etc/systemd/system/NetworkManager.service.d/10-froodzos-stop.conf etc/systemd/system/iio-sensor-proxy.service.d/10-froodzos-stop.conf usr/share/alsa/ucm2/Qualcomm/x1e80100/LENOVO-Ideapad-3.conf usr/share/alsa/ucm2/Qualcomm/x1e80100/Ideapad-3-HiFi.conf; do
  mode=644; case "$f" in usr/local/bin/fz-mount-image|usr/local/sbin/fz-smartlog|usr/local/sbin/fz-backlight-max|usr/local/sbin/fz-kexec-uki|usr/local/sbin/fz-stick-autorun|usr/local/sbin/fz-persist|usr/local/sbin/fz-bootmnt-ro|usr/local/sbin/fz-sound-setup|usr/local/bin/helium|usr/local/bin/zen) mode=755;; esac
  sudo install -D -m "$mode" -o root -g root "$OVL/$f" "$BASE/merged/$f"
done
# sound: the ALSA card of this laptop is named X1E80100-LENOVO-Ideapad-3 (by short name and by long name) and matches no stock UCM profile
UCD="$BASE/merged/usr/share/alsa/ucm2/conf.d/x1e80100"
sudo ln -sf ../../Qualcomm/x1e80100/LENOVO-Ideapad-3.conf "$UCD/X1E80100-LENOVO-Ideapad-3.conf"
sudo ln -sf ../../Qualcomm/x1e80100/LENOVO-Ideapad-3.conf "$UCD/LENOVO-83N3-IdeaPadSlim315Q8X10-LNVNB161216.conf"
# topology: the T14s class (2 WSA speakers, 2 mics, WCD headset) uses the Romulus topology; with the Yoga Slim 7x one the ADSP rejected GRAPH_START
# (owner-tested 2026-11-19: Romulus plays through the speakers). The ADSP firmware itself is still the laptop's own and is not shipped.
sudo ln -sf X1E80100-Romulus-tplg.bin "$BASE/merged/usr/lib/firmware/qcom/x1e80100/X1E80100-LENOVO-Ideapad-3-tplg.bin"
# live-fix tools: the device-tree fix-up (needs dtc, installed through PKGS) next to the kexec helper
sudo install -D -m 755 -o root -g root "$OVL/../fz-dtb-fixup.py" "$BASE/merged/usr/local/sbin/fz-dtb-fixup.py"
sudo mkdir -p "$BASE/merged/etc/systemd/system/multi-user.target.wants"
sudo ln -sf ../fz-smartlog.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-smartlog.service"
sudo ln -sf ../fz-backlight-max.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-backlight-max.service"
sudo ln -sf ../fz-stick-autorun.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-stick-autorun.service"
sudo ln -sf ../fz-persist.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-persist.service"
sudo ln -sf ../fz-bootmnt-ro.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-bootmnt-ro.service"
sudo ln -sf ../fz-sound-setup.service "$BASE/merged/etc/systemd/system/multi-user.target.wants/fz-sound-setup.service"
# clock: the laptop has no usable RTC after a cold start; enable network time (what `systemctl enable systemd-timesyncd` does)
sudo mkdir -p "$BASE/merged/etc/systemd/system/sysinit.target.wants"
sudo ln -sf /usr/lib/systemd/system/systemd-timesyncd.service "$BASE/merged/etc/systemd/system/sysinit.target.wants/systemd-timesyncd.service"
sudo ln -sf /usr/lib/systemd/system/systemd-timesyncd.service "$BASE/merged/etc/systemd/system/dbus-org.freedesktop.timesync1.service"
# default applications: browser and disk images (appended to an existing /etc/xdg/mimeapps.list, else created)
M="$BASE/merged/etc/xdg/mimeapps.list"
if sudo test -f "$M"; then
  # (an input root built with this script already carries the lines: do not append them twice)
  sudo grep -q 'fz-mount-image' "$M" || grep -v '^\[Default Applications\]' "$OVL/etc/xdg-mimeapps-default.list" | sudo tee -a "$M" > /dev/null
else
  sudo install -D -m 644 -o root -g root "$OVL/etc/xdg-mimeapps-default.list" "$M"
fi
# browsers: Helium (GPL-3.0, Chromium based) and Zen (MPL-2.0, Firefox based), official linux-aarch64 release tarballs, unmodified
BD=${BROWSER_DIR:-$OUTDIR/browsers-dl}
HEL_SHA=720b90b55c190c25069d2443f121a0c3c4fee705564060d7b8d3f219aa9e1ef0; ZEN_SHA=8591434fcf498a836a32bc7314eb89fbdc4bdc8f03a2d735774b1ae69b6b21d5
test "$(sha256sum "$BD/helium-0.21.2.1-arm64_linux.tar.xz" | cut -d' ' -f1)" = "$HEL_SHA" || { echo "Helium tarball does not match the pin"; exit 4; }
test "$(sha256sum "$BD/zen.linux-aarch64.tar.xz" | cut -d' ' -f1)" = "$ZEN_SHA" || { echo "Zen tarball does not match the pin"; exit 4; }
sudo mkdir -p "$BASE/merged/opt"
if sudo test -x "$BASE/merged/opt/helium/helium" && sudo test -x "$BASE/merged/opt/zen/zen"; then
  echo "browsers already in the input root (same pinned tarballs): not unpacked again"
else
  sudo tar -xJf "$BD/helium-0.21.2.1-arm64_linux.tar.xz" -C "$BASE/merged/opt" --no-same-owner --no-same-permissions
  sudo mv "$BASE/merged/opt/helium-0.21.2.1-arm64_linux" "$BASE/merged/opt/helium"
  sudo tar -xJf "$BD/zen.linux-aarch64.tar.xz" -C "$BASE/merged/opt" --no-same-owner --no-same-permissions
fi
sudo chown -R root:root "$BASE/merged/opt/helium" "$BASE/merged/opt/zen"
sudo chmod -R go-w "$BASE/merged/opt/helium" "$BASE/merged/opt/zen"
# Helium ships every translation; keep English, Arabic and French (smaller image)
for f in "$BASE"/merged/opt/helium/locales/*.pak; do n=$(basename "$f" .pak); case "$n" in en-US*|en-GB*|ar*|fr*) ;; *) sudo rm -f "$f" ;; esac; done
sudo mkdir -p "$BASE/merged/usr/share/licenses/helium" "$BASE/merged/usr/share/licenses/zen-browser"
sudo install -m 644 "$BD/helium-LICENSE.txt" "$BASE/merged/usr/share/licenses/helium/LICENSE"
sudo install -m 644 "$BD/helium-LICENSE.ungoogled_chromium.txt" "$BASE/merged/usr/share/licenses/helium/LICENSE.ungoogled_chromium"
sudo install -m 644 "$BD/zen-LICENSE.txt" "$BASE/merged/usr/share/licenses/zen-browser/LICENSE"
printf 'Helium 0.21.2.1 (arm64), GPL-3.0 with Chromium components (BSD-3-Clause and others), unmodified official release from https://github.com/imputnet/helium-linux/releases/tag/0.21.2.1 (tag object c594074e635a6567694017258e73cff8a8235424). Tarball sha256 %s, signature checked against key BE67 7C19 89D3 5EAB 2C5F 26C9 3516 01AD 01D6 378E. Source: https://github.com/imputnet/helium-linux and https://github.com/imputnet/helium (see also the FroodzOS source offer).
' "$HEL_SHA" | sudo tee "$BASE/merged/usr/share/licenses/helium/SOURCE" > /dev/null
printf 'Zen Browser 1.24.2b (linux-aarch64), MPL-2.0, unmodified official release from https://github.com/zen-browser/desktop/releases/tag/1.24.2b . Tarball sha256 %s. Source: https://github.com/zen-browser/desktop (zen.source.tar.zst in the same release).
' "$ZEN_SHA" | sudo tee "$BASE/merged/usr/share/licenses/zen-browser/SOURCE" > /dev/null
sudo test -x "$BASE/merged/opt/helium/helium" && echo "helium present"; sudo test -x "$BASE/merged/opt/zen/zen" && echo "zen present"
sudo test ! -e "$BASE/merged/usr/bin/chromium" && echo "chromium absent"
sudo test ! -e "$BASE/merged/usr/bin/falkon" && echo "falkon gone"
if sudo test -x "$BASE/merged/usr/bin/udisksctl"; then echo "udisksctl present"; else echo "WARNING: no udisksctl"; fi
# identity: development increment of the same series
sudo sed -i -e "s/^VERSION=.*/VERSION=\"$VER_ID (Maverick)\"/" -e "s/^VERSION_ID=.*/VERSION_ID=\"$VER_ID\"/" -e "s/^BUILD_ID=.*/BUILD_ID=$BUILD_ID/" "$BASE/merged/etc/os-release" "$BASE/merged/usr/lib/os-release"
grep -E "^(VERSION|VERSION_ID|BUILD_ID)=" "$BASE/merged/etc/os-release"
pacman --root "$BASE/merged" --dbpath "$BASE/merged/var/lib/pacman" -Q > "$OUTDIR/${OUTNAME:-r4}-installed.txt"
wc -l < "$OUTDIR/${OUTNAME:-r4}-installed.txt"
# optional size reduction (PRUNE=1): see prune-root.sh
if [ "${PRUNE:-0}" = 1 ]; then
  $PAC -Rns --noconfirm signon-ui 2>&1 | tail -n 4 || true
  PRUNE_SH=${PRUNE_SH:-/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110/tools/prune-root.sh}
  . "$PRUNE_SH"
  # leftovers of the removed packages are fine; check the files the session needs
  for f in usr/lib/firmware/ath12k usr/lib/firmware/qcom/x1e80100 opt/helium/helium opt/zen/zen usr/bin/haruna usr/lib/libreoffice usr/local/sbin/fz-smartlog; do sudo test -e "$BASE/merged/$f" && echo "kept: $f" || echo "MISSING: $f"; done
  pacman --root "$BASE/merged" --dbpath "$BASE/merged/var/lib/pacman" -Q > "$OUTDIR/${OUTNAME:-r4}-installed.txt"
fi
# the shared-library cache is built here, so ldconfig.service (28 s on every live boot, measured 2026-11-18) is not needed at boot;
# packages installed in a running session still run ldconfig through their pacman hook
sudo ldconfig -r "$BASE/merged" && sudo test -s "$BASE/merged/etc/ld.so.cache" && echo "ld.so.cache built" || { echo "ldconfig failed"; exit 5; }
sudo ln -sf /dev/null "$BASE/merged/etc/systemd/system/ldconfig.service"
# release the bind mounts before squashing
for m in merged/dev merged/proc merged/sys; do sudo umount "$BASE/$m"; done
echo "mksquashfs start $(date -u +%T)"
sudo mksquashfs "$BASE/merged" "$OUTDIR/airootfs-${OUTNAME:-r4}.sfs" -comp xz -b 131072 -noappend -no-progress -processors 4 -mkfs-time 1794400000 > /dev/null
echo "mksquashfs done $(date -u +%T)"
sudo chown "$(id -u):$(id -g)" "$OUTDIR/airootfs-${OUTNAME:-r4}.sfs"
ls -l "$OUTDIR/airootfs-${OUTNAME:-r4}.sfs"
sha256sum "$OUTDIR/airootfs-${OUTNAME:-r4}.sfs" | tee "$OUTDIR/airootfs-${OUTNAME:-r4}.sfs.sha256"
echo ROOT_BUILD_OK
