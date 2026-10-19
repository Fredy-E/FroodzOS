# dt21: repair the USB repeater I2C5 dependency chain

## Scope and current status

The owner requested continued autonomous repair, not another unchanged boot.
**dt21 is installed on the physical Kingston USB and independently verified.**
Artifact, compiled-DT, initramfs, full EFI/live-root shell, systemd and
no-USB disposable-firmware tests all passed for the same exact candidate hash.
Before installation, the previous native evidence was freshly backed up and
only the four owned checkpoint slots were cleared; readback confirmed them empty.
**Native dt21 now enumerates the Kingston stick, mounts the live source and
reaches the overlay-ready / switch-root-pending stage.** A responsive Bash
prompt, actual keyboard input and native systemd/Plasma remain unverified.
See [native dt21 recovery](dt21-native-usb-success.md). The dt21 native evidence
is preserved in `firmware-clear-20261017T111017185Z/`; all four slots were
then rearmed empty and independently verified (`dt21-preboot-20261017T111050612Z/`).

This candidate addresses the bus feeding the four existing PTN3222 repeaters.
It does not change connector wiring, PHY supply voltages, USB speed, kernel
code, display/GPU settings, or re-enable the reset-associated GEM NoC.

## Root dependency verified from the active source and compiled DT

- `hamoa.dtsi:2538-2572`: I2C5 (`/soc@0/geniqup@bc0000/i2c@b94000`)
  requests qup-core, qup-config and qup-memory ICC paths. qup-config directly
  names disabled gem_noc; the DDR route is also severed by that disable.
- `drivers/soc/qcom/qcom-geni-se.c:923-951,1196-1225` mandates successful
  ICC acquisition before `geni_i2c_probe` can create the I2C adapter. Merely
  packaging i2c-qcom-geni in dt20 could not repair this DT supplier chain.
- The board I2C5 children are PTN3222 repeaters at 0x43/0x47/0x4b/0x4f.
  usb_2, usb_mp and usb_1_ss1 reference these through their HS PHYs. The
  only controller bound in dt20, a600000, uses a separate SPMI repeater.
- I2C5's dmas property names existing gpi_dma0 channel 5. That provider was
  disabled in the compiled DT and its modular `gpi` driver was not packed.
  `setup_gpi_dma` requests it when hardware reports FIFO disabled; this mode
  has not been observed directly on this laptop. GPI closure is supplied
  defensively rather than claiming FIFO-disabled hardware has been proven.
- `drivers/interconnect/core.c:591-592` returns NULL when interconnects is
  absent. GENI stores the NULL paths; ICC bandwidth/enable APIs explicitly
  accept NULL. This permits a local diagnostic no-vote path without altering
  generic driver behavior or enabling the known reset-associated provider.

## Applied delta

Numbered standard unified patch:
`pkgs/linux-cachyos-arm64/patches/0018-diagnostic-usb-i2c5-dependencies.patch`.
It applies after the existing diagnostic series, not directly to pristine
upstream. Forward application and reverse reproduction of the exact saved
baseline both passed. This does not retroactively fix reproducibility of
older abbreviated diagnostic patch records.

1. Board `&i2c5`: delete only interconnects/interconnect-names.
2. Board `&gpi_dma0`: enable the existing provider with unchanged channel mask,
   interrupts and IOMMU stream mapping.
3. Canonical initramfs MODULES: add `gpi` before the already included GENI I2C,
   PTN3222 and QRTR modules. Both packed presence and forced early loading
   are required by the regression gate; actual loading is checked in QEMU.

Decompiled DT comparison proves all content outside these three properties
is unchanged. GEM, GPU, GMU and MDSS remain disabled. Kernel Image, boot stub,
HWIDs, embedded cmdline, bounded checkpoint executable and logger hooks remain
byte-identical to dt20. No firmware write limits, triggers or deadlines changed.
The early logger starts before forced module loading in mkinitcpio's /init.

No-vote operation is diagnostic, not a production safety/performance claim.
Physical port-to-controller mapping, real FIFO/DMA mode, regulator behavior
and any additional supplier problems remain hardware acceptance questions.
The unrelated ss1 QMP disable remains for a separate evidence-driven step.

## Regression and evidence

- `dt20-board-dependency-red.json`: old DT fails the ICC/GPI dependency gate.
- `dt20-gpi-module-red.json`: old initramfs fails GPI packed/early-load checks.
- `dt21-board-dependency-green.json`: all board dependency predicates pass.
- `dt21-dtb-build-result.json`: only the allowed three compiled properties
  differ; Image unchanged; patch forward/reverse verified.
- Five platform gate unit test methods pass, including removal of each
  packed/early-load provider independently.
