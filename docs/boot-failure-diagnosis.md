# Native boot failure: reproduced defects and correction

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


> Research and next repair: [native console/input research](research/native-console-next-step-20261017.md) — compiled keyboard supplier/module defects; research basis for the implemented dt24 candidate below.
> Current native result: [dt24 interactive native text boot PASSED](dt24-native-text-success.md) — systemd PID1, live overlay, tty1 Bash and typed-command proof recovered; startup reported 40.786 seconds.
> Current build: [dt24 keyboard repair + systemd text](dt24-systemd-text-repair.md). [Project progress](project-progress.md). Plasma and full peripheral/power acceptance remain open.
> Previous failed native attempt: [dt20 screen/checkpoint comparison](dt20-native-log-comparison.md).
> Logger repair and native evidence: [logger-v2-repair.md](logger-v2-repair.md).
> Historical sections below include superseded hypotheses. Native dt24 now boots
> the USB-backed live root into running systemd and an interactive tty1 session.
> The next major milestone is native graphics/Plasma, with thermal and remaining
> hardware dependencies still to be validated. Do not repeat old failed entries unchanged.

## Hardware evidence
The owner reported three identical failed attempts: a dash on a blank screen, followed by a restart within seconds. No loader menu/text or live desktop was observed. File-copy hashes were correct; that was not proof of a bootable image.

## Reproduced fatal defect
QEMU was booted through ARM64 EDK2 firmware, a FAT USB image, GRUB, the original stubble UKI and its original embedded initramfs. It reached Linux 7.3.0-rc3, executed `/init`, printed WSL `init-distro` errors and panicked with `Attempted to kill init! exitcode=0x00000100` before mounting the live root.

The original initramfs `/init` is byte-for-byte the builder's WSL `/init` ELF binary (SHA256 `18204d25f9e8e6e9314829c85ae17eec2136bd1fd3922686a9e7b335495f3a3f`), not mkinitcpio's `/usr/lib/initcpio/init` shell script. WSL injects `/usr/bin/mount.drvfs -> /init`. The stock mkinitcpio `filesystems` hook enumerates all `mount.*` helpers, follows this helper's dependency and overwrites the real init script. The original archive contains that helper symlink too.

This establishes a fatal shipped-image defect. It does not prove the observed physical-machine reset got as far as that defect: a firmware/DT failure may occur earlier.

## Build corrections
- Project-local filesystems hook excludes `drvfs` and `wslfs`; WSL's own files remain untouched.
- Extract-and-validate gate requires `/init` to exactly match mkinitcpio's live-init script, excludes WSL helpers, and checks archiso plus board firmware.
- Explicitly include `nls_iso8859_1` and `nls_utf8`. A second EFI test reached archiso but could not mount the FAT32 source: `FAT-fs ... IO charset iso8859-1 not found`. The kernel's default FAT charset is modular, and mkinitcpio's generic filesystem hook filters NLS modules. The validation gate now checks their archive presence. Test fixtures now use a proper MBR/FAT32 partition rather than a superfloppy.
- New builds use explicit config arrays and a sanitized environment, with early local board/GPU firmware staging.
- Rootfs services: enable SDDM and NetworkManager, set graphical.target.
- Add the signed ALARM `linux-firmware-qcom` package: the original rootfs lacked generic Qualcomm GPU firmware even though its DT-named local zap/DSP firmware was present.
- Remove `quiet`, enable loader/kernel diagnostics, and use `panic=0` to preserve a kernel panic on screen rather than automatically rebooting.
- Preserve original UKI/squashfs/staging as evidence; produce separate v2 artifacts.

## Additional boot-chain difference
The downloaded Ubuntu Concept ISO's `boot/grub/grub.cfg` detects Snapdragon processors and invokes `cutmem 0x8800000000 0x8fffffffff` when GRUB lockdown is not enabled. Its comment calls this a Snapdragon X firmware-bug workaround; it also appends `arm64.nopauth`. Original Kestrel direct-stubble loading skipped this GRUB step. The diagnostic menu carries the reference conditional workaround and offers both Kestrel and Ubuntu control entries. Its effectiveness on the physical Lenovo remains untested.

## Evidence
- `testing/boot-failure/qemu-grub-original.log`
- `testing/boot-failure/qemu-grub-original-result.json`
- `testing/boot-failure/rootfs-audit.md` (rootfs-only inspection, not initramfs validation)
- `testing/boot-failure/control-reference/boot/grub/grub.cfg`
- `builder/validate-live-initramfs.py` (original image exits 1)
- `builder/initcpio/install/filesystems`

## Verified v2 test results
Both disposable MBR/FAT32 EFI tests passed on QEMU `virt`, `cortex-a53` (ARMv8-A), 2 GiB RAM, two vCPUs:
- `qemu-v2-nls-shell-result.json`: real GRUB -> corrected UKI -> live initramfs -> USB FAT32 mount -> squashfs -> writable overlay -> rootfs bash; `uname` was `7.3.0-rc3`, `ID=kestrelos`, SDDM and NetworkManager read back `enabled`, and the kernel reached `reboot: Power down`.
- `qemu-v2-nls-systemd-result.json`: systemd reached `Multi-User System`; its serial log showed `Started Network Manager`. The VM was then terminated by the test harness. No Plasma/GUI claim is made.
- Final initramfs extracted-validation gate passed all nine checks, including exact live PID 1, absent WSL helpers, FAT charset modules and local board firmware.
- Original failures and first v2 FAT-mount failures remain preserved in their separate logs/images.

Local-only `live-staging-v2` contains 442 files / 6,631,784,896 bytes, including both Kestrel and Ubuntu control payloads. `testing/boot-failure/staging-v2-manifest.json` records all per-file SHA256s and the two VM test results. The original ISO's integrity list omitted grub.cfg; the adapted list updates the changed EFI loader and adds a checksum for the new menu. Original ISO payload/provenance are retained.

## Remaining acceptance gates
The owner approved the file-only update on 2026-10-09 ("update USB and reask questions if needed"). The update completed normally (exit 0) against Kingston DataTraveler PhysicalDrive2, FAT32 KESTREL_A64 at E:. Robocopy copied all 442 manifest files with zero failures; the updater read back and matched all 442 SHA256s. Independent post-update verification confirmed the USB identity, all 442 file sizes, the 6,631,784,896-byte manifest total, and fresh hashes of the EFI loader, corrected UKI, live squashfs and GRUB menu. Only two Windows System Volume Information metadata files were outside the manifest. The update did not format the disk or change internal disks, BCD, BIOS or Windows boot settings. Real Lenovo boot, Plasma, wired networking and thermals still require an owner-executed hardware test. Ubuntu control boot is also untested. Local DriverStore firmware keeps these images private and non-publishable.

