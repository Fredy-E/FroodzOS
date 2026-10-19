#!/bin/bash
# Swap unified dt11 UKI into an existing menutest fixture, clear its
# result, and re-run validation.
set -e
TAG=qemu-v2-menutest17
T=/home/builder/boot-failure-tests
P=/mnt/d/CachyOS-ARM64/testing/boot-failure
rm -f "$P/$TAG-result.json" "$P/$TAG.log" "$P/$TAG-grub.cfg"
OFF=$(python3 -c "import json,subprocess; print(json.loads(subprocess.run(['sfdisk','--json','$T/$TAG.fat'],check=True,text=True,capture_output=True).stdout)['partitiontable']['partitions'][0]['start']*512)")
mcopy -o -i "$T/$TAG.fat@@$OFF" /home/builder/uki-v2-dt11/vmlinuz-live.efi ::/EFI/Linux/kestrel-live.efi
echo SWAPPED
python3 "$P/run-efi-log-validation.py" --image "$T/$TAG.fat" --tag "$TAG" --systemd 2>&1 | tail -2
