#!/bin/bash
# Clear partial menutest15 evidence, then run fixture + validation.
rm -f /home/builder/boot-failure-tests/qemu-v2-menutest15.fat \
      /home/builder/boot-failure-tests/qemu-v2-menutest15.fat1 \
      /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-menutest15*
ls /mnt/d/CachyOS-ARM64/testing/boot-failure/ | grep menutest15 || echo CLEARED
