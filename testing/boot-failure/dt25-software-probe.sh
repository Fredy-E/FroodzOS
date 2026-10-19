#!/bin/bash
set -u
ROOT=/home/builder/imgroot
K=/home/builder/src/ksrc
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory-raw.txt
{
echo "=== BINARIES ==="
for n in kwin_wayland kwin_wayland_wrapper startplasma-wayland dbus-run-session sddm python3 systemd-run timeout login cage weston Xwayland; do
  p="$ROOT/usr/bin/$n"
  if [ -e "$p" ]; then echo "EXISTS usr/bin/$n"; ls -l "$p"; else echo "ABSENT usr/bin/$n"; fi
done
for n in plasma-dbus-run-session-if-needed kwin_wayland_wrapper; do
  for d in usr/bin usr/lib; do
    if [ -e "$ROOT/$d/$n" ]; then echo "EXISTS $d/$n"; ls -l "$ROOT/$d/$n"; fi
  done
done
echo "=== PACKAGES ==="
chroot "$ROOT" pacman -Q kwin plasma-workspace mesa sddm python systemd qt6-declarative libseat seatd elogind 2>&1 || true
echo "=== FILES ==="
for rel in usr/lib/systemd/system/sddm.service usr/share/wayland-sessions/plasma.desktop etc/sddm.conf etc/sddm.conf.d/autologin.conf usr/lib/systemd/user/plasma-kwin_wayland.service etc/sddm.conf.d/kde_settings.conf usr/lib/sddm/sddm.conf.d/00default.conf; do
  echo "---FILE $rel---"
  if [ -f "$ROOT/$rel" ]; then cat "$ROOT/$rel"; echo; else echo ABSENT; fi
done
echo "--- startplasma-wayland head ---"
if [ -f "$ROOT/usr/bin/startplasma-wayland" ]; then head -n 100 "$ROOT/usr/bin/startplasma-wayland"; echo; fi
echo "--- kwin_wayland_wrapper cat ---"
if [ -f "$ROOT/usr/bin/kwin_wayland_wrapper" ]; then cat "$ROOT/usr/bin/kwin_wayland_wrapper"; echo; ls -l "$ROOT/usr/bin/kwin_wayland_wrapper"; fi
echo "=== KWIN HELP ==="
chroot "$ROOT" kwin_wayland --help 2>&1 | head -n 120 || true
echo "=== KWIN strings render/backends ==="
strings "$ROOT/usr/bin/kwin_wayland" 2>/dev/null | grep -i -E "software|swrast|llvmpipe|lavapipe|LIBGL_|GALLIUM_|QT_QPA|KWIN_|WLR_|EGL_PLATFORM|surfaceless|gbm|drm" | head -n 100 || true
echo "=== MESA drivers present ==="
ls "$ROOT/usr/lib/dri/" 2>&1 | head -n 50
find "$ROOT/usr/lib" -maxdepth 4 -name "*swrast*" -o -name "*lavapipe*" -o -name "*llvmpipe*" 2>/dev/null | head -n 30
echo "=== EGL platforms ==="
find "$ROOT/usr" -name "*egl*surfaceless*" -o -name "libEGL*" 2>/dev/null | head -n 20
echo "=== passwd live entry (no shadow) ==="
grep -E "^(live|root):" "$ROOT/etc/passwd" 2>&1 || true
id live 2>&1 || chroot "$ROOT" id live 2>&1 || true
echo "=== loginctl/seat files ==="
ls "$ROOT/usr/lib/systemd/system/" 2>&1 | grep -E "logind|seatd|sddm|getty|graphical|multi-user" | head -n 30
cat "$ROOT/usr/lib/systemd/system/sddm.service" 2>&1
echo "=== modprobe blacklists ==="
cat "$ROOT/etc/modprobe.d/"* 2>&1 | head -n 100; echo "---"
find "$ROOT" -path "*modprobe.d*" -type f 2>/dev/null | head
echo "=== kernel cmdline artifacts ==="
cat /home/builder/uki-v2-dt24/live-cmdline.txt 2>&1 || cat /home/builder/boot-failure-tests/dt25-baseline/kernel-cmdline.txt 2>&1 || echo NOCMDLINE
echo "=== KERNEL CONFIG ==="
grep -E "CONFIG_DRM_SIMPLEDRM=|CONFIG_DRM_MSM=|CONFIG_QCOM_TSENS=|CONFIG_THERMAL=|CONFIG_HWMON=|CONFIG_FRAMEBUFFER_CONSOLE=|CONFIG_DRM_FBDEV|CONFIG_FB_SIMPLE|CONFIG_SYSFB_SIMPLEFB=" "$K/.config" 2>&1 || true
echo "=== PAM sddm-autologin (public only) ==="
cat "$ROOT/etc/pam.d/sddm-autologin" 2>&1 || true
echo "=== SDDM state dir ==="
ls -la "$ROOT/var/lib/sddm/" 2>&1 || true
echo DONE
} | tee "$out" 2>&1
echo "WROTE $out"
