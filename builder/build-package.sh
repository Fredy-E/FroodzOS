#!/bin/bash
# Build + sign the linux-cachyos-arm64 package from the validated build tree (2026-10-08)
set -euo pipefail
rm -rf /home/builder/pkg-linux
sudo -u builder mkdir -p /home/builder/pkg-linux
cp /mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/PKGBUILD /home/builder/pkg-linux/
chown builder /home/builder/pkg-linux/PKGBUILD

sudo -u builder bash <<'BUILD'
set -e
export GNUPGHOME=/home/builder/.gnupg
cd /home/builder/pkg-linux
makepkg --sign --key builder@local --noconfirm --skipchecksums
ls -la
BUILD

PKG=$(ls /home/builder/pkg-linux/linux-cachyos-arm64-*.pkg.tar.* | grep -v '\.sig$' | head -1)
echo "package=$PKG"
pacman -U --noconfirm "$PKG"
pacman -Qi linux-cachyos-arm64 | head -8
ls -la /boot/vmlinuz-linux-cachyos-arm64 /boot/vmlinuz-cachyos-arm64.efi /boot/dtbs/linux-cachyos-arm64/
ls /lib/modules/ | head -3
echo KERNEL_PACKAGE_DONE
