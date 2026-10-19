#!/bin/bash
# Task 1.4 (G0b) + Task 1.5 (G1) on CachyOSBuilder (2026-10-08)
set -e

echo "== G0b: toolchain baseline probe =="
echo 'int main(){return 0;}' | gcc -x c - -o /tmp/g0b-probe
readelf -A /tmp/g0b-probe | grep -E 'Tag_CPU_arch|Tag_FP_arch' | head -3
echo "-- libc --"
readelf -A /usr/lib/libc.so.6 | grep Tag_CPU_arch | head -2
echo "-- gcc defaults --"
gcc -Q --help=target 2>/dev/null | grep -E 'march=|mtune=' | head -3

echo "== G1: first signed package =="
rm -rf /home/builder/g1
sudo -u builder mkdir -p /home/builder/g1
cp /mnt/d/CachyOS-ARM64/pkgs/cachyos-arm64-hello/PKGBUILD /home/builder/g1/
chown builder /home/builder/g1/PKGBUILD

sudo -u builder bash <<'BUILD'
set -e
export GNUPGHOME=/home/builder/.gnupg
mkdir -p "$GNUPGHOME"; chmod 700 "$GNUPGHOME"
if ! gpg --list-keys builder@local >/dev/null 2>&1; then
    gpg --batch --pinentry-mode loopback --passphrase '' \
        --quick-generate-key 'Builder <builder@local>' ed25519 sign 0
fi
cd /home/builder/g1
makepkg --sign --key builder@local --noconfirm --skipchecksums
ls -la
BUILD

echo "== verify signature and install =="
PKG=$(ls /home/builder/g1/cachyos-arm64-hello-*.pkg.tar.* | grep -v '\.sig$' | head -1)
KEYID=$(sudo -u builder bash -c 'gpg --list-keys --with-colons builder@local | awk -F: "/^pub/{print \$5; exit}"')
echo "package=$PKG keyid=$KEYID"
sudo -u builder bash -c "gpg --export '$KEYID'" > /tmp/buildkey.asc
pacman-key --add /tmp/buildkey.asc
pacman-key --lsign-key "$KEYID"
sed -i 's/^LocalFileSigLevel.*/LocalFileSigLevel = Required/' /etc/pacman.conf
grep '^LocalFileSigLevel' /etc/pacman.conf
pacman -U --noconfirm "$PKG"
pacman -Qi cachyos-arm64-hello | head -6
cachyos-arm64-hello
echo G1_PASS
