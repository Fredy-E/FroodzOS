#!/bin/bash
set -u
echo "=== uki-v2-dt14 ==="
ls -la /home/builder/uki-v2-dt14/ 2>&1
echo "=== sha/size ==="
sha256sum /home/builder/uki-v2-dt14/vmlinuz-live.efi 2>&1
stat -c %s /home/builder/uki-v2-dt14/vmlinuz-live.efi 2>&1
stat -c %s /home/builder/uki-v2-dt14/initramfs-live.img 2>&1 || stat -c %s /home/builder/uki-v2-dt14/live-initramfs.img 2>&1 || ls -la /home/builder/uki-v2-dt14/*.img 2>&1
echo "=== initramfs content ==="
lsinitcpio -l /home/builder/uki-v2-dt14/initramfs-live.img 2>/dev/null | grep -E "kestrel-checkpoint|kestrel-efilog|kestrel_log|kestrel_efilog" || lsinitcpio -l /home/builder/uki-v2-dt14/live-initramfs.img 2>/dev/null | grep -E "kestrel-checkpoint|kestrel-efilog|kestrel_log|kestrel_efilog"
echo "=== fixtures ==="
ls -la /home/builder/boot-failure-tests/ 2>&1 | grep -E "dt14|menu8" || echo "no dt14 fixtures"
echo "=== D: results ==="
ls -la /mnt/d/CachyOS-ARM64/testing/boot-failure/ 2>&1 | grep -E "dt14|menu8|checkpoint" || echo "none"