USB evidence:
- `testing/boot-failure/usb-v2-result.json`
- `testing/boot-failure/usb-v2-20261009T104545Z.log`
- `testing/boot-failure/usb-v2-independent-verification.json`
- `testing/boot-failure/verify-live-stick-v2.ps1` (read-only USB checks; exit 0)
- Original loader/checksum backup: `testing/boot-failure/usb-before-v2-20261009T104545Z/`

Next native test: use the existing one-time USB boot selection. Confirm the visible diagnostic GRUB menu, select Ubuntu Concept control (Try Ubuntu only, never install), then test Kestrel v2. Record the last visible text/photo and whether the machine reaches a desktop, freezes or restarts. If the desktop fails, the text-only Kestrel option separates graphical-login failure from early boot failure. Do not repeatedly retry an unchanged early-reset path.

## Native v2 boot attempt (2026-10-09): menu appears, both entries reset
The owner reported: the GRUB menu appeared. Ubuntu Concept control showed a black screen for a few seconds, then restarted automatically to BIOS. Kestrel v2 desktop showed scrolling Linux messages for some seconds, then crashed with an automatic restart. No photo was captured. No logs survive these resets: USB recovery found zero new files, and UEFI variable enumeration (78 names) found zero Linux crash records, so there is nothing to reconstruct the lost messages from.

## USB log-capture diagnostic option (owner-approved, applied 2026-10-09)
A separate `kestrel-live-log.efi` UKI (revision v2-log6) plus two menu entries write kernel/initramfs/userspace logs to `Logs/boot-<id>/` on the same USB before a crash. Design limits: USB label `KESTREL_A64` + marker file + USB-sysfs checks, 32 MiB free-space gate, 16 MiB kmsg cap, 120 userspace samples; writes go through the live system's own USB mount (an early separate mount blocked the live mount during testing); the log UKI is inert unless its menu entry is selected. Cannot capture a reset that happens before Linux reaches the logger.
- File-only delta applied to Kingston PhysicalDrive2 E:: `EFI/Linux/kestrel-live-log.efi` (244,916,224 B), `boot/grub/grub.cfg` (new 6-entry menu, default unchanged), `KESTREL-LOG-TARGET` marker, `Logs/` directory. Updater and independent checks both passed (3/3 delta hashes plus untouched v2 bootloader/UKI hashes). No formatting, internal-disk, BIOS or Windows boot-setting changes.
- VM proof: `qemu-v2-log6-shell` and `qemu-v2-log6-systemd` both PASS (GRUB -> log UKI -> overlay root -> poweroff / Multi-User System; captured kmsg, dmesg snapshots, initramfs console, 284 KB userspace journal read back off the FAT).
- Evidence: `testing/boot-failure/log-option-manifest.json`, `usb-log-option-result.json`, `verify-log-option.ps1`, build log `build-uki-v2-log6.log`, revision build dirs `/home/builder/uki-v2-log*` (v2-log..v2-log5 preserved as superseded evidence).
- Next: boot the USB, select a `Kestrel v2 + USB LOG CAPTURE` entry, let it run/crash, reboot to Windows, and report the new `E:\Logs\boot-*/` files. If the reset happens before any `Logs/boot-*` directory appears, the crash is before the live logger and needs a photo of the last screen instead.

## Native log-capture attempt (2026-10-09): logger never reached, photo instead
`E:\Logs\` is empty after the owner's log-capture boot: no `boot-*` directory, so the USB logger never started. The owner's photo explains why: the kernel froze ~0.145s after kernel entry, during integrity/MODSIGN init (`integrity: Couldn't get UEFI db/dbx list`, `secureboot mode unknown`, `No TPM chip found`). USB storage only appears ~50s into boot and the logger starts after the live mount, so an early-kernel freeze leaves nothing behind by design.
- Photo proves real hardware progress: ARM64 kernel running on the Lenovo (PMIC arbiter v7, msm_serial, mmo timer, PMU), device tree plausible, `simple-framebuffer` + `Console: switching to colour frame buffer device 240x75` working. No kernel panic is visible; the screen stops mid-init with no userspace (`Run /init`, root mount) reached.
- The db/dbx `Unsupported` warnings are normally non-fatal; the actual hang is at or just after this point and needs a later photo/video to place (continues scrolling vs frozen vs reboot) plus which menu entry was used.

## Screen-as-log: initcall-debug entries (menu updated 2026-10-09)
No storage logger can run before ~50s, so the screen is the only channel for this early reset. Two file-only menu entries were added (existing UKIs, no rebuild): `initcall debug` prints every driver initcall with its return status, so the last visible line at reset names the crashing init; the second adds `nowatchdog` to test the watchdog-reset hypothesis with one variable changed. New menu (3,654 B) was VM-booted to Multi-User (`qemu-v2-log6-menutest` PASS), then copied file-only to the USB with pre-state check, backup and read-back hash match. Default entry unchanged.

