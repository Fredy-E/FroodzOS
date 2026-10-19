#!/bin/bash
# Parent-authorized D-space reclaim, guest side only.
# Removes ONLY superseded intermediate build dirs + caches. Keeps:
#  uki-v2-dt24 (dt24 baseline), uki-v2-dt25b (accepted), uki-v2-dt26-dt26a1 (current),
#  imgroot (live rootfs source), boot-failure-tests (all evidence/receipts/fixtures),
#  everything else under /home/builder.
set -u
cd /home/builder || exit 1
echo "--- before ---"
df -B1 / | tail -1
# 1. journal vacuum to 100M
journalctl --vacuum-size=100M --vacuum-time=7d 2>&1 | tail -1
# 2. pacman cache: drop packages not installed (keep installed versions)
pacman -Sc --noconfirm 2>&1 | tail -2
# 3. superseded uki-v2 trial build dirs (accepted/baseline/current kept)
KEEP="uki-v2-dt24 uki-v2-dt25b uki-v2-dt26-dt26a1"
for d in uki-v2-*/; do
  base="${d%/}"
  keep=0
  for k in $KEEP; do
    if [ "$base" = "$k" ]; then keep=1; break; fi
  done
  if [ "$keep" = 0 ]; then
    echo "removing superseded $base"
    rm -rf -- "$base"
  else
    echo "keeping $base"
  fi
done
echo "--- after ---"
df -B1 / | tail -1
du -sh /home/builder/uki-v2-* 2>/dev/null
