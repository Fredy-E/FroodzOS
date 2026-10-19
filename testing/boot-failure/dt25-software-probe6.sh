#!/bin/bash
set -u
ROOT=/home/builder/imgroot
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory6.txt
{
echo "==KWIN_COMPOSE strings full=="
strings "$ROOT/usr/bin/kwin_wayland" 2>/dev/null | grep -E "KWIN_COMPOSE" | head -n 20
strings "$ROOT/usr/lib/libkwin.so.6.7.5" 2>/dev/null | grep -E "KWIN_COMPOSE" | head -n 20
echo "==compositingType enum strings=="
strings "$ROOT/usr/lib/libkwin.so.6.7.5" 2>/dev/null | grep -i -E "composit|QPainter|OpenGL" | head -n 60
echo "==KWIN_COMPOSE docs in man/help?=="
chroot "$ROOT" man -w kwin_wayland 2>&1 | head || true
ls "$ROOT/usr/share/man/"*"/kwin"* 2>&1 | head || true
echo "==kwin src env handling (if any local source?)"
find /home/builder/src -maxdepth 3 -name "*kwin*" 2>/dev/null | head || echo NOSRC
echo "==EGL GBM present=="
ls "$ROOT/usr/lib/libEGL"* "$ROOT/usr/lib/libGBM"* "$ROOT/usr/lib/libGLES"* 2>&1 | head -n 20
echo "==seat availability check=="
ls "$ROOT/run/seat" 2>&1 || echo NORUNSEAT
cat "$ROOT/usr/lib/udev/rules.d/"*seat* 2>&1 | head -n 30 || true
ls "$ROOT/usr/lib/udev/rules.d/" 2>&1 | grep -i -E "seat|uaccess|logind" | head
echo "==logind session files=="
ls "$ROOT/etc/systemd/logind.conf"* "$ROOT/usr/lib/systemd/logind.conf"* 2>&1 | head
cat "$ROOT/usr/lib/systemd/system/systemd-logind.service" 2>&1 | head -n 30
echo DONE6
} > "$out" 2>&1
cat "$out" 2>&1 | head -n 10
