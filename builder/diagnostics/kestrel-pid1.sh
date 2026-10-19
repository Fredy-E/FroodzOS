#!/bin/sh
# SPDX-License-Identifier: MIT
# Kestrel PID1 wrapper: proves switch_root reached live userspace.
# /bin/sh (NOT /usr/bin/ash): the live root has no initramfs busybox ash;
# /bin/sh -> bash there. Never executed in the initramfs, only post-switch.
# Installed into the live overlay at latehook; runs as PID 1 after switch_root.
# Every marker goes to both /dev/console (photo-visible) and /dev/kmsg
# (USB-captured), so a silent handoff becomes a located fault instead of a gap.
echo 'KESTREL_PID1_ENTER' >/dev/console 2>/dev/null || true
echo 'KESTREL_PID1_ENTER' >/dev/kmsg 2>/dev/null || true
echo "KESTREL_PID1_CMDLINE: $(cat /proc/cmdline 2>/dev/null)" >/dev/console 2>/dev/null || true
echo "KESTREL_PID1_CMDLINE: $(cat /proc/cmdline 2>/dev/null)" >/dev/kmsg 2>/dev/null || true
ls -l /usr/bin/bash >/dev/console 2>&1 || true
if [ ! -x /usr/bin/bash ]; then
    echo 'KESTREL_PID1_BASH_MISSING' >/dev/console 2>/dev/null || true
    echo 'KESTREL_PID1_BASH_MISSING' >/dev/kmsg 2>/dev/null || true
    exec /usr/bin/bash -i
fi
echo 'KESTREL_POSTSWITCH_ALIVE' >/dev/console 2>/dev/null || true
echo 'KESTREL_POSTSWITCH_ALIVE' >/dev/kmsg 2>/dev/null || true
echo "KESTREL_POSTSWITCH_FSTYPE: $(findmnt -n -o FSTYPE / 2>/dev/null)" >/dev/console 2>/dev/null || true
echo "KESTREL_POSTSWITCH_FSTYPE: $(findmnt -n -o FSTYPE / 2>/dev/null)" >/dev/kmsg 2>/dev/null || true
echo "KESTREL_POSTSWITCH_PID1: $(cat /proc/1/comm 2>/dev/null)" >/dev/console 2>/dev/null || true
echo "KESTREL_POSTSWITCH_PID1: $(cat /proc/1/comm 2>/dev/null)" >/dev/kmsg 2>/dev/null || true
# Writable-userspace proof: lands in the same USB log dir even if the
# display freezes and the keyboard is dead. Boot ID format matches the
# log dir name (boot-<uuid>).
bid=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
if [ -n "$bid" ]; then
    echo 'KESTREL_POSTSWITCH_OK' >"/run/archiso/bootmnt/Logs/boot-$bid/04-postswitch-alive.txt" 2>/dev/null \
        && echo 'KESTREL_POSTSWITCH_FILE_WRITTEN' >/dev/kmsg 2>/dev/null || true
    echo 'KESTREL_POSTSWITCH_FILE_WRITTEN' >/dev/console 2>/dev/null || true
fi
# Input-subsystem proof without a working display: blink every keyboard LED
# twice. The owner watches the physical keyboard, not the screen.
echo 'KESTREL_LED_BLINK_START' >/dev/console 2>/dev/null || true
echo 'KESTREL_LED_BLINK_START' >/dev/kmsg 2>/dev/null || true
for led in /sys/class/leds/*::capslock /sys/class/leds/*::numlock /sys/class/leds/*::scrolllock; do
    [ -w "$led/brightness" ] || continue
    echo "KESTREL_LED_FOUND: $led" >/dev/console 2>/dev/null || true
    echo "KESTREL_LED_FOUND: $led" >/dev/kmsg 2>/dev/null || true
    i=0
    while [ "$i" -lt 2 ]; do
        echo 1 >"$led/brightness" 2>/dev/null || true
        sleep 1
        echo 0 >"$led/brightness" 2>/dev/null || true
        sleep 1
        i=$((i + 1))
    done
done
echo 'KESTREL_LED_BLINK_DONE' >/dev/console 2>/dev/null || true
echo 'KESTREL_LED_BLINK_DONE' >/dev/kmsg 2>/dev/null || true
echo 'KESTREL_PID1_EXEC_BASH' >/dev/console 2>/dev/null || true
echo 'KESTREL_PID1_EXEC_BASH' >/dev/kmsg 2>/dev/null || true
exec /usr/bin/bash -i 0</dev/console 1>/dev/console 2>/dev/console
