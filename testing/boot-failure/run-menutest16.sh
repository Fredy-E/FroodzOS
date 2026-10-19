#!/bin/bash
# menutest16: fresh fixture + unified dt11 UKI as kestrel-live.efi, then validate.
set -e
T=/home/builder/boot-failure-tests
P=/mnt/d/CachyOS-ARM64/testing/boot-failure
python3 "$P/make-menutest-fixture.py" --tag qemu-v2-menutest16
FAT="$T/qemu-v2-menutest16.fat"
OFF=$(python3 -c "import json,subprocess; print(json.loads(subprocess.run(['sfdisk','--json','$FAT'],check=True,text=True,capture_output=True).stdout)['partitiontable']['partitions'][0]['start']*512)")
mcopy -o -i "$FAT@@$OFF" /home/builder/uki-v2-dt11/vmlinuz-live.efi ::/EFI/Linux/kestrel-live.efi
echo SWAPPED_UNIFIED_UKI
python3 "$P/run-efi-log-validation.py" --image "$FAT" --tag qemu-v2-menutest16 --systemd 2>&1 | tail -2