## Five-boot photo series (2026-10-11): nondeterministic loader placement
The owner sent five screenshots from the initcall menu. Together they show THREE different outcomes from the same binaries: (a) stub prints DTB-found then silence, no kernel output; (b) `EFI stub: ERROR: FIRMWARE BUG: kernel image not aligned on 64k boundary` then hang; (c) healthy kernel driver probing to 0.5s (interconnect/power-domain probes, all expected return codes, no panic). `E:\Logs\` stayed empty throughout, consistent with never reaching the logger.
- Root cause (confirmed in source): stubble `linux_exec` copies the inner kernel to an `AllocateAnyPages` buffer, which guarantees only 4K alignment, while the ARM64 kernel stub requires 64K (TEXT_OFFSET). Fresh-firmware allocations are often 64K-aligned by luck, so some boots run and others fail at the stub check. Fix: over-allocate 15 pages and align the base up to 64K (`pkgs/stubble-arm64/patches/0001-linux-exec-64k-kernel-alignment.patch`, generated from pristine tarball; tree verified pristine first; `make` exit 0).
- Both UKIs rebuilt against the fixed stub (plain `v2-align1`, log `v2-log7`) and VM-validated: shell + systemd PASS each (one plain-systemd run exceeded the 240s harness budget under load but reached Multi-User in its log; rerun passed in 218s). File-only USB refresh applied 2026-10-11 with pre-state checks, backup and read-back hashes (`testing/boot-failure/usb-align-result.json`).
- Next: boot the initcall entry 3 times, photographing each outcome. If the alignment error and silent stalls are gone, whatever remains is a second, separate issue to bisect from the last initcall line.

## Alignment fix confirmed on hardware (2026-10-11): reset moved later
Two post-fix initcall photos both boot cleanly past the stub with no alignment error and healthy probing to ~0.51s (smem/interconnect/power-domain/cluster probes, all expected codes, no panic). Both still end in automatic reset, at slightly different points. The loader bug is fixed; a second, later reset remains, located after 0.51s in driver probing. Next evidence: video or later photo catching the last lines at reset, plus the nowatchdog entry to test whether the reset itself is watchdog-driven (freeze instead of reboot would name both the resetter and the hang point).

## Both initcall videos reset at the same place (2026-10-11)
Frame-by-frame review of both videos (with and without `nowatchdog`): kernel runs to ~0.51s, last lines are qnoc interconnect probes (`1680000.interconnect returned 0`), then black screen and reset. No panic/oops in any frame. Watchdog entry behaves the same, so the kernel watchdog is ruled out as the resetter. Next DT node in address order after 1680000 is `interconnect@16c0000` (pcie_south_anoc), making its probe (or the immediately following driver) the prime suspect. Control files verified intact on USB (`/casper/vmlinuz` + `/casper/initrd`, 8 menu entries). Next: one Ubuntu-control boot with photo to separate a machine-level reset from an our-kernel/DTB reset.

## Interconnect-blacklist test entry (menu updated 2026-10-11)
New entry `Kestrel v2 - NO interconnect driver` boots the plain UKI with `initcall_blacklist=qnoc_driver_init` (symbol confirmed in System.map; kills all qnoc probing). If the boot progresses past 0.51s, the crash sits in interconnect probing; if it resets identically, the suspect moves on. Menu VM-booted to Multi-User (`qemu-v2-menutest2` PASS) and applied file-only with pre-state/backup/read-back checks. No rebuild, default entry unchanged.

## Blacklist boot goes much further (2026-10-11): crash site confirmed
Four owner photos of the blacklist boot show regulators setting voltages, PCIe/USB/GPU/display probing, and finally `qcom-bam-dma-engine 1dc0000.dma-controller: deferred probe timeout, ignoring dependency` — the kernel alive at end of deferred probing, no panic, no reset at 0.51s. Remaining deferrals (mdss display, adreno GPU, USB phys, BAM DMA, wwan) are expected with interconnects off. Crash site confirmed inside qnoc probing (first un-probed node after 1680000 is `interconnect@16c0000`/pcie_south_anoc). Next: check the kernel fork for newer qnoc/Slim3 fixes, else DT-disable 16c0000 as the single-variable test.

## Single-node test: 16c0000 disabled (on USB 2026-10-11)
Fork frozen at our pin (no upstream fix). Board-DTS override `&pcie_south_anoc { status = "disabled"; }` recorded as local-only diagnostic patch `pkgs/linux-cachyos-arm64/patches/0006-...`; DTB rebuilt with the exact per-board target (207,656 B, `fdtget` confirms disabled); plain UKI `v2-dt1` VM shell PASS. File-only USB swap of `kestrel-live.efi` applied with pre-state/backup/read-back (`usb-dt1-result.json`). Boot the normal initcall entry (NOT the blacklist one): if it passes 0.51s, 16c0000 is the reset site; if it resets identically, the crash is systematic, not node data.

## Consumer-bisect entries (menu updated 2026-10-11)
16c0000-disable changed nothing, so the crasher is a downstream driver released by interconnects, not node data. Three new entries ban suspect groups via `initcall_blacklist` (symbols from System.map): display/GPU (`msm_drm_register`), USB/PCIe (`dwc3_qcom_driver_init,qcom_pcie_driver_init,xhci_plat_init`), DSP firmware (`qcom_pas_driver_init`). Whichever progresses past 0.51s names the family for round 2. Menu VM-booted to Multi-User (`qemu-v2-menutest3` PASS), file-only USB refresh verified. Note on empty `E:\Logs`: the logger can only start after USB+rootfs (~50s+ kernel time); a ~0.5s reset is 100x too early for any storage logger, so the screen stays the only channel until boot gets that far.

## Bisect round 1: all three reset within 13ms (2026-10-11)
Owner reported last timestamps 0.511871 (no display/gpu), 0.525024 (no usb/pcie), 0.515395 (no dsp) — all reset at the same place. None of those families is the crasher. Still needed: the actual last photo lines from those boots. Remaining early suspects move to round 2 (SMMU, PDC).

## Bisect round 2: phys and iommu/pdc (menu updated 2026-10-11)
45s blacklist run (frozen black, no reset, no logs) proves the reset needs interconnect-dependent drivers and the black screen is display-without-icc, not death. Two new entries: NO usb/dp phys (`snps_eusb2_hsphy_driver_init,qcom_snps_hsphy_driver_init,qmp_usbc_driver_init,qmp_usb_driver_init,qmp_combo_driver_init`) and NO iommu/pdc (`arm_smmu_init,qcom_smmu_module_init,qcom_pdc_driver_init`). Menu VM-booted (`qemu-v2-menutest5` reached Multi-User) and applied file-only with pre-state/backup/read-back. One photo of the last screen per entry.

## Two void tests found; display/DSP/WLAN/camera/video/UFS-host all modules (2026-10-11)
`verify-blacklist-names.py` against System.map: `msm_drm_register` and `qcom_pas_driver_init` NEVER MATCHED — those two entries excluded nothing. Worse, .config shows DRM_MSM=m, QCOM_Q6V5_PAS=m, VENUS=m, CAMSS=m, ATH12K=m, UFSHCD=m: none of them are even present during early boot. UFS PHY (=y, `qmp_ufs_driver_init`) was the one PHY family never banned. Round 3 menu entries (7527 B, VM `qemu-v2-menutest6` Multi-User PASS, USB verified): NO ufs phy entry + NO cpuidle entry (`cpuidle.off=1` — if the kernel reaches the end of probing then dies on first CPU power-collapse, this walks straight past it).

## Bisect round 4: boot reaches 9.45s — tail NoCs were the reset site (2026-10-15)
Owner booted entry #6 with dt2: last line `9.458923 regulator-wcn-1p9 ... returned -517`. Kernel time 9.45s is ~20x further than every prior boot (0.51s wall) — the tail-NoC disable WORKED; one (or more) of gem/nsp/lpass-ag/lpiaon/lpicx was the silent-reset site. The -517 itself is a benign EPROBE_DEFER (supply not ready, retried later), NOT the crash — the killer is whatever probed next, off-screen. Needed: full-screen photo (earlier lines name the next suspect) + outcome after that line (reset/freeze/continue + wall seconds).
Five tail NoCs (gem, nsp, lpass ag/lpiaon/lpicx) plus the earlier 16c0000
disable are the only qnoc nodes left after the 1770000/1780000 crash
point. Recorded as local-only patch `0007`, DTB rebuilt natively
(207,776 B — cross-ld was missing, native aarch64 gcc used), all six
`fdtget` statuses verified disabled. Plain UKI `v2-dt2` (244,385,792 B,
`b1adc18b...`) VM shell PASS (rootfs/overlay/poweroff). Promoted into
staging and applied file-only to USB with pre-state/backup/read-back
(`usb-dt2-result.json`). Boot the normal initcall-debug entry: if it
walks past 1780000, the crasher is one of the five — re-enable round
follows. If it resets at the same place, the crash is NOT a late qnoc
probe and the theory redirects.

## Bisect round 5: minimal-boot DT cut (dt3 on USB 2026-10-15)
Owner confirmed the 9.45s frame IS the end (screenshotted from video).
22 nodes disabled in one cut (patch `0008`, all verified via decompiled
DTB): 4x PCIe + 4x PCIe PHYs, 7x WLAN/WWAN/display/NVMe rails, 4x
thermal sensors, 2x display PHYs, UFS PHY. USB and core stay enabled.
Plain UKI `v2-dt3` (244,386,304 B, `a3d1f6c2...`) VM shell PASS,
promoted to staging, USB file-only verified (`usb-dt3-result.json`).
Boot entry #6: if it walks past 9.45s toward USB/rootfs, re-enable
families one at a time. If it resets at the same place, the crasher
is in the remaining core (USB path, PMIC, pinctrl, SCM) and the
emergency-shell capture plan activates.

## The hang chain found in source; 0009 breaks it (2026-10-15)
19s transcription: timeout wave forcing drivers through (bam-dma,
3x QUP, scmi all `returned 0`), but pinctrl/SCM/USB/IOMMU still
deferring, then black. Root chain, all verified in source + DT:
SCM's icc path (aggre2 0x17 + mc_virt 0x18) never resolves ->
SCM defers -> X1E PDC quirk `if (!qcom_scm_is_available()) return
-EPROBE_DEFER` (qcom-pdc.c:720) -> TLMM (wakeup-parent = PDC 0x99)
defers -> no GPIO -> USB PHYs/regulators stuck -> no USB storage ->
no rootfs -> black hang. Fix 0009: `/delete-property/ interconnects`
on `&scm` — devm_of_icc_get treats absent property as no-vote, so
SCM probes without bus voting. DTB 208,016 B verified scm-without-
interconnects. UKI v2-dt4 building.

## dt4 (SCM unblocked) on USB 2026-10-15
v2-dt4 (244,386,304 B, `93019748...`) VM shell PASS, promoted to
staging, USB file-only verified (`usb-dt4-result.json`). Boot entry
#6: expect SCM/PDC/TLMM to probe in the first wave instead of
deferring — screenshot the 0.5s region AND the late region.

## dt4 boots: pinctrl first-try, kernel reaches init at 8.9s (2026-10-16)
Owner transcriptions: 0.57s wave all green incl. `f100000.pinctrl
returned 0` (chain broken as predicted); 9.02s `Run /init`, udev
triggering uevents (userspace reached); 9.33s clocks/power/SMMU/PMIC
all resolving. Awaiting outcome after 9.33s (desktop? hang? reset?).

## Black screen right after 9.33s; regulator-cleanup suspect (2026-10-16)
Owner: black immediately after 9.33, then nothing. Prime suspect is
the kernel's own unused-regulator poweroff (`regulator_init_complete`
ran at 8.85s, screen dies ~9.3s): a firmware-left-on panel/backlight
rail with no consumer gets switched off. `regulator_ignore_unused`
confirmed in source (core.c `__setup`). New entry `initcall debug,
keep regulators` added, menu VM-booted (`qemu-v2-menutest8` PASS),
USB verified (11 entries). Boot it: if the screen survives past
9.33s, theory confirmed and boot proceeds toward USB/rootfs.

## Keep-regulators boot: USB PHYs binding, GPIO alive (2026-10-16)
Owner frame ends 9.268614 `88e3000.phy (qcom-qmp-usb-phy) returned 0`:
combo-phy + qmp-usb-phy bound, `qcom-spmi-gpio returned 0` (GPIO
alive — TLMM chain fully resolved), rpmh `regulators-1 returned 0`
with voltage-setting lines, dispcc/camcc/videocc/lpasscc all `0`.
dwc3 hosts still deferring (-517) but their PHY prerequisites are now
binding. Awaiting outcome after 9.27s (screen survived? black? what
next?).

## Regulator theory dead; display-clock init now suspect (2026-10-16)
Keep-regulators boot ALSO goes black (~9.3s) — cleanup ruled out.
`E:\Logs\` still empty (no rootfs; USB never completes). clk/pd
ignores confirmed on USB cmdline. New prime suspects active exactly
at the black point: dispcc/videocc/camcc init (24ms/21ms block
resets), adreno-SMMU config, or a backlight driver binding to OFF.
Zero-cost physical tests asked: flashlight-at-angle (backlight vs
signal) + caps-lock LED (alive vs dead). If signal-loss: blacklist
dispcc/camcc/videocc inits (names confirmed on-screen) menu-only
round follows.

## Full SoC hang at ~9.3s; cpuidle + smmu rounds (2026-10-16)
Owner: flashlight shows nothing (signal loss) + caps-lock dead
(kernel dead) on entry #10. Full silent freeze, no reset. Suspects:
CPU power-collapse on first idle, or IOMMU enable. Menu now has NO
cpuidle (#9, `cpuidle.off=1`) and re-added NO iommu (#12, smmu-only —
old combined verdict is stale, crash point moved). VM menutest9
Multi-User PASS, USB verified. Boot #9 first, then #12, last-frame
photo each.

## NO iommu alive at 19.4s, GPU binding (2026-10-16)
#11 (smmu ban): 9.5s archiso mounting KESTREL_A64 (10s wait), fd3000
USB PHY bound; 19.44s timeout wave forces GPU `returned 0`, GMU
starting — screen ALIVE 10s past the old death point. SMMU enable
looks like the 9.3s killer. Awaiting mount outcome (desktop/shell?)
+ #9 cpuidle outcome.

## Both end black; dwc3 needs gem_noc — re-enabling it (2026-10-16)
#9 and #11 both end black, no logs (mount times out, USB never
enumerates). Root cause in DT+source: dwc3 acquires `apps-usb` =
gem->config_noc, and gem is OUR 0007 disable — USB can never come
up. Fix 0010 re-enables gem alone (nsp/lpass/16c stay off). v2-dt5
building. Boot #6 when on stick: reset at 0.51s = gem was the
crasher; dwc3 binding + USB enumeration = USB unblocked, watch for
the mount.

## dt5 (gem back) on USB 2026-10-16
v2-dt5 (244,386,304 B, `239b5634...`, .dtbauto 208,012 B) VM shell
PASS, promoted, USB file-only verified (`usb-dt5-result.json`).
Boot #6: reset at 0.51s = gem was the crasher (route USB around
it); dwc3 `returned 0` + `new USB device` + mount = USB unblocked,
then watch what display/rootfs do.

## dt5 stops at 0.54s again; gem's voter looks wrong (2026-10-16)
Owner: #6 ends at `1780000 returned 0` @0.540753 ("Full Downgrade" —
back at the old wall). New: `interconnect-0/1` (clk_virt+mc_virt)
both `returned 0` — mc_virt registers now. But no pinctrl line
(dt4 had it at 0.556s). gem's `qcom,bcm-voters = <0x1b>` resolves
to an SCMI shmem node, not a voter — likely DT quirk (yields defer,
not reset). Awaiting: RESET or HANG at 0.54s + wall seconds?

## Reset in 4s wall with gem on; rerouting USB around gem (2026-10-16)
Owner: RESET after 4s wall. dt5's only delta vs the 19s-booting dt4
is gem → gem's presence resets the machine (probe itself or an
unlocked consumer; GENI children can't exist yet at 0.54s). But dwc3
needs gem for apps-usb. Fix 0011: gem back off + each dwc3
apps-usb pair rerouted onto its own usb-ddr pair (verified: no
0x36 in any dwc3 interconnects, 12 cells each). v2-dt6 building.

## dt6 (gem off, USB rerouted) on USB 2026-10-16
v2-dt6 (244,386,304 B, `6b27f7f2...`) VM shell PASS, promoted,
USB file-only verified (`usb-dt6-result.json`). Boot #6: no 0.54s
reset expected (gem off); watch dwc3 lines ~9.5s (`returned 0` =
reroute worked) then `new USB device` + the mount.

## dt6 boots past 9.26s, GPU joins IOMMU group (2026-10-16)
Owner: no 0.54s reset; 9.26s `platform 3d00000.gpu: Adding to iommu
group 11`, spmi-gpio alive, all clock controllers green — WITH smmu
enabled. The 9.3s death didn't repeat. Awaiting: dwc3/USB/mount
outcome after 9.26s.

## dt7: black ~9.34 with no GPU either; wait for the 19s wave (2026-10-16)
dt7 frame ends 9.3436 (combo-phy defer): no GPU lines (disable
worked), gpio-keys bound, PMIC alive — yet black again. But silence
9.3→19s is NORMAL (deferred retries only fire on supplier events +
the ~19s timeout wave; #11 proved the kernel can be alive behind
it). #10's caps-dead verdict may have been GPU-SMMU-specific. Asked:
caps-lock test on dt7 black + wait 60s for the timeout wave (photo
any text that appears).

## Black-with-backlight: mdss takes over, panel never lights (0013, dt8 building 2026-10-16)
Owner: screen alive, backlight on, no image; caps untested. removing
gpu/gmu didn't stop it because the mdss driver (initramfs module)
binds the still-present `ae00000.display-subsystem`, takes over the
firmware framebuffer, and the panel never lights. Fix 0013 disables
`&mdss`; console stays on simplefb. v2-dt8 building + VM, then USB.

## dt8 (no mdss) on USB 2026-10-16
v2-dt8 (244,386,304 B, `00b5ffe6...`, .dtbauto 208,048 B) VM shell
PASS, promoted, USB file-only verified (`usb-dt8-result.json`).
Boot #6 and STAY on text: if lines keep flowing past 9.34s toward
the 19s wave, the invisible-boot era is over — then it's purely a
USB/mount fight.

## dt8: black ~9.15 with text stopping at voltage-sets; smmu entry back (2026-10-16)
dt8 frames: init 8.76s, gpio-keys registered as input0, SMMU
configured, first PMIC voltage-sets at 9.12-9.15s, then black
("shortest boot"). mdss/gpu/gmu all off yet black persists. The
longest visible boot ever was the SMMU-ban (19.4s text), so NO
iommu is back as entry #7 (menu 3774 B, menutest11 Multi-User PASS,
USB verified). Boot #7, wait 60s, photo any late text.

## #7 (dt8+smmu-ban): text stops 9.22s, hdmi-connector bound (2026-10-16)
#7 frame ends 9.225098 (rpmh regulators-2 defer); new: `hdmi-
connector ... returned 0` (display-connector binding). dt4's smmu-
ban lived to 19.44s, so the question is whether #7's 9.2s black is
death or just the normal silent gap before the ~19s timeout wave.
Asked: wait 60s on black, photo any late text.

## Instant black-freeze at 9.22s; dispcc module ban (2026-10-16)
Owner: instant black freeze right after 9.225, forced shutdown.
`disp_cc_x1e80100_init` is NOT in System.map (module-local) so entry
#8 uses `module_blacklist=dispcc_x1e80100`. Menu 4209 B, menutest12
Multi-User PASS, USB verified.

## #8: xhci UP at 19.47s then torn down at 19.51s (2026-10-16)
#8 (dispcc module ban): screen alive past 9.3s; repeater + regulators
bound, mount + 10s wait; 19.47s xHCI up (buses, hubs — dwc3 bound
off-screen!), then at 19.51s both root hubs disconnect + `remove,
state 1`. Role-switch theory DEAD (`dr_mode = "host"` already in
DT). One line at 19.506 (the actual error) unreadable in photo.
Awaiting: outcome after 19.513764 + that hidden line.

## Stale-phandle bug in 0011; label-based 0014 (dt9 building 2026-10-16)
Owner read the hidden line: interconnect-cells error for the cpucp
mailbox. Root cause in MY method: 0011 hardcoded raw phandle numbers
from a stale decompile — 0x18 now resolves to the mailbox, breaking
path parsing (and the xhci teardown). The fork source uses &labels
(single usb-ddr path + gem apps-usb path per port). Fix 0014 redoes
the reroute with &labels (compile-time resolved, verified per-node
in the new DTB: usb_noc+mc_virt only). Rule: never raw numbers.
v2-dt9 building + VM, then USB.

## Duplicate-pair rejected; apps-usb via config_noc (0015, dt10 building 2026-10-16)
dt9's `of_icc_get_by_index: invalid path` comes from core's
path_find refusing the SAME route twice (duplicate pair0 for both
names) — xhci torn down 40ms after coming up. Fix 0015 points
apps-usb at config_noc (stock shape, gem replaced, all &labels;
verified: usb_noc+config_noc per port, no gem/mailbox). If the
graph lacks that link, fallback is optional-apps-usb in dwc3-qcom
(kernel patch). v2-dt10 building + VM, then USB.

## dt10 (apps-usb via config_noc) on USB 2026-10-16
v2-dt10 (244,386,304 B, `e2e1fe93...`) VM shell PASS, promoted,
USB file-only verified (`usb-dt10-result.json`). Boot #8: if
apps-usb resolves, NO invalid-path line and xhci STAYS up — then
`new USB device` + mount. If invalid-path persists, the kernel
patch (optional apps-usb) is next.

## Unified capture on USB 2026-10-16
v2-dt11 (244,916,736 B, `765ddb44...`, hook-in) VM shell PASS
without flag (inert proven) + menutest16 PASS with capture
(multi-user, kmsg, journal). Promoted, both log entries repointed
at the shared image + flag, menu 4621 B, stale log UKI retired to
backup. USB file-only verified (`usb-unified-result.json`). Any
entry can now capture by adding `kestrel_log=1`.

## Capture flag on all entries (menu 4705 B, 2026-10-16)
Owner: flag on #8 and everywhere. All 8 Kestrel entries now carry
`kestrel_log=1` (Ubuntu excluded, foreign initramfs). Menutest17
needed the unified UKI swapped into the fixture (it still carried
the hookless one) then PASS with capture. USB menu-only update
verified. Whichever entry goes furthest now logs automatically.

## dt13 ON USB — FW LOG NATIVE TEST ON HOLD (audit correction)
v2-dt13 (244,919,296 B, `0f319c98...`) and its menu remain on the
USB. Hook inclusion and generic VM root-shell boot passed, but
the VM command line did NOT enable `kestrel_efilog=1`; firmware
capture and persistence were never tested. The writer has no
total write limit and hides failures; the Windows reader has a
misplaced parameter block and incomplete privilege/error handling.
The earlier "BOOT FW LOG NOW", "survives any crash" and "No photos
needed" claims are retracted. Do not use FW LOG or the reader's
`-Delete` mode until hardened and validated. See
[firmware-logger-audit.md](firmware-logger-audit.md) for evidence
and the remaining safety gates. The audit changed no USB or
firmware contents.

## Current USB content (verified 2026-10-16, read-back from E:)
- `EFI/Linux/kestrel-live.efi` — v2-dt13 (0016 + efilog hook),
  244,919,296 B, `0f319c9847b3dcbb31701b707c557d78fab62fd7bbaf9823174ac63c2e4410a2`
- `boot/grub/grub.cfg` — 5225 B,
  `9bbf0d682159a9ac5d5856b8c58efa20ec0d6bec0a3f721a50593f7f912e5200`,
  11 entries (FW LOG = NO dispcc + `kestrel_efilog=1`)
  (supersedes dt11 `765ddb44...` / menu `ce2580fa...` above)
- `boot/slim3-x126100.dtb` — control DTB (unchanged)
- `EFI/boot/bootaa64.efi` — reference GRUB (unchanged)
- `arch/aarch64/airootfs.sfs` — repaired v2 rootfs (unchanged)
- Retired (backed up, off the stick): `kestrel-live-log.efi`
  (log7, stale tree)
- Menu: 1 desktop, 2 Ubuntu, 3 text-only, 4 log-desktop,
  5 log-text, 6 initcall debug, 7 NO iommu, 8 NO dispcc,
  9 FW LOG (HOLD; do not boot), 10 slow print, 11 return

## dt10: xhci bound at 9.49s, no invalid-path (2026-10-16)
Owner: NO invalid-path line; `xhci-hcd.0.auto returned 0` at
9.495705 (10s earlier than ever), buses + hubs up, fd3000 PHY
bound — config_noc route resolved, controller STAYS (no teardown
in frame). Other dwc3 ports still retrying (-517). Awaiting: real
device enumeration (stick/mouse vendor IDs?) + mount.

## config_noc link missing too; apps-usb optional in driver (0016, kernel rebuilding 2026-10-16)
dt10 still `invalid path` then teardown: the graph lacks NoC to
config_noc links as well. Fallback executed: driver patch 0016
makes `apps-usb` best-effort (warn + NULL, all use sites guarded;
usb-ddr still votes). Applied to ksrc with assertions, recorded.
Kernel Image rebuilding incrementally, then UKI v2-dt12 + VM +
USB. If dwc3 binds and stays, USB enumeration is next.

## dt12 BUILT + patch-in-Image verified (2026-10-16)
UKI 244,916,736 B, `passed:true LIVE_UKI_DONE`, 0016 warn string
present in the Image (52,492,800 B). WSL rebooted mid-session
(/mnt/d mount point gone; `mount -t` mangled through wsl.exe —
use `mount --type`); build had already finished. VM shell PASS.

## dt12 ON USB 2026-10-16 — BOOT ENTRY #8 NOW
v2-dt12 (244,916,736 B, `afb0aa04...`) VM shell PASS, promoted,
USB file-only verified (`usb-dt12-result.json`). 0016 in the
Image: the diagnostic workaround attempts to skip an unavailable
apps-usb path with a warning. Native success is NOT verified:
the owner tested dt12 without a photo or recovered trace. The
expected warning, continued host operation, physical USB-device
enumeration and successful mount remain observations to obtain,
not established results.

## Historical UEFI-variable proposal — superseded by safety audit
The following design notes were provisional, not proof of safe
capture. Its retained bytes are bounded but write count is not;
survival across crashes and reader success are unverified. See
[firmware-logger-audit.md](firmware-logger-audit.md) before acting.

### Original proposal (2026-10-16)
Owner: "smart optimized way to actually log on USB". Reality: no
file logger can run before USB storage exists. Answer: stream
dmesg tails (4x512B rotating + seq) into NVRAM vars from an
earlyhook loop — survives resets/hangs, readable from Windows via
`read-kestrel-efilog.ps1` (`-Delete` frees NVRAM). Files ready:
hook + install + loop + reader. NOT wired into the build yet
(never patch build-live-uki.sh mid-build). Flag: `kestrel_efilog=1`.
Risk (stated plainly): bounded tiny writes + deletable, but
nonzero firmware-quirk risk; flag-gated, opt-in per boot.

## xhci up then black, no devices, no logs; slow-print entry (2026-10-16)
Owner: full black after 9.49s, no devices, no mount; `E:\Logs\`
empty. Paint-lag makes last-lines unreliable, so new entry #9
(`boot_delay=1000`, one second per line): the line on screen when
it goes black IS the killer. Menu 4660 B, menutest13 Multi-User
PASS, USB verified. Boot #9 and photograph the frozen line.

## dt9 (label reroute) on USB 2026-10-16
v2-dt9 (244,386,304 B, `3004ed18...`, .dtbauto 208,048 B) VM shell
PASS, promoted, USB file-only verified (`usb-dt9-result.json`).
Boot #8: dwc3 should bind WITHOUT the mailbox error this time;
watch for `new USB device` (the stick!) then the mount.

## Black right after GPU iommu-attach; gpu+gmu cut (dt7 building 2026-10-16)
Owner: black screen after 9.264837. Without SMMU the boot lived to
19.4s+; with GPU joining its IOMMU group the display dies — the
GPU-SMMU interaction is the killer (context setup or zap firmware
load). Fix 0012 disables `&gpu` + `&gmu`; console stays on the
firmware framebuffer. v2-dt7 building + VM test, then USB.

## dt7 (no gpu/gmu) on USB 2026-10-16
v2-dt7 (244,386,304 B, `ce428160...`, .dtbauto 208,044 B) VM shell
PASS, promoted, USB file-only verified (`usb-dt7-result.json`).
Boot #6: screen should survive 9.26s now; watch dwc3/USB/mount
after, plus where (if anywhere) it stops next.

## dt2 ending was a black hang, not a reset (2026-10-15)
Owner: after the 9.45s frame the screen went black, waited minutes,
nothing, forced shutdown. No reset this time — the tail-NoC reset site
is eliminated and the failure mode changed to a hang. `E:\Logs\` still
empty, so the kernel never reached USB+rootfs (logger never started):
stuck in device probing with display dead, or dead. Awaiting the dt3
minimal-boot result (entry #6): reset vs black-hang + last frame.

## Round-1 photos: crash moved to 1770000/1780000, still no panic (2026-10-11)
All three boots sailed past disabled 16c0000 through ~10 more interconnects (1500000→1780000, `Skipping QoS` warnings, EPROBE_DEFERs all benign) and reset right after `1780000.interconnect` (mmss_noc). So the 16c0000-disable DID let probing continue — the reset is systematic, and every reset lands at ~0.51-0.525s kernel time regardless of node count. Caveat: the initcall flood over a ~10x-slow framebuffer means last-painted lags the true crash; the crash may sit in the next initcall after the deferred pass. Decisive next test costs nothing: boot the quiet DESKTOP entry (no initcall flood, paint keeps up) and photograph the last screen for true placement.

## Quiet desktop photo: caught mid-boot, not at reset (2026-10-11)
Owner's quiet-boot photo shows only 0.07→0.162s (display init, keyring, integrity, first QoS skips) — far earlier than the initcall boots' 0.51s, so this frame predates the reset; the boot was likely still running when photographed. No panic. Still needed: how many seconds from GRUB to reset in quiet mode, plus a photo of the FINAL screen before the reset.

## USB contents re-verified; 25s wall timer clue (2026-10-11)
Owner challenged whether the stick is actually patched: all 5 boot-critical hashes re-verified on E: (dt1 plain UKI, log7 UKI, latest menu, DTB, bootloader) — the fixes ARE on the stick. Owner confirms the quiet screen IS the last line and reset comes at exactly 25s wall. Combined with the videos (resets ~25-30s wall, kernel progress only 0.16-0.51s), the reset looks wall-clock-driven, not progress-driven — a firmware watchdog outside kernel control fits. Decisive test: time the NO-interconnect (blacklist) entry to reset. It already lived past the deferred-probe timeout message once; if it runs well past 25s wall, the timer theory dies and the crash is progress-dependent after all.

## Control entry was broken: no DTB passed (fixed 2026-10-11)
The Oct 9 "control FAILED" verdict is retracted as evidence: our Ubuntu entry never passed a device tree, and this is a DT machine (Windows boots via ACPI, so firmware gives Linux no DT). An arm64 kernel without DT dies pre-console — exactly the observed silent reset. Fix: `devicetree /boot/slim3-x126100.dtb` in the Ubuntu entry plus the staged DTB (207,656 B), menu VM-booted (`qemu-v2-menutest4` PASS) and applied file-only with pre-state/backup/read-back (`usb-controlfix-result.json`). If Ubuntu now boots, the machine is fine and its dmesg becomes the reference; if it resets at the same place, the reset is firmware/hardware-level.

## dt14/dt15/dt16 logger hardening + USB ready (2026-10-16)
Old unbounded firmware loop retired (never shipped past dt13, never ran natively).
Replaced with a bounded static binary (`builder/diagnostics/kestrel-checkpoint.c`):
64 KB RAM ring of /dev/kmsg from the early hook, always on with `kestrel_log=1`;
firmware checkpoints strictly opt-in (`kestrel_efilog=1`), max FOUR 1 KB
write-once records under project GUID `674b8af1-da8e-4c2b-a84c-467e2d36c97c`,
CRC + boot-ID stamped, existing records disarm new writes, 60 s deadline,
no updates/deletes, checked errors stop it. Default entries write NOTHING to
firmware (QEMU-proven: flag OFF creates zero records).
QEMU proof (disposable AAVMF store, abrupt-kill recovery): OFF->none,
ON->2 records, kill->records intact, re-opt-in with evidence present->refused
(`dt14-checkpoint-v1-result.json`, `persistence_verified: true`). Unit tests
(`test-checkpoint.py`) + read-only recovery script tests
(`test-checkpoint-reader.py`, `Read-KestrelCheckpoint.ps1`, no delete path)
pass on synthetic fixtures. Native firmware safety still NOT proven: entry #9
asks for typed YES and states EXPERIMENTAL; recommended native first boot is
entry #8 (default), which uses no firmware writes at all.
Handover bugs found by dt14 full-chain validation and fixed: the backgrounded
observer outlived switch_root (stale mount view -> console spam) -- cleanup hook
now owns the final USB sync and terminates it; STOPPED marker + console banners
added; all rotating file writes atomic (tmp+rename) after proving
truncate-then-poweroff yields 0-byte journals. dt15 proved lifecycle
(STOPPED on USB + console, zero spam) but its journal sample was cut by
poweroff timing; dt16 (same 7.3.0-rc3 kernel `a8a39190...`, same DTB
`fec64902...`, initramfs-only changes) passes the full gate:
`qemu-dt16-menu8-v4-result.json` -- systemd-multi-user at ~288 s, kmsg 187 KB,
journal 280 KB, early-kmsg with boot banner, STOPPED present, no panic.
dt14/dt15 superseded before touching USB (never staged).
Boot-chain audit (read-only, 2026-10-16): 0016 apps-usb workaround present in
source and DTB keeps both `usb-ddr`+`apps-usb` (workaround is the safety net);
`module_blacklist=dispcc_x1e80100` is VALID (module is `=m` AND packed in the
initramfs by the kms hook, so entry #8 is a real exclusion test);
`initcall_blacklist=arm_smmu_init,qcom_smmu_module_init` both in System.map;
no efi-pstore backend in initramfs (only pstore_blk/zone/ramoops frontends),
so firmware-off also means no pstore NVRAM path.
USB file-only update `usb-dt16-result.json` (`USB_DT16_VERIFIED`, backup kept):
UKI 244,407,296 B `d85658ae24762ef9ee0d71c4df2b3b208dbabbe8096dd7124805037fc8055cab`,
menu 5586 B `c79c5bc52f3f44c7acc2fcf362704cacc3d121932361861703506681614bd0f5`,
11 entries, default #8 NO dispcc; #9 FW CHECKPOINTS gated behind typed YES;
staging hashes match builder. Native state unchanged: G3 FAILED, no Logs yet.
Next native: boot default entry #8, photograph screen + note wall time; #9 only
after #8 is characterized, and export records with Read-KestrelCheckpoint.ps1
before any retest (existing records disarm new writes).

## Native #9 firmware checkpoints WORK + root cause found (2026-10-17)
Owner booted #8 then #9 on dt16. `E:/Logs` empty (USB never enumerated, as
expected). Firmware holds 3 records, one boot `c28598ee`, all CRC-valid
(`firmware-recovery-20261017T064728719Z`, read-only export, `valid: true`):
slot 0 @9073 ms `/init` running (cmdline proves #9, `kestrel_efilog=1`);
slot 1 @9589 ms xHCI bound (irq 154, `0x0a600000`); slot 2 @10106 ms
`dwc3-qcom a600000.usb: of_icc_get_by_index: invalid path=-517`.
No slot 3: machine died before the 60 s deadline. Notably ABSENT: 0016's
`apps-usb ... continuing without it` warning is NOT the failing site.
Probe-order proof (source): `dwc3_qcom_probe` runs `dwc3_core_probe()` (binds
the xHCI child) BEFORE `dwc3_qcom_interconnect_init()`; the parent then defers
on the lookup and the framework tears the bound child down. The only remaining
defer path in `interconnect_init` is `usb-ddr`.
Graph walk (`x1e80100.c` + shipped DTB): usb-ddr = usb_south_anoc -> usb_center
-> system_noc -> qnm_snoc_sf -> [gem_noc] -> qns_llcc -> llcc_mc -> ebi(mc_virt).
Every provider on the route is enabled with a built-in driver EXCEPT gem_noc,
disabled since the 0.51 s reset investigation. `path_find` therefore defers
forever; all four dwc3 ports (-517 on a200000/a400000 too) share the cause.
Our own reset-mitigation disable is what kills USB. The driver's own
`failed to get usb-ddr path` line prints microseconds after the trigger and
is cut from the 944 B record window -- inferred, not yet observed; the dt17
diagnostic build tests the inference directly.
Fix direction: dt17 makes usb-ddr best-effort (0017, mirrors 0016, NULL guards
on enable/disable/set_bw/put/exit, `ret = 0` init fix). If xHCI stays up and
enumerates the stick, inference confirmed and G3 unblocks via real USB logs;
then pursue the true memory-path fix. NOT for publication.

## dt17 (usb-ddr optional) validated, on USB (2026-10-17)
0017 applied via assertion script (`apply-0017.py`, 6 sites), patch record
`0017-diagnostic-dwc3-ddr-optional.patch`. Incremental kernel rebuild, same
size; Image carries both `continuing without it` warnings (apps-usb + usb-ddr).
dt17 UKI `15e9c8bb...` (244,407,296 B, kernel #3, same DTB) passes the full
gate: `qemu-dt17-menu8-v5-result.json` -- systemd-multi-user ~286 s, kmsg
185 KB, journal 287 KB, STOPPED present, no panic. One flake: 05-dmesg
snapshots absent on the FAT despite a clean console (force-poweroff vs FAT
flush timing; full stream in 01-kmsg regardless) -- watch, not a gate failure.
USB file-only update `usb-dt17-result.json` (`USB_DT17_VERIFIED`, dt16 backup
kept); independent read-back matches. Menu unchanged (default #8).
Native next: boot #8 (file logging should now work if xHCI survives).
#9 again only if #8 still tears down; export firmware first (records disarm
new writes).

## #8 carries efilog now; stale records cleared (2026-10-17)
Owner asked for the firmware logger in #8 too: entry renamed
`Kestrel dt17 - NO dispcc + FW CHECKPOINTS (default)`, same flags plus
`kestrel_efilog=1`. Menu-only USB update `update-live-stick-menu-efilog8.ps1`
(`USB_MENU_EFILOG8_VERIFIED`, backup kept): menu 5715 B `b3fb4e16...`,
UKI untouched (dt17). New `Clear-KestrelCheckpoint.ps1` (project GUID +
four names only, `-Yes` gate, pre-delete export, privilege hygiene)
removes cycled records; the three #9 records were exported then deleted,
read-back confirms all slots Missing. Reminder: each test boot consumes the
four one-shot slots -- export after every boot before retesting.
Also fixed along the way: `Read-KestrelCheckpoint.ps1` now exits 0/2
explicitly so callers can gate on `$?`; clear-script refusal path tested.
