#!/bin/bash
# Phase 4: build the live rootfs for the ARM64 image (2026-10-08)
# Desktop per M1 bar: Plasma desktop, wired network, USB, safe shutdown.
# Firmware staged from THIS machine's own Windows DriverStore (local-only, ADR-5).
set -euo pipefail
# Public source derivative: do not recreate the historical shared credential.
: "${FROODZOS_LIVE_PASSWORD:?Provide a new local live-session password before any build effects}"
case "$FROODZOS_LIVE_PASSWORD" in
    live|*$'\n'*|*$'\r'*) printf '%s\n' 'Refusing the historical default or a multiline password' >&2; exit 2 ;;
esac
ROOT=/home/builder/imgroot
FW=/mnt/c/Windows/System32/DriverStore/FileRepository

echo "=== STEP 0: wire [cachyos-arm64] repo + trust on builder ==="
if ! grep -q 'cachyos-arm64' /etc/pacman.conf; then
    cat >> /etc/pacman.conf <<'EOF'

[cachyos-arm64]
SigLevel = Required DatabaseOptional
Server = file:///srv/cachyos-arm64/aarch64
EOF
fi
if ! pacman-key --list-keys "100A8D5D6E712043E283B2F0BF1F79CAB61B722F" >/dev/null 2>&1; then
    pacman-key --add /mnt/d/CachyOS-ARM64/keys/offline/master-public.asc
    pacman-key --lsign "100A8D5D6E712043E283B2F0BF1F79CAB61B722F"
fi
pacman -Sy --noconfirm

echo "=== STEP 1: pacstrap rootfs $(date --iso-8601=seconds) ==="
mkdir -p "$ROOT"
if [ ! -e "$ROOT/etc/os-release" ]; then
    pacstrap -c "$ROOT" \
        base linux-firmware linux-firmware-qcom \
        mkinitcpio \
        mesa \
        plasma-desktop sddm plasma-nm networkmanager \
        konsole dolphin firefox \
        sudo nano
else
    echo "rootfs exists, skipping pacstrap"
fi

echo "=== STEP 2: trust + install our kernel inside the target ==="
mkdir -p "$ROOT/usr/share/pacman/keyrings"
cp /usr/share/pacman/keyrings/archlinuxarm.* "$ROOT/usr/share/pacman/keyrings/" 2>/dev/null || true
arch-chroot "$ROOT" pacman-key --init
arch-chroot "$ROOT" pacman-key --populate archlinuxarm
if ! pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --list-keys "100A8D5D6E712043E283B2F0BF1F79CAB61B722F" >/dev/null 2>&1; then
    pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --add /mnt/d/CachyOS-ARM64/keys/offline/master-public.asc
    pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --lsign "100A8D5D6E712043E283B2F0BF1F79CAB61B722F"
fi
BUILD_FPR=$(gpg --homedir /home/builder/.gnupg --list-keys --with-colons 'builder@local' | awk -F: '/^fpr/{print $10; exit}')
gpg --homedir /home/builder/.gnupg --armor --export "$BUILD_FPR" > /tmp/buildkey.asc
if ! pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --list-keys "$BUILD_FPR" >/dev/null 2>&1; then
    pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --add /tmp/buildkey.asc
    pacman-key --gpgdir "$ROOT/etc/pacman.d/gnupg" --lsign "$BUILD_FPR"
fi
grep -q 'cachyos-arm64' "$ROOT/etc/pacman.conf" || cp /etc/pacman.conf "$ROOT/etc/pacman.conf"
pacman --root "$ROOT" --config "$ROOT/etc/pacman.conf" --gpgdir "$ROOT/etc/pacman.d/gnupg" \
    --cachedir /var/cache/pacman/pkg -U --noconfirm /srv/cachyos-arm64/aarch64/linux-cachyos-arm64-*.pkg.tar.xz

echo "=== STEP 3: stage local firmware (ADR-5) ==="
DEST="$ROOT/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3"
mkdir -p "$DEST"
FOUND=0
for f in qcadsp8380.mbn qccdsp8380.mbn qcdxkmsuc8380.mbn qcdxkmsucpurwa.mbn \
         adsp_dtbs.elf cdsp_dtbs.elf adspr.jsn adsps.jsn adspua.jsn battmgr.jsn; do
    path=$(find "$FW" -name "$f" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)
    if [ -n "$path" ]; then
        install -m 0644 "$path" "$DEST/$f"
        echo "STAGED $f"
        FOUND=$((FOUND+1))
    else
        echo "MISS $f"
    fi
done
echo "firmware staged: $FOUND/10 (local-only, never publish this rootfs)"

echo "=== STEP 3: live-session identity ==="
sed -i 's/^ID=.*/ID=kestrelos/; s/^NAME=.*/NAME="Kestrel OS (unofficial ARM64 port, LIVE)"/; s/^PRETTY_NAME=.*/PRETTY_NAME="Kestrel OS LIVE (unofficial CachyOS-derived ARM64 port)"/' "$ROOT/etc/os-release" 2>/dev/null || true
mkdir -p "$ROOT/etc/sddm.conf.d"
cat > "$ROOT/etc/sddm.conf.d/autologin.conf" <<'EOF'
[Autologin]
User=live
Session=plasma
EOF
arch-chroot "$ROOT" useradd -m -G wheel -s /bin/bash live 2>/dev/null || true
echo 'live ALL=(ALL) NOPASSWD: ALL' > "$ROOT/etc/sudoers.d/live"
chmod 440 "$ROOT/etc/sudoers.d/live"
printf 'live:%s\n' "$FROODZOS_LIVE_PASSWORD" | arch-chroot "$ROOT" chpasswd

echo "=== enable desktop and wired networking ==="
systemctl --root="$ROOT" enable sddm NetworkManager
systemctl --root="$ROOT" set-default graphical.target
systemctl --root="$ROOT" is-enabled sddm NetworkManager
: > "$ROOT/etc/machine-id"

echo "=== STEP 4: squashfs ==="
rm -f /home/builder/live-rootfs.squashfs
mksquashfs "$ROOT" /home/builder/live-rootfs.squashfs -comp xz -processors 4 -noappend
ls -la /home/builder/live-rootfs.squashfs
echo ROOTFS_DONE
