#!/bin/bash
set -u
X=/home/builder/boot-failure-tests/qemu-dt14-menu8-v2-extracted
D=$(ls -d "$X"/boot-* 2>/dev/null | head -1)
echo "=== dir: $D ==="
echo "--- checkpoint-status.log ---"
cat "$D/checkpoint-status.log" 2>&1
echo "--- early-kmsg.log head (300B) ---"
head -c 300 "$D/early-kmsg.log" 2>&1; echo
echo "--- early-kmsg for Linux version? ---"
grep -c "Linux version" "$D/early-kmsg.log" 2>&1 || true
echo "--- early-kmsg tail (300B) ---"
tail -c 300 "$D/early-kmsg.log" 2>&1; echo
echo "=== menutest17 baseline: can't create errors? ==="
grep -c "can't create" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-menutest17.log 2>&1 || true
echo "=== menutest17 stop reason/passed ==="
python3 -c "import json; r=json.load(open('/mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-menutest17-result.json')); print('stop:',r.get('stop_reason'),'sec:',r.get('seconds'),'passed:',r.get('passed'))"
echo "=== dt14 log: multi-user reached? ==="
grep -c "Reached target.*Multi-User" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-dt14-menu8-v2.log 2>&1 || true
echo "=== dt14 log: checkpoint lines ==="
grep -a "KESTREL_RAM_CAPTURE\|KESTREL_FW" /mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-dt14-menu8-v2.log 2>&1 | head -5 || true
