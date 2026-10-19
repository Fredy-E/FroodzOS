# dt20: early USB-provider modules and a live-root shell

> Superseded on the physical USB by [dt21](dt21-usb-repeater-fix.md).
> The failed dt20 native evidence remains preserved; instructions below are historical.

## Current state

The Kingston KESTREL_A64 USB now holds **v2-dt20**. Only the UKI and GRUB menu
were changed, with physical-disk/volume identity, prestate hashes, verified
dt19 rollback backups, temporary-file flushing and post-write readback.
No formatting, partition changes, internal-disk, BCD, BIOS or boot-order changes.
**The native dt20 test still failed to enumerate external USB or mount the
live root.** The boot reached the emergency initramfs shell again.
Current comparison and recovered evidence:
[dt20 native log comparison](dt20-native-log-comparison.md).

The earlier approved rearming below was completed before that test and has
now been consumed by a new four-record capture. Current firmware slots are
occupied with boot ID `2e6c8caa-5649-4be1-a007-2cb1268df794`; recovery was
read-only and did not clear them. Another capture requires separately approved
rearming. Historical pre-test verification/instructions below are not current
empty-slot claims.

Firmware checkpoint rearming was **completed after explicit user approval**.
A fresh checked backup is retained in
`testing/boot-failure/firmware-clear-20261017T093016401Z/`.
Only KestrelBoot00..03 under the project GUID were deleted, after matching the
exact dt19 boot ID and all current raw bytes to the backup. The clear helper
verified all four absent, and a separate read-only export independently
confirmed absence. USB/RAM capture remains enabled. Earlier evidence remains
preserved in `testing/boot-failure/firmware-recovery-20261017T084552888Z/`.
No boot/security/vendor/legacy variables were changed.

## Evidence behind this candidate

Native dt19 boot `c0fede4e-027f-44a3-a71e-3d6814f9b9bd` retained four valid
checkpoints through 64.128 seconds. At the later snapshots, a600000.usb was
bound but there were two root hubs, zero external USB devices and no boot
label. a200000/a400000/a800000 were unbound. The boot-device timeout was seen.

Source/config/archive checks confirmed:

1. `CONFIG_I2C_QCOM_GENI=m`, but `i2c-qcom-geni.ko.zst` was absent from dt19's
   initramfs. PTN3222 repeater support was present, but the bus needed to
   instantiate those I2C devices was missing. The board's `i2c5` hosts the
   eusb3/eusb5/eusb6/eusb9 repeaters; usb_mp and usb_2 reference these PHYs.
2. `CONFIG_QRTR=m` and `CONFIG_QRTR_SMD=m`, but neither module was packaged.
   Built-in PMIC GLINK calls PDR -> QMI -> `sock_create_kern(AF_QIPCRTR)`.
   Missing QRTR yields `EAFNOSUPPORT`, translated to `EPROBE_DEFER` by
   `drivers/soc/qcom/qmi_interface.c:659-665`; PMIC GLINK reports this at
   `drivers/soc/qcom/pmic_glink.c:321-325`. The retry mechanism is intentional,
   but the missing provider makes the deferral persistent in this initramfs.
3. dt19's packed runtime `config` only forced `nls_iso8859_1 nls_utf8`.
   Block/kms hook discovery had not closed the board's non-storage provider
   dependencies. USB storage, UAS and USB HID support were already included.
4. Physical USB-A-to-controller wiring is not established by DT alone.
   a600000 binding does not prove the owner's USB-A port's path is working.

The separate audits also found usb_1_ss1_qmpphy disabled while its controller
requests it. That remains a possible blocker for that controller. **dt20 does
not enable this PHY, change supply assumptions or claim all ports work.**
The reset-associated gem_noc remains disabled; no kernel/DT bisect delta is
introduced in this candidate.

## Changes

- `builder/build-live-uki.sh` explicitly packs and early-loads
  `i2c-qcom-geni phy-nxp-ptn3222 qrtr qrtr-smd`, alongside the existing NLS list.
- `builder/platform_usb_gate.py` and the validator's `--require-platform-usb`
  gate independently check both archive presence and the runtime MODULES list.
- Five unit tests cover the complete set, each missing packed module, each
  missing early-load entry, hyphen/underscore aliases and malformed config.
- The old dt19 image fails the new gate as expected; retained as
  `dt19-platform-usb-red.json`. This does not retroactively invalidate its
  correctly scoped logger tests.
- #8 and #9 add `init=/usr/bin/bash` after the normal archiso live-root mount.
  They bypass the graphical login/systemd for this shell-first hardware test.
  This is not `rdinit` and is not an intentional initramfs emergency shell.
- Kernel, DTB, stub code, HWIDs, embedded cmdline, checkpoint binary and logger
  hooks are byte-identical to dt19. No new kernel build was needed.

