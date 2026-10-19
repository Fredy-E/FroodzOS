#!/bin/bash
# Phase 4: live initramfs (mkinitcpio-archiso) + final live UKI (2026-10-08)
set -euo pipefail
KSRC=/home/builder/src/ksrc
STUB=/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a
OUT=${OUT:-/home/builder/uki}
ROOT=${ROOT:-/home/builder/imgroot}
PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$OUT/install"
install -m 0755 "$PROJECT/builder/initcpio/install/filesystems" "$OUT/install/filesystems"
install -m 0755 "$PROJECT/builder/initcpio/install/kestrel_firmware" "$OUT/install/kestrel_firmware"

cat > "$OUT/live-mkinitcpio.conf" <<'EOF'
# Board USB repeaters sit on GENI I2C and must be reachable before USB root.
# QRTR supplies AF_QIPCRTR to the built-in PMIC GLINK/PDR client. Do not rely
# on block/kms hooks to discover these non-storage provider dependencies.
MODULES=(nls_iso8859_1 nls_utf8 gpi i2c-qcom-geni phy-nxp-ptn3222 qrtr qrtr-smd i2c-hid i2c-hid-of hid-generic)
BINARIES=()
FILES=()
HOOKS=(base udev archiso modconf kestrel_firmware kms block filesystems keyboard)
COMPRESSION="xz"
COMPRESSION_OPTIONS=(-6 -T2)
EOF

# Unified capture: the kestrel_log hook ships in every UKI. It is fully
# inert without kestrel_log=1 on the kernel cmdline (both run_latehook
# and run_cleanuphook return immediately), so default entries boot
# byte-identically with or without it.
install -m 0755 "$PROJECT/builder/initcpio/install/kestrel_log" "$OUT/install/kestrel_log"
mkdir -p "$OUT/hooks"
install -m 0755 "$PROJECT/builder/initcpio/hooks/kestrel_log" "$OUT/hooks/kestrel_log"
sed -i 's/^HOOKS=(base udev archiso modconf kestrel_firmware /HOOKS=(base udev archiso modconf kestrel_firmware kestrel_log /' "$OUT/live-mkinitcpio.conf"

# Early RAM capture and separately opt-in bounded EFI checkpoints.
# Compile from current source; never reuse an unverified stale executable.
gcc -static -O2 -Wall -Wextra -Werror "$PROJECT/builder/diagnostics/kestrel-checkpoint.c" -o "$OUT/kestrel-checkpoint"
install -m 0755 "$PROJECT/builder/initcpio/install/kestrel_efilog" "$OUT/install/kestrel_efilog"
install -m 0755 "$PROJECT/builder/initcpio/hooks/kestrel_efilog" "$OUT/hooks/kestrel_efilog"
sed -i 's/^HOOKS=(base udev archiso modconf kestrel_firmware kestrel_log /HOOKS=(base udev archiso modconf kestrel_firmware kestrel_efilog kestrel_log /' "$OUT/live-mkinitcpio.conf"

# An independent opt-in hook stages a standard systemd/getty text console
# into the writable live overlay. Logger lifecycle and firmware code stay intact.
install -m 0755 "$PROJECT/builder/initcpio/install/kestrel_text" "$OUT/install/kestrel_text"
install -m 0755 "$PROJECT/builder/initcpio/hooks/kestrel_text" "$OUT/hooks/kestrel_text"
sed -i 's/kestrel_efilog kestrel_log /kestrel_efilog kestrel_log kestrel_text /' "$OUT/live-mkinitcpio.conf"

# An independent inert hook stages opt-in simpledrm/software-Plasma helpers
# into the writable live overlay AFTER the text console. Uses existing
# initcpio install/hooks paths; text/logger/firmware behavior unchanged.
install -m 0755 "$PROJECT/builder/initcpio/install/kestrel_graphics" "$OUT/install/kestrel_graphics"
install -m 0755 "$PROJECT/builder/initcpio/hooks/kestrel_graphics" "$OUT/hooks/kestrel_graphics"
sed -i 's/kestrel_efilog kestrel_log kestrel_text /kestrel_efilog kestrel_log kestrel_text kestrel_graphics /' "$OUT/live-mkinitcpio.conf"

echo "=== live initramfs ==="
env -i HOME=/root PATH=/usr/bin:/bin LC_ALL=C.UTF-8 \
    MKINITCPIO_INSTALL="$OUT/install:/usr/lib/initcpio/install" \
    MKINITCPIO_HOOKS="$OUT/hooks:/usr/lib/initcpio/hooks" \
    KESTREL_ROOTFS="$ROOT" \
    KESTREL_PROJECT="${KESTREL_PROJECT:-$PROJECT}" \
    KESTREL_LOG_BINARY="${KESTREL_LOG_BINARY:-/home/builder/diag/kestrel-kmsg}" \
    KESTREL_CHECKPOINT_BINARY="$OUT/kestrel-checkpoint" \
    KESTREL_LOG="${KESTREL_LOG:-0}" \
    mkinitcpio --nopost -k 7.3.0-rc3 -c "$OUT/live-mkinitcpio.conf" -g "$OUT/live-initramfs.img"
python3 "$PROJECT/builder/validate-live-initramfs.py" "$OUT/live-initramfs.img" --require-local-firmware --require-log-capture --require-platform-usb --require-platform-input --require-graphics
ls -la "$OUT/live-initramfs.img"

echo "=== live UKI ==="
cat > "$OUT/live-cmdline" <<'EOF'
archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M clk_ignore_unused pd_ignore_unused efi-pstore.pstore_disable=1 console=tty0 debug loglevel=7 ignore_loglevel panic=0
EOF
python3 "$STUB/stubblify" build \
  --linux="$KSRC/arch/arm64/boot/Image" \
  --stub="$STUB/stubble.efi" \
  --hwids="$STUB/hwids/json" \
  --devicetree-auto="$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb" \
  --initrd="$OUT/live-initramfs.img" \
  --cmdline=@"$OUT/live-cmdline" \
  --uname="7.3.0-rc3" \
  --output="$OUT/vmlinuz-live.efi"

ls -la "$OUT/vmlinuz-live.efi"
python3 "$STUB/stubblify" inspect "$OUT/vmlinuz-live.efi" | grep -E "^\.|size:" | head -12
echo LIVE_UKI_DONE
