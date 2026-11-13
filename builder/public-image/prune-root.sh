#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Size reduction of the live root (sourced by build-root.sh when PRUNE=1). Removes only data that a read-only live session on the 83N3 does not use:
#   firmware for other Qualcomm chip families and older Wi-Fi generations, translations except English/Arabic/French, documentation and manual pages,
#   development headers and introspection files, and the two kernel copies in /boot (the machine boots the kernel inside the UKI).
# Licence texts (usr/share/licenses) are kept. The package database is left as it is: pacman -Qk will report the removed files as missing.
# Everything is relative to $BASE/merged and refuses to run elsewhere.
set -u
R="$BASE/merged"
[ -n "${BASE:-}" ] && [ -d "$R/usr/lib" ] && [ -f "$R/etc/os-release" ] || { echo "prune-root: not a root tree, nothing done"; return 1 2>/dev/null || exit 1; }
size_mb() { sudo du -sm "$R" 2>/dev/null | cut -f1; }
before=$(size_mb); echo "prune: tree size before ${before} MB"
# 1) firmware: keep X1E80100/X1P42100, the video decoder blobs and top-level GPU files; drop every other SoC family and old Wi-Fi generations
for d in "$R"/usr/lib/firmware/qcom/*/; do
    n=$(basename "$d")
    case "$n" in x1e80100|x1p42100|vpu) ;; *) sudo rm -rf -- "$d" ;; esac
done
sudo rm -rf -- "$R"/usr/lib/firmware/ath10k "$R"/usr/lib/firmware/ath11k "$R"/usr/lib/firmware/ath12k/QCN9274
# 2) translations: keep English, Arabic, French
if [ -d "$R/usr/share/locale" ]; then
    for d in "$R"/usr/share/locale/*/; do
        n=$(basename "$d")
        case "$n" in en|en_*|ar|ar_*|fr|fr_*) ;; *) sudo rm -rf -- "$d" ;; esac
    done
fi
# 3) documentation, manual pages, info, GTK docs
sudo rm -rf -- "$R"/usr/share/doc "$R"/usr/share/man "$R"/usr/share/info "$R"/usr/share/gtk-doc "$R"/usr/share/help
# 4) development files
sudo rm -rf -- "$R"/usr/include "$R"/usr/share/gir-1.0 "$R"/usr/share/vala "$R"/usr/lib/cmake
# 5) kernel images inside the root (the UKI carries the kernel)
sudo rm -f -- "$R"/boot/vmlinuz-froodzos-arm64.efi "$R"/boot/vmlinuz-linux-froodzos-arm64
# 6) package manager: do not bring documentation and other languages back on later installs
if ! sudo grep -q '^NoExtract' "$R/etc/pacman.conf"; then
    sudo sed -i 's#^\[options\]#[options]\nNoExtract = usr/share/doc/* usr/share/man/* usr/share/info/* usr/share/locale/*\nNoExtract = !usr/share/locale/en* !usr/share/locale/ar* !usr/share/locale/fr* !usr/share/locale/locale.alias#' "$R/etc/pacman.conf"
fi
after=$(size_mb); echo "prune: tree size after ${after} MB (saved $((before - after)) MB)"
