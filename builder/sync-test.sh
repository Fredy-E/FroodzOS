#!/bin/bash
SYNC=/home/builder/imgroot/var/lib/pacman/sync
echo "== perms =="
stat -c "%U %G %a %n" "$SYNC" "$SYNC/cachyos-arm64.db" 2>&1
echo "== ls =="
ls -la "$SYNC" | tail -8
echo "== touch test =="
if touch "$SYNC/testfile" 2>&1; then echo TOUCH_OK; rm -f "$SYNC/testfile"; else echo TOUCH_FAIL; fi
echo "== retry sync =="
pacman --root /home/builder/imgroot --config /home/builder/imgroot/etc/pacman.conf --gpgdir /home/builder/imgroot/etc/pacman.d/gnupg -Sy 2>&1 | tail -4
echo SYNC_TEST_DONE
