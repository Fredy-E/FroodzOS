#!/bin/bash
# Clear partial log8-shell evidence (killed mid-run), keep the UKI.
rm -f /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-log8-shell.log \
      /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-log8-shell-grub.cfg \
      /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-log8-shell-result.json
ls /mnt/d/CachyOS-ARM64/testing/boot-failure/ | grep log8
