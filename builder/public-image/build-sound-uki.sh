#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the first-entry boot image of 0.1.0-dev.4 ("dspM") from the base boot image:
#   fz-dtb-fixup.py --all-pas --sound-nodp --wsa-right-gpio13   (orphaned interconnect votes, USB PHY, DisplayPort dai-links, right speaker amp reset)
#   fz-board-touchpad.py                                        (FocalTech touchpad at I2C 0x38, interrupt TLMM GPIO 19)
# and swaps the result in as the `.dtbauto` section with build-gfx-variant-uki.py; every other section stays byte-identical (checked below).
#
#   build-sound-uki.sh <base-uki.efi> <out-uki.efi> [<workdir>]
#
# Needs dtc (dtc, fdtget, fdtput), binutils (objcopy) and python3. Writes nothing outside <workdir> and <out-uki.efi>.
set -euo pipefail
SRC=${1:?base uki}; OUT=${2:?output uki}; W=${3:-$(mktemp -d)}
H=$(cd "$(dirname "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$W"
objcopy -O binary --only-section=.dtbauto "$SRC" "$W/base.dtb"
python3 "$H/fz-dtb-fixup.py" "$W/base.dtb" "$W/pre.dtb" --all-pas --sound-nodp --wsa-right-gpio13 ${FZ_DTB_EXTRA:-}   # FZ_DTB_EXTRA: more rules, e.g. --enable-nvme (experimental, test builds only)
python3 "$H/fz-board-touchpad.py" "$W/pre.dtb" "$W/dspM.dtb"
python3 "$H/build-gfx-variant-uki.py" "$SRC" - "$OUT" "@dtb=$W/dspM.dtb"
objcopy -O binary --only-section=.dtbauto "$OUT" "$W/chk.dtb"; cmp "$W/chk.dtb" "$W/dspM.dtb" && echo "device tree in the image matches"
for s in .linux .cmdline .hwids .osrel .uname .initrd; do
  objcopy -O binary --only-section=$s "$SRC" "$W/a.bin"; objcopy -O binary --only-section=$s "$OUT" "$W/b.bin"
  cmp -s "$W/a.bin" "$W/b.bin" && echo "$s identical" || { echo "$s DIFFERS"; exit 1; }
done
sha256sum "$OUT" "$W/dspM.dtb"
