#!/bin/bash
# Remove regenerable QEMU fixtures + pacman cache (evidence JSONs/logs stay).
rm -f /home/builder/boot-failure-tests/*.fat /home/builder/boot-failure-tests/*.fat1
pacman -Sc --noconfirm 2>&1 | tail -1
df -h / | tail -1
du -x -sh /home/builder/boot-failure-tests
