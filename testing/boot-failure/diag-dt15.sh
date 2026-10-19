#!/bin/bash
set -u
D=/home/builder/boot-failure-tests/qemu-dt15-menu8-v3-extracted/boot-6edf18d2-ce08-4c7a-b390-ed59540f08e3
echo "=== 00-status ==="
cat "$D/00-status.txt"
echo "=== 04-status tail ==="
tail -c 800 "$D/04-userspace-status.txt"
echo "=== early-kmsg head ==="
head -c 400 "$D/early-kmsg.log"; echo
echo "=== early-kmsg banner? ==="
grep -c "Linux version" "$D/early-kmsg.log" || true
echo "=== checkpoint-status ==="
cat "$D/checkpoint-status.log"
echo "=== console: STOPPED/ACTIVE ==="
grep -a -c "KESTREL_RAM_CAPTURE_STOPPED" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-dt15-menu8-v3.log || true
grep -a -c "KESTREL_RAM_CAPTURE_ACTIVE" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-dt15-menu8-v3.log || true
echo "=== console: cleanup can't-create errors? ==="
grep -a -c "can't create" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-dt15-menu8-v3.log || true
echo "=== menutest17 00-status tail ==="
tail -c 300 /home/builder/boot-failure-tests/qemu-v2-menutest17-extracted/boot-8a487d8c-6a67-4f80-9803-ec44d61893e6/00-status.txt
