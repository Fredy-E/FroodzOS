#!/bin/bash
# Hash the v2-dt2 UKI and report the current USB plain-UKI hash (prestate).
sha256sum /home/builder/uki-v2-dt2/vmlinuz-live.efi
ls -l /home/builder/uki-v2-dt2/vmlinuz-live.efi
python3 -c "import hashlib; print(hashlib.sha256(open('/mnt/d/CachyOS-ARM64/live-staging-v2/EFI/Linux/kestrel-live.efi','rb').read()).hexdigest(), 'STAGED_PRESTATE')"