## Exact-candidate verification

All four gates match UKI SHA256
`081b399d298addcf8665f4fbe350b7802b816e04957b78b1166d35eeebe7e09d`.

| Gate | Result | Scope |
|---|---|---|
| `dt20-artifact-audit.json` | PASS | PE inputs equal current source artifacts; non-initramfs sections unchanged; full initramfs validator; module dependency resolution |
| `dt20-logger-v2-v1-result.json` | PASS | Disposable AAVMF: flag OFF has zero records; virtual USB unplug -> real timeout -> abrupt stop -> new process recovers four CRC-valid records; existing-record boot preserves bytes |
| `qemu-dt20-menu8-shell-fw-off-v1-result.json` | PASS, 84.56 s / 360 s budget | EFI -> exact candidate -> FAT USB -> squashfs/overlay -> Bash; actual runtime modules and overlay fstype; log readback; poweroff |
| `qemu-dt20-menu8-systemd-fw-off-v1-result.json` | PASS, 270.80 s / 600 s budget | Separate fixture, firmware flag and init=Bash removed only for this regression; multi-user, userspace logging and USB log readback |

The QEMU shell test confirmed `i2c_qcom_geni`, `phy_nxp_ptn3222`, `qrtr` and
`qrtr_smd` in actual `/proc/modules`, not just file names. QEMU has none of the
Lenovo's real USB/I2C wiring: these gates prove packaging, module loading,
boot-chain and logger behavior, **not native external USB operation**.
Firmware regression modified only disposable VM pflash, not physical firmware.
The earlier failed dt18 timeout-observation evidence remains retained.

## Installed artifacts and rollback

- UKI `EFI/Linux/kestrel-live.efi`: 244442624 bytes,
  `081b399d298addcf8665f4fbe350b7802b816e04957b78b1166d35eeebe7e09d`.
- Menu `boot/grub/grub.cfg`: 6186 bytes,
  `98f701d7345e2b59042a9b8c8ce2e0a5678fab498cd2977efe6e23ed663d2278`.
- dt19 backup:
  `testing/boot-failure/usb-before-dt20-20261017T092307100Z/`.
- `Update-Dt20Usb.ps1` dry run then `-Apply`: exit 0,
  `USB_DT20_FILE_UPDATE_VERIFIED`.
- `Verify-Dt20Usb.ps1`: exit 0; re-resolved Kingston PhysicalDrive2 / FAT32 E:,
  read back changed UKI/menu plus unchanged loader/rootfs hashes and staging,
  verified 11 entries and default #8 shell/logging arguments.
- Initial pre-rearm export `dt20-preboot-20261017T092346745Z` retained the dt19
  records while approval was pending. After approval, fresh checked backup and
  scoped deletion completed with `CHECKPOINT_CLEAR_VERIFIED`.
- Latest `Verify-Dt20Usb.ps1 -RequireRearmed`: exit 0. Updated
  `usb-dt20-independent.json` reports `firmware_slots_verified_empty=true`;
  independent export `dt20-preboot-20261017T093028887Z` has all four slots
  Missing/error 203 and no boot IDs. All USB boot-critical hashes still match.
- Canonical, alternate and staging menus are synchronized with the USB.

## Next native test

Approved backup/clear/independent absence verification is complete for the
four owned slots under GUID 674b8af1-da8e-4c2b-a84c-467e2d36c97c, expected old
boot ID c0fede4e-027f-44a3-a71e-3d6814f9b9bd. `Verify-Dt20Usb.ps1 -RequireRearmed`
passed. No further clearing is needed before this one native attempt.

Owner-executed boot with the same USB-A setup, using the on-device entry:
**#8 `Kestrel dt20 - USB dependencies + LIVE ROOT SHELL (default)`**.

Acceptance, in order:

1. Real external USB device enumeration, not just usb1/usb2 root hubs.
2. KESTREL_A64 found, FAT and squashfs mounted, writable overlay created.
3. Bash on the real live root, with a working external USB keyboard.
4. If typing works, `findmnt -n -o FSTYPE /` should report `overlay`.
   Do not request commands if the keyboard still does not enumerate.
5. Do not exit Bash when it is PID 1. For shutdown use
   `/usr/bin/systemctl poweroff --force --force`, exercised by the QEMU test.
6. If still at emergency `[rootfs ~]#`, do not call it a live-root success.
   After rearming, allow ~90 seconds after kernel start for bounded checkpoint
   completion, retain the screen/markers and return to Windows for read-only
   recovery before another trial. Missing slots never prove a crash location.

If the I2C bus now binds but no external USB appears, use the new records and
USB files to decide the next PHY/power/controller change. Do not stack the
ss1 QMP change onto this candidate before the native result. All generated
firmware-bearing UKIs/rootfs remain local-only and must not be published.
