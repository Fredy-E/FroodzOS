# FroodzOS 0.1.0-dev.7 "Maverick" — the internal disk is visible (read-only), sound firmware read straight from Windows (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick. The internal disk is now visible to the live system, **read-only**; nothing in this image writes to it. It follows `0.1.0-dev.6`.
Build id `maverick-public-dev-20261123.1`.

## What is new since 0.1.0-dev.6
- **The internal NVMe disk now shows up.** The boot image of the first two entries (`froodzos-maverick-dspN2.efi`) enables the PCIe controller of the internal drive and removes the one
  GPIO property (`wake-gpios` of the controller node) that is repeated on its root-port child. In dev.5 an image that only enabled the controller crashed the kernel (a NULL pointer in
  the GPIO core) and took Wi-Fi down with it; the repeated property was the suspected cause. It was a theory, not proven: it is now known only that this boot image worked on the laptop
  in two owner boots (below). The PCIe link comes up at Gen4 x4 and the disk appears with its four partitions.
- **Sound firmware is read straight from your Windows partition.** `fz-sound-setup` already looked at the Windows partition first; with the disk visible it now finds it, mounts it
  read-only and copies the six audio firmware files into memory. **You no longer need to copy a folder to the stick** (the `FroodzOS-firmware` folder still works as a fallback, for
  example when Windows is encrypted with BitLocker, which cannot be read).
- **The read-only rule for the internal disk now works.** The rule in dev.5 and dev.6 tried to set the disk read-only through a sysfs file the kernel does not allow writing
  ("Permission denied" in the owner log), so in those releases the drive was hidden from the desktop but not read-only. That was harmless while the drive was invisible. The rule now runs
  `blockdev --setro` on the disk and on every partition and keeps hiding the drive from the desktop's mount offer. Measured on the laptop: read-only flag 1 on the disk and all four partitions,
  and zero write operations to the disk during the boot.
- Library updates from a full system upgrade (`libseccomp`, `at-spi2-core`/`libatk`); no package added or removed. Version strings `0.1.0-dev.7`.

## What you need for sound
Windows must still be installed on the internal disk, with the Qualcomm audio driver (it comes with the normal Windows driver updates; the April 2026 version was the one tested), and not
encrypted with BitLocker. Boot the **second** entry ("with sound setup"): after the desktop is up, the sound card appears by itself about a minute and a half after power-on.
Or boot the first entry, open Konsole and run `sudo fz-sound-setup`, then `speaker-test -c 2 -t wav -l 1`. If "Front Left" comes from your right side, run `fz-swap-lr`.
If the internal disk cannot be used, copy the folder `qcsubsys_ext_adsp8380...` from `C:\Windows\System32\DriverStore\FileRepository\` into a folder `FroodzOS-firmware` on the stick (see `FIRMWARE.md`).

## What works (tested)
**Tested on the laptop (2026-11-23), two owner boots:** the boot image of this release (identical file) with (a) the previous root and (b) the root of this release (identical file), from a
private test stick, with the second-entry kernel options (`fz_sound=1`; the stick menu used a 3 GB RAM overlay and a differently named root folder). In both: the desktop started, no kernel
oops or warning, the internal disk appeared (`nvme0n1`, four partitions), Wi-Fi associated and stayed up, `fz-sound-setup` reported "source: Windows DriverStore on /dev/nvme0n1p3 (mounted read-only)",
staged the six files, the audio DSP went to running and the sound card and speaker sink appeared with no typing. In the second boot (the release root) the owner also reported sound and Wi-Fi good,
and the log shows read-only flag 1 on the disk and its partitions and no writes to the disk.
**The released image itself was tested only in an emulator** (QEMU, see `maverick-public-dev-20261123.1.json`); it was not written to a stick and booted on the laptop. A second emulator run with an emulated NVMe disk confirmed that the read-only rule marks the disk and its partitions read-only, that a write is refused and that the disk is hidden from the desktop.

## What does not work or is unverified
- **The internal disk is not hidden from other tools**, only from the desktop's mount offer. The read-only flag is set by a udev rule when the disk appears, so there is a moment of a fraction of a second
  before it is applied. Do not mount or write to the internal disk yourself.
- **Windows in BitLocker or hibernated "fast startup" states:** an encrypted partition cannot be read; a read-only mount of a dirty NTFS volume works but may show "Correct links count" kernel messages (they are fixed in memory only).
- **Left and right can come out reversed on some boots** after the sound set-up (cause not found); `fz-swap-lr` swaps them.
- **No GPU acceleration** (software rendering); USB-C display output and alternate modes are not claimed (the display driver is still disabled).
- A memory-bandwidth monitor driver (`bwmon`) fails to load its table. **Wi-Fi does not recover after suspend and resume**; suspend and resume are not
  claimed. Touchpad gesture quality is unconfirmed.
- RAR is extract-only. LibreOffice layout fidelity varies. The browsers (Helium, Zen) are unmodified third-party releases.
- Browsers need unprivileged user namespaces; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- Wine, Waydroid and QEMU are not in this build. Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.7-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu). Entry 1 is the plain image, entry 2 runs the sound set-up automatically after boot,
   entry 3 is the dev.2 style boot with the user-space touchpad driver (its boot image does not enable the internal disk). Default account: user `live`, password `live`. The live system keeps nothing after power off.

## Firmware, legal, source
No firmware is included; the sound set-up copies firmware that is already on your own Windows partition (or that you supply) into memory only (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose. Although the internal disk is set read-only, keep a backup of anything important on it before trying this.
