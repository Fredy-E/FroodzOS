#!/bin/bash
set -u
ROOT=/home/builder/imgroot
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory2.txt
{
echo "==WRAPPER file=="
file "$ROOT/usr/bin/kwin_wayland_wrapper" 2>&1
echo "==WRAPPER strings=="
strings "$ROOT/usr/bin/kwin_wayland_wrapper" 2>&1 | head -n 200
echo "==KWIN full help-all=="
chroot "$ROOT" kwin_wayland --help-all 2>&1 | head -n 300 || true
echo "==KWIN version=="
chroot "$ROOT" kwin_wayland --version 2>&1 || true
echo "==plasma-dbus-run-session-if-needed=="
cat "$ROOT/usr/lib/plasma-dbus-run-session-if-needed" 2>&1
echo "==DRI drivers=="
ls -1 "$ROOT/usr/lib/dri" 2>&1
echo "==gallium pipe drivers=="
find "$ROOT/usr/lib" -maxdepth 5 -type f -name "*.so*" 2>/dev/null | xargs -I{} basename {} 2>/dev/null | sort -u | grep -i -E "swrast|llvmpipe|lavapipe|soft|pipe" | head -n 30 || true
ls -1 "$ROOT/usr/lib/dri" 2>&1; echo "---vulkan icd---"
ls -1 "$ROOT/usr/share/vulkan/icd.d/" 2>&1 || true
cat "$ROOT/usr/share/vulkan/icd.d/"* 2>&1 | head -n 60 || true
echo "==Mesa strings LP_NUM_THREADS=="
for f in "$ROOT/usr/lib/dri/swrast_dri.so" "$ROOT/usr/lib/dri/kms_swrast_dri.so" "$ROOT/usr/lib/libGLESv2.so"* "$ROOT/usr/lib/libGLX_mesa.so"*; do
  [ -e "$f" ] || continue
  echo "--- $f ---"
  strings "$f" 2>/dev/null | grep -E "LP_NUM_THREADS|GALLIUM_THREAD|LIBGL_ALWAYS_SOFTWARE|GALLIUM_DRIVER" | head -n 20 || true
done
echo "==LP strings in libgallium=="
find "$ROOT/usr/lib" -name "*gallium*" 2>/dev/null | head
strings "$ROOT/usr/lib/dri/swrast_dri.so" 2>/dev/null | grep -i -E "num_thread|thread|llvmpipe|lavapipe" | head -n 30 || true
echo "==Xwayland help=="
chroot "$ROOT" Xwayland -help 2>&1 | head -n 40 || true
echo "==sddm pam=="
cat "$ROOT/etc/pam.d/sddm-autologin" 2>&1
cat "$ROOT/etc/pam.d/sddm" 2>&1 | head -n 40 || true
echo "==sddm service full=="
cat "$ROOT/usr/lib/systemd/system/sddm.service" 2>&1
echo "==getty service=="
cat "$ROOT/usr/lib/systemd/system/getty@.service" 2>&1 | head -n 60
echo "==live user=="
grep -E "^live:" "$ROOT/etc/passwd" 2>&1
grep -E "^live:" "$ROOT/etc/group" 2>&1 || true
chroot "$ROOT" id live 2>&1 || true
echo "==modprobe=="
ls -1 "$ROOT/etc/modprobe.d/" 2>&1
cat "$ROOT/etc/modprobe.d/"* 2>&1 | head -n 80 || true
ls -1 "$ROOT/usr/lib/modprobe.d/" 2>&1
cat "$ROOT/usr/lib/modprobe.d/"* 2>&1 | head -n 120 || true
echo "==cmdline / kernel config=="
grep -E "CONFIG_DRM_SIMPLEDRM|CONFIG_DRM_MSM|CONFIG_QCOM_TSENS|CONFIG_THERMAL=|CONFIG_HWMON|CONFIG_FRAMEBUFFER_CONSOLE|CONFIG_FB_SIMPLE|CONFIG_SYSFB" "$K/.config" 2>&1 || /home/builder/src/ksrc/.config 2>&1 || true
grep -E "CONFIG_DRM_SIMPLEDRM|CONFIG_DRM_MSM" /home/builder/src/ksrc/.config 2>&1 | head || true
echo DONE2
} > "$out" 2>&1
echo "wrote $out"
cat "$out" 2>&1 | head -n 20
