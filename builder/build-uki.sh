#!/bin/bash
# Task 2.3 (part 2): assemble the Slim 3 UKI from built kernel + stubble (2026-10-08)
set -euo pipefail
KSRC=/home/builder/src/ksrc
STUB=/home/builder/src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a
OUT=/home/builder/uki
mkdir -p "$OUT"

test -f "$KSRC/arch/arm64/boot/Image"
test -f "$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb"
test -f "$STUB/stubble.efi"

cat > "$OUT/cmdline" <<'EOF'
clk_ignore_unused pd_ignore_unused console=tty0 quiet
EOF

python3 "$STUB/stubblify" build \
  --linux="$KSRC/arch/arm64/boot/Image" \
  --stub="$STUB/stubble.efi" \
  --hwids="$STUB/hwids/json" \
  --devicetree-auto="$KSRC/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb" \
  --cmdline=@"$OUT/cmdline" \
  --uname="7.3.0-cachyos-arm64" \
  --output="$OUT/vmlinuz.efi"

ls -la "$OUT/vmlinuz.efi"
python3 "$STUB/stubblify" inspect "$OUT/vmlinuz.efi" | head -25
echo UKI_BUILD_DONE
