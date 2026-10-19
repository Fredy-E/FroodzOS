#!/bin/bash
set -u
ROOT=/home/builder/imgroot
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory5.txt
{
echo "==XSESSIONS=="
ls -la "$ROOT/usr/share/xsessions/" 2>&1 || echo NOXSESSIONS
ls -la "$ROOT/usr/share/wayland-sessions/" 2>&1
echo "==QT base wayland=="
chroot "$ROOT" pacman -Q qt6-base 2>&1 || true
ls "$ROOT/usr/lib/qt6/plugins/platforms/" 2>&1 | head -n 30
echo "==KWin linkage logind seat=="
chroot "$ROOT" ldd /usr/bin/kwin_wayland 2>&1 | grep -i -E "seat|logind|systemd|elogind" | head -n 20 || true
echo "==live groups=="
chroot "$ROOT" id live 2>&1
grep -E "^live:|^video:|^render:|^input:|^seat" "$ROOT/etc/group" 2>&1 | head -n 20
echo "==KWIN_COMPOSE in bins/libs=="
for f in "$ROOT/usr/bin/kwin_wayland" "$ROOT"/usr/lib/libkwin*.so* "$ROOT"/usr/lib/qt6/plugins/*; do [ -e "$f" ] || continue; done
find "$ROOT/usr/lib" -maxdepth 2 -name "libkwin*" 2>/dev/null | head -n 20
echo "---strings KWIN_COMPOSE---"
grep -r -l "KWIN_COMPOSE" "$ROOT/usr/bin/kwin_wayland" 2>/dev/null && echo FOUND_BIN || echo NOTBIN
for lib in $(find "$ROOT/usr/lib" -name "libkwin*" 2>/dev/null | head -n 10); do echo "---$lib---"; strings "$lib" 2>/dev/null | grep -E "KWIN_COMPOSE|QPainter|isSoftwareRenderer|QSG_RENDER|software" | head -n 20 || true; done
echo "==KWIN_DRM in libs=="
for lib in $(find "$ROOT/usr/lib" -name "libkwin*" 2>/dev/null | head -n 10); do echo "---drmcheck $lib---"; strings "$lib" 2>/dev/null | grep -E "KWIN_DRM" | head -n 20 || echo NODRM; done
strings "$ROOT/usr/bin/kwin_wayland" 2>/dev/null | grep -E "KWIN_DRM" | head || echo NODRM_BIN
echo "==QPainter backend symbols=="
for lib in $(find "$ROOT/usr/lib" -name "libkwin*" 2>/dev/null | head -n 5); do echo "---$lib QPainter---"; strings "$lib" 2>/dev/null | grep -E "QPainter|QPaintEngine|SoftwareBackend|RenderLoop" | head -n 30 || true; done
echo "==default target=="
ls -l "$ROOT/etc/systemd/system/default.target" 2>&1 || echo NODEFAULT
ls -l "$ROOT/etc/systemd/system/display-manager.service" 2>&1 || echo NODM
ls -l "$ROOT/etc/systemd/system/graphical.target.wants/" 2>&1 | head -n 20 || true
ls -l "$ROOT/usr/lib/systemd/system/graphical.target.wants/" 2>&1 | head -n 20 || true
echo DONE5
} > "$out" 2>&1
cat "$out" 2>&1 | head -n 10
