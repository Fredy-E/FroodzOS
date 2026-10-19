#!/bin/bash
# G2 smoke boot + G0b runtime proof: boot our Image under qemu-system-aarch64
# -cpu cortex-a53 (ARMv8-A) with a minimal static init (2026-10-08).
set -euo pipefail
WORK=/home/builder/smoke
mkdir -p "$WORK"
cd "$WORK"

cat > init.c <<'EOF'
#include <stdio.h>
#include <sys/reboot.h>
#include <sys/utsname.h>
#include <unistd.h>
int main(void) {
    struct utsname u;
    uname(&u);
    printf("SMOKE_OK uname=%s %s %s\n", u.sysname, u.release, u.machine);
    fflush(stdout);
    sync();
    reboot(RB_POWER_OFF);
    return 0;
}
EOF
gcc -static -O2 -o init init.c
mkdir -p initrd-root
cp init initrd-root/
( cd initrd-root && echo init | cpio -o -H newc 2>/dev/null | gzip > ../smoke-initramfs.cpio.gz )
ls -la smoke-initramfs.cpio.gz init

echo "=== QEMU smoke (cortex-a53, ARMv8-A) ==="
timeout 120 qemu-system-aarch64 \
    -M virt -cpu cortex-a53 -m 2048 -smp 2 \
    -kernel /home/builder/src/ksrc/arch/arm64/boot/Image \
    -initrd "$WORK/smoke-initramfs.cpio.gz" \
    -append "console=ttyAMA0 rdinit=/init" \
    -nographic -no-reboot 2>&1 | tail -25
echo "=== QEMU exit: $? ==="
echo SMOKE_DONE