- `dt21-artifact-audit.json`: exact PE inputs, platform modules, dependency
  resolution, local firmware, correct live PID 1 and existing logger verified.
- Initial patch dry run rejected malformed EOF framing from a line-numbered
  readback. No source was changed by that failed attempt. Regenerated from
  actual file bytes; current patch passed forward and reverse checks. The
  initial `dt21-board-build` snapshot and successful `dt21-board-build-v2`
  snapshot are retained, not silently reclassified as the same run.

Candidate UKI: 244480512 bytes, SHA256
`a1ced156e198be71a586aa6283a86edc251ddb147a3564c28ed2b5ddcd92a75c`.
DTB: 207916 bytes, SHA256
`9a4be4a7d716516960e574c16e4a0c9d4d51f78317ec00ffd176f7aef26c32e6`.
Menu: 6195 bytes, SHA256
`2dd7a70d6853664c628cab5d00c2444a321cd54254b2b0f8f2fb07e1fc5b7cfb`.

## Independent review disposition

The active-source I2C audit independently identified the same disabled GEM
reference as the primary blocker; it classifies GPI as conditional on hardware
mode. A second review suggested USB2-only fallback but did not read the live
kernel tree and incorrectly inferred a working I2C adapter from module presence.
That fallback is not stacked onto dt21. Its `input_errno=0` statement is not
HID evidence: this logger field tracks /dev/kmsg input errors, not keyboard
operation. The PMIC device-link warning is not treated as a proven cause.

## Validation/install handoff (completed)

All four gates match the candidate UKI hash above:
- `dt21-artifact-audit.json`: PASS; same kernel/stub/logger, correct changed DT.
- `dt21-logger-v2-v1-result.json`: PASS; flag OFF zero records, virtual USB
  removal -> timeout -> abrupt stop -> new process recovers four valid slots;
  existing-record reboot disarms and preserves the bytes. No physical firmware
  writes were made by this VM test.
- `qemu-dt21-menu8-shell-fw-off-v1-result.json`: PASS, 104.96 s within the
  declared 360 s budget. Actual runtime gpi/GENI/PTN3222/QRTR modules, USB-backed
  overlay root, captured file logs and poweroff verified.
- `qemu-dt21-menu8-systemd-fw-off-v1-result.json`: PASS, 330.34 s within the
  declared 600 s budget; actual multi-user and userspace log readback. Only
  firmware flag and init=Bash were removed for this separate regression.

`Update-Dt21Usb.ps1` passed dry run then -Apply with
`USB_DT21_FILE_UPDATE_VERIFIED`. `Verify-Dt21Usb.ps1 -RequireRearmed` passed
independently. Both resolve the physical Kingston/KESTREL_A64 FAT32 association,
not just a drive letter; readback includes changed UKI/menu and unchanged
loader/rootfs. Staging and canonical/alternate menus are synchronized.
No format, partition table, internal-disk, boot-order or boot-security changes.
Kali remains listed and stopped; the dedicated builder is also stopped.

- dt20 rollback: `testing/boot-failure/usb-before-dt21-20261017T104348959Z/`.
- Fresh native evidence backup before deletion:
  `testing/boot-failure/firmware-clear-20261017T104420408Z/`.
- Deleted only KestrelBoot00..03 under the project GUID after boot-ID and
  byte/hash checks matched `2e6c8caa-5649-4be1-a007-2cb1268df794`.
- Independent absence readback:
  `testing/boot-failure/dt21-preboot-20261017T104433740Z/`.
  All four slots Missing/error 203, no boot IDs.
- Final aggregate also verified all four archived raw record hashes and exact
  cleared-name set. Old dt20 evidence remains intact in earlier archives.
- Firmware boot/security/vendor/legacy variables were not touched.

Next owner-executed boot: **#8 `Kestrel dt22 - PID1-marked live shell (default)`**,
read back from the on-device menu. Superseded by dt22 (same USB stack plus
switch_root handoff markers); dt22 is installed and rearmed, see
[native dt22 handoff fix](dt22-pid1-handoff-fix.md). The criterion is
external USB enumeration, KESTREL_A64 mounted, then Bash on overlay root with
working USB input. If typing works, `findmnt -n -o FSTYPE /` should say overlay.
Do not exit PID 1 Bash; use `/usr/bin/systemctl poweroff --force --force`.
If still at emergency `[rootfs ~]#`, leave about 90 seconds after kernel start
for bounded capture, retain screen/markers and return to Windows for recovery.
The emergency shell does not satisfy live-root acceptance. QEMU passes only
validate tooling/boot chain, not Lenovo I2C/DMA/PHY hardware. All firmware-bearing
images remain local-only.
