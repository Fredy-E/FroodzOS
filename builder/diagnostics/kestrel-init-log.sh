#!/usr/bin/ash
# SPDX-License-Identifier: MIT
# Late-phase USB capture: runs AFTER the archiso hook has mounted the live
# USB read-only at /run/archiso/bootmnt. Uses that mount (remounted RW) so
# there is never a second competing mount of the same device.
state=/run/kestrel-capture
bootmnt=/run/archiso/bootmnt
mkdir -p "$state"
mountpoint -q "$bootmnt" || { echo 'KESTREL_USB_LOG_UNAVAILABLE: bootmnt not mounted' >/dev/console; exit 1; }
# findmnt is not in the initramfs: resolve the labelled device directly,
# falling back to the recorded mount source.
dev=$(readlink -f /dev/disk/by-label/KESTREL_A64 2>/dev/null)
if [ ! -b "$dev" ]; then
    dev=$(awk '$2 == "/run/archiso/bootmnt" {print $1}' /proc/mounts)
    dev=$(readlink -f "$dev" 2>/dev/null)
fi
[ -b "$dev" ] || { echo 'KESTREL_USB_LOG_UNAVAILABLE: bootmnt source not a block device' >/dev/console; exit 1; }
name=${dev##*/}
case "$(readlink -f "/sys/class/block/$name")" in */usb[0-9]*/*) ;; *) echo 'KESTREL_USB_LOG_REFUSED: live medium is not USB' >/dev/console; exit 1 ;; esac
[ "$(blkid -p -s LABEL -o value "$dev" 2>/dev/null)" = KESTREL_A64 ] || { echo 'KESTREL_USB_LOG_REFUSED: live medium label mismatch' >/dev/console; exit 1; }
[ "$(cat "$bootmnt/KESTREL-LOG-TARGET" 2>/dev/null)" = KESTREL_A64_USB_CAPTURE_V1 ] || { echo 'KESTREL_USB_LOG_REFUSED: capture marker missing' >/dev/console; exit 1; }
bootid=$(cat /proc/sys/kernel/random/boot_id)
[ -n "$bootid" ] || exit 1
if ! mount -o remount,rw,sync "$bootmnt"; then
    echo 'KESTREL_USB_LOG_UNAVAILABLE: bootmnt remount-rw failed' >/dev/console
    exit 1
fi
available=$(df -Pk "$bootmnt" | awk 'NR == 2 {print $4}')
case "$available" in ''|*[!0-9]*) mount -o remount,ro "$bootmnt"; exit 1 ;; esac
if [ "$available" -lt 32768 ]; then
    echo 'KESTREL_USB_LOG_REFUSED: less than 32 MiB free' >/dev/console
    mount -o remount,ro "$bootmnt"
    exit 1
fi
dest="$bootmnt/Logs/boot-$bootid"
mkdir -p "$dest" || { mount -o remount,ro "$bootmnt"; exit 1; }
printf '%s\n' "$dest" >"$state/destination"
printf '%s\n' "$dev" >"$state/device"
printf '%s\n' "$bootmnt" >"$state/bootmnt"
        {
            echo 'KESTREL_CAPTURE_STARTED latehook-via-bootmnt'
            echo "boot_id=$bootid"
            echo "device=$dev"
            echo 'cmdline:'
            cat /proc/cmdline
            echo 'kernel:'
            uname -a
            echo 'Writes limited to this USB Logs directory. No EFI/internal writes.'
        } >"$dest/00-status.txt"
        /usr/bin/kestrel-kmsg "$dest/01-kernel-kmsg.log" >"$state/streamer.stdout" 2>"$state/streamer.stderr" &
        printf '%s\n' "$!" >"$state/streamer.pid"
        sync 2>/dev/null || true
        echo "KESTREL_USB_LOG_ACTIVE: $dest" >/dev/console
        # Latehooks run after the live overlay is mounted, so record that here in the
        # observer itself rather than depending on cleanup-hook ordering.
        if mountpoint -q /sysroot 2>/dev/null; then
            printf '%s\n' 'KESTREL_OVERLAY_ROOT_READY' >>"$dest/00-status.txt"
            sync 2>/dev/null || true
        fi
        # Preserve early RAM capture without a competing pre-root USB mount.
        for early in early-kmsg.log checkpoint-status.log; do
            [ ! -f "$state/$early" ] || cp "$state/$early" "$dest/$early"
        done
        # Snapshot initramfs console output and bounded dmesg tails while streaming.
count=0
while [ ! -e "$state/stop-init" ] && [ "$count" -lt 300 ] && [ -d "$dest" ]; do
    if [ -r /run/initramfs/init.log ]; then
        cp /run/initramfs/init.log "$dest/02-initramfs-console.tmp" 2>/dev/null || true
        if [ -s "$dest/02-initramfs-console.tmp" ]; then
            mv -f "$dest/02-initramfs-console.tmp" "$dest/02-initramfs-console.log" 2>/dev/null || true
        fi
    fi
    if [ -s "$state/streamer.stderr" ]; then
        cp "$state/streamer.stderr" "$dest/09-streamer-errors.tmp" 2>/dev/null || true
        if [ -s "$dest/09-streamer-errors.tmp" ]; then
            mv -f "$dest/09-streamer-errors.tmp" "$dest/09-streamer-errors.txt" 2>/dev/null || true
        fi
    fi
    if [ $((count % 2)) -eq 0 ]; then
        {
            echo "=== dmesg snapshot sample=$count ==="
            dmesg -r 2>/dev/null | tail -c 65536
        } >>"$dest/05-dmesg-snapshots.log" 2>/dev/null
    fi
    sync 2>/dev/null || true
    count=$((count + 1))
    sleep 1
 done
# Handover to the cleanup hook: it owns the final sync (valid mount view) and
# terminates this observer, whose mount-namespace view goes stale after
# switch_root. The kmsg streamer survives; the overlay service resumes there.
sync 2>/dev/null || true
exit 0
