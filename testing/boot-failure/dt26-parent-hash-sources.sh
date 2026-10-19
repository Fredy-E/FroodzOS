#!/bin/bash
# Parent manifest hashing: exact bytes + sha256 for all 31 REQUIRED_SOURCES.
cd /mnt/d/CachyOS-ARM64 || exit 1
while IFS= read -r f; do
  if [ -f "$f" ]; then
    s=$(stat -c%s "$f")
    h=$(sha256sum "$f" | awk '{print $1}')
    printf '%s %s %s\n' "$s" "$h" "$f"
  else
    printf 'MISSING %s\n' "$f"
  fi
done <<'EOF'
builder/build-live-uki.sh
builder/validate-live-initramfs.py
builder/platform_graphics_gate.py
builder/platform_usb_gate.py
builder/platform_input_gate.py
builder/initcpio/hooks/kestrel_graphics
builder/initcpio/hooks/kestrel_text
builder/initcpio/hooks/kestrel_log
builder/initcpio/hooks/kestrel_efilog
builder/initcpio/install/kestrel_graphics
builder/initcpio/install/kestrel_text
builder/initcpio/install/kestrel_log
builder/initcpio/install/kestrel_efilog
builder/initcpio/install/kestrel_firmware
builder/initcpio/install/filesystems
builder/diagnostics/kestrel-graphics-supervisor.py
builder/diagnostics/kestrel_graphics_guard.py
builder/diagnostics/kestrel-graphics-env.conf
builder/diagnostics/kestrel-graphics-policy.json
builder/diagnostics/kestrel-graphics.service
builder/diagnostics/kestrel-graphics-sddm.service
builder/diagnostics/kestrel-graphics-tty2.conf
builder/diagnostics/kestrel-text-login.sh
builder/diagnostics/kestrel-text-proof.sh
builder/diagnostics/kestrel-text-bashrc
builder/diagnostics/kestrel-text-getty.conf
builder/diagnostics/kestrel-init-log.sh
builder/diagnostics/kestrel-root-log.sh
builder/diagnostics/kestrel-pid1.sh
builder/diagnostics/kestrel-usb-log.service
builder/diagnostics/kestrel-checkpoint.c
EOF
