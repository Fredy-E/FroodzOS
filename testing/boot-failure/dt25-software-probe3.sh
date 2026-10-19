#!/bin/bash
set -u
ROOT=/home/builder/imgroot
KSRC=/home/builder/src/ksrc
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory3.txt
{
echo "==VULKAN=="
ls -R "$ROOT/usr/share/vulkan" 2>&1 | head -n 30
for f in "$ROOT"/usr/share/vulkan/icd.d/*; do [ -f "$f" ] && { echo "---$f---"; cat "$f"; }; done 2>&1 | head -n 80
echo "==LP THREADS in dri=="
strings "$ROOT/usr/lib/dri/swrast_dri.so" 2>/dev/null | grep -i -E "LP_NUM|THREAD|GALLIUM" | head -n 30 || echo NOSTRING
echo "==libgallium strings=="
strings "$ROOT/usr/lib/libgallium-26.2.4-arch1.1.so" 2>/dev/null | grep -E "LP_NUM_THREADS|LIBGL_ALWAYS|GALLIUM_DRIVER|lvp_|llvmpipe" | head -n 30 || echo NOGALLIUMSTR
echo "==all mesa env strings=="
strings "$ROOT/usr/lib/libGLX_mesa.so.0.0.0" 2>/dev/null | grep -E "LIBGL_|GALLIUM_|LP_" | head -n 30 || true
echo "==QT quick backends present=="
ls "$ROOT/usr/lib/qt6/plugins/scenegraph/" 2>&1 | head -n 20 || true
ls "$ROOT/usr/plugins/scenegraph/" 2>&1 | head || true
find "$ROOT/usr" -name "*software*" -path "*qt*" 2>/dev/null | head -n 20 || true
echo "==QT QSG strings in kwin=="
strings "$ROOT/usr/bin/kwin_wayland" 2>/dev/null | grep -E "QSG_|QT_QUICK|QT_QPA|softwarecontext|basic " | head -n 30 || true
echo "==kwin env docs strings=="
strings "$ROOT/usr/bin/kwin_wayland" 2>/dev/null | grep -i -E "KWIN_|EGL|GBM|surfaceless|swrast|llvmpipe|software" | head -n 60 || true
echo "==KERNEL CONFIG=="
grep -E "CONFIG_DRM_SIMPLEDRM|CONFIG_DRM_MSM|CONFIG_QCOM_TSENS|CONFIG_THERMAL=|CONFIG_HWMON|CONFIG_FRAMEBUFFER_CONSOLE|CONFIG_FB_SIMPLE|CONFIG_SYSFB_SIMPLEFB|CONFIG_DRM_FBDEV" "$KSRC/.config" 2>&1 | head -n 20
echo "==BLACKLIST cmdline=="
cat /home/builder/uki-v2-dt24/live-cmdline.txt 2>&1 | tr ' ' '\n' | head -n 60 || true
echo "---build-live-uki cmdline---"
grep -n -E "cmdline|modprobe|blacklist|dispcc|simpledrm|msm|GEM|MDSS|GPU" /mnt/d/CachyOS-ARM64/builder/build-live-uki.sh 2>&1 | head -n 60
cat /mnt/d/CachyOS-ARM64/builder/build-live-uki.sh 2>&1 | head -n 200
echo "==validate initramfs=="
cat /mnt/d/CachyOS-ARM64/builder/validate-live-initramfs.py 2>&1 | head -n 120
echo "==THERMAL worker policy?=="
ls /mnt/d/CachyOS-ARM64/builder/diagnostics/ 2>&1
echo DONE3
} > "$out" 2>&1
cat "$out" 2>&1 | head -n 10
