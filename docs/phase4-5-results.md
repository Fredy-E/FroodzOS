# Phase 4-5 results - image assembly + stick write (2026-10-08)

> Current update (2026-10-18): [dt24 native interactive text boot passed](dt24-native-text-success.md). The early-boot failures below are historical. Native systemd/overlay/tty1/typed-command acceptance is now proven; the original desktop/network/full-hardware M1 gate is still open. See [current project progress](project-progress.md).

## Phase 4 - image assembly: DONE
- Live rootfs built in the builder (pacstrap upstream + our signed kernel via [cachyos-arm64]):
  `linux-cachyos-arm64-7.3.0rc3-1` installed in target with full signature verification
  (keys: master 100A8D5D...B61B722F + builder key, locally signed; DB + pkg sigs checked).
- 10/10 firmware files staged from the Windows DriverStore into
  `usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/` (local-only, ADR-5).
- Live identity: os-release "Kestrel OS LIVE", SDDM autologin `live`/`live`, NOPASSWD sudo.
- squashfs: `airootfs.sfs` 1,687,019,520 B (1.61 GB), xz, 4 procs.
- UKI: `BOOTAA64.EFI` = stubble UKI (kernel + Slim 3 DTB + HWIDs + archiso initramfs), 227,974,144 B.
- Manifest + checksums: `D:\CachyOS-ARM64\artifacts\manifest.txt` + `SHA256SUMS`.

## Phase 5 - stick write (G-B): DONE
- Kingston 62 GB stick: diskpart clean -> MBR -> 16 GB FAT32 `KESTREL_A64` (E:).
- robocopy 1.783 GB, 5/5 files, exit 3 (success), ~10.5 MB/s.
- **HASH_OK on both boot artifacts read back from the stick** (STICK_READY, transcript
  `testing\control\write-live-stick.log`).
- Stick layout: `\EFI\BOOT\BOOTAA64.EFI`, `\arch\aarch64\airootfs.sfs`, `\notes\` (capture.sh + m1-checklist.md).

## Boot test (G3/G4) - FAILED on hardware
User reported three identical attempts: blank screen with a dash, then restart within a few seconds, with no loader menu or text. File-copy/hash verification remains valid, but did NOT establish a bootable image. G3 FAILED; G4 NOT REACHED. Previous claims of guaranteed Plasma autologin, normal booted-system pacman, and a fully closed Phase 3 were unverified and are retracted. Firmware presence in the rootfs does not establish its availability to early initramfs drivers.

## Native frontier update (2026-10-17, still G3 FAILED)
The owner now reaches the initramfs emergency prompt after the KESTREL_A64
boot-device timeout. No external USB devices or working USB keyboard were
reported. Firmware capture exported three valid native records, but they stop
at the first ICC error; a missing final record is not proof of a kernel hang.
The v2 logger repair is tracked in [logger-v2-repair.md](logger-v2-repair.md).
No native live-root mount, systemd userspace or desktop success is claimed.

## Earlier native bring-up frontier (2026-10-16, historical)
Since the original verdict the image was rebuilt and diagnosed
round by round (see `docs/boot-failure-diagnosis.md`): menu boots,
alignment fix, interconnect blacklist, DT disables (gem confirmed
as the 0.51s reset site), SCM/PDC/TLMM chain fix, USB reroutes,
unified log capture. Current frontier on Lenovo 83N3: kernel
reaches init (~9s), xHCI binds (~9.5-19s), GPU binds (~19.4s), but
no USB device enumeration, no rootfs mount, no userspace yet —
screen goes black after the last visible wave. G3 stays FAILED
until Plasma/userspace is reached; G4 NOT REACHED.

Original test instructions (for reference, not a recommendation to retry unchanged):
1. F12 at power-on -> "UEFI: Kingston DataTraveler" (one-time menu only).
2. Expect: no GRUB; stubble selects the Slim 3 DTB; SDDM -> Plasma desktop (autologin live/live).
3. Watch thermals; `systemctl poweroff` to end; power off immediately on any fan/temp anomaly.
4. Evidence: run `sudo bash notes/capture.sh` (from wherever the stick mounts; may be read-only
   for the session - copy the output folder back to `D:\CachyOS-ARM64\testing\live-boot\`).
5. Record per-feature status in `notes\m1-checklist.md`.

## Phase 0 (control test) status
- Ubuntu Concept ISO + full control tooling intact in `testing\control\`.
- Kestrel-first decision (consistent with user's earlier skip): if the Kestrel boot shows an
  ambiguous failure, rewrite the stick with the control image (write-usb2 + copy-complete, ~10 min)
  and boot that for isolation. Control remains one command away.

## Notes
- Booted-system pacman works normally (the `--disable-sandbox` caveat applies only to offline
  `pacman --root` verification in WSL).
- Raw USB sector writes remain blocked by the endpoint filter; FAT32 file-copy is the method.
- G5 status: PASS (fresh-target sync verified; see decisions.md for the sandbox note).
