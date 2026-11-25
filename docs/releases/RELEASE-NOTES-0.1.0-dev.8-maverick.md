# FroodzOS 0.1.0-dev.8 "Maverick" — Android apps with Waydroid (experimental), the Windows disk opens read-only from the file manager (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick. The internal disk is visible to the live system, **read-only**; nothing in this image writes to it. It follows `0.1.0-dev.7`.
Build id `maverick-public-dev-20261125.1`.

## What is new since 0.1.0-dev.7
- **Android apps: Waydroid is installed (experimental).** The kernel already had the Android binder support; this release adds the `waydroid` package with `lxc`, `dnsmasq` and `libgbinder`
  from Arch Linux ARM, and a helper, `fz-waydroid`. On the laptop, Android 13 started completely (about 16 s) and its window showed on the Plasma desktop (owner test, 2026-11-25).
  `sudo fz-waydroid check` reports whether everything needed is there, `sudo fz-waydroid init` downloads the Android image (about 1 GB) from the Waydroid project's servers
  and keeps it on the persistent partition, `sudo fz-waydroid report` collects the state and Android's error lines into the journal. **The Android image is not part of FroodzOS and is not in
  this release**; it is downloaded by you, at run time, and there is no Google Play. Android needs a **persistent partition** (a second partition named `FROODZ_PERSIST` on the stick and the
  boot option `fz_persist=1`); without one, `fz-waydroid init --ram` keeps the 1 GB image in memory and loses it at power-off. The released image has no such partition, so create one first.
  After `init`, as the normal user: `waydroid session start &`, then `waydroid show-full-ui`. If the full-screen window does not appear, run
  `sudo waydroid prop set persist.waydroid.multi_windows true`, restart the session and start an app (`waydroid app launch com.android.settings`): in the owner test this is what made the window appear.
  Android prints cgroup warnings during start; they were harmless.
- **The internal disk now shows in the file manager, read-only.** In dev.5 to dev.7 the drive was hidden from the desktop; that is **superseded**. It now appears in Dolphin's
  Devices panel, is **not mounted by itself**, and opens with one click. The read-only flag from dev.7 is unchanged (`blockdev --setro` on the disk and every partition by udev) and
  the desktop's own mount is forced to `ro,nosuid,nodev,noexec`. A polkit rule lets the person at the live session mount (not write, format or unmount other users' mounts) without a password,
  because the live system has no administrator prompt to answer.
- **A sound report for the left/right problem.** `fz-sound-setup` now writes a read-only channel report (sound-card devices, speaker mixer values, amplifier kernel lines, speaker positions)
  into its log, so that the next boot with reversed channels can be compared with a good one. It changes no behaviour.
- Version strings `0.1.0-dev.8`. The boot images are the same files as in dev.7.

## What you need for sound
Unchanged from dev.7: Windows must still be installed on the internal disk with the Qualcomm audio driver and not encrypted with BitLocker. Boot the **second** entry ("with sound setup"): after
the desktop is up, the sound card appears by itself about a minute and a half after power-on. Or run `sudo fz-sound-setup` in Konsole, then `speaker-test -c 2 -t wav -l 1`.
If "Front Left" comes from your right side, run `fz-swap-lr`. Fallback: a `FroodzOS-firmware` folder on the stick (see `FIRMWARE.md`).

## What works (tested)
**Tested on the laptop (2026-11-25), owner boots of the previous test root** (same Waydroid, udev and sound code, from a private test stick, internal disk visible): the desktop started with no kernel oops, sound and Wi-Fi worked,
`fz-waydroid check` reported READY, the Android image downloaded, Android booted completely and its window was displayed. The internal disk showed read-only flag 1 on the disk and all four partitions.
**Not tested on the laptop:** the passwordless read-only open from the file manager (the polkit rule) was added after that boot; **the released image itself was tested only in an emulator**
(QEMU, see `maverick-public-dev-20261125.1.json`): it boots, the Android binder module loads, the Waydroid tools are present, `fz-waydroid init` refuses without persistence, and with an emulated NVMe disk the read-only flag, the refused write and the "shown but not auto-mounted" udev properties are as described.

## What does not work or is unverified
- **Waydroid is experimental.** No GPU acceleration (software rendering, so Android is slow and heavy), the Android window can need the multi-window setting above, camera and sensors are untested, no Google Play, ARM64 Android apps only. It needs a persistent partition and several GB of free memory.
- **The internal disk is visible**; the read-only flag is set by a udev rule when the disk appears, so there is a moment of a fraction of a second before it is applied. Do not write to the internal disk yourself. Keep a backup of anything important on it.
- **Windows in BitLocker or hibernated "fast startup" states:** an encrypted partition cannot be read; a read-only mount of a dirty NTFS volume works but may show "Correct links count" kernel messages (fixed in memory only).
- **Left and right can come out reversed on some boots** after the sound set-up (cause not found); `fz-swap-lr` swaps them.
- **No GPU acceleration**; USB-C display output and alternate modes are not claimed (the display driver is still disabled).
- A memory-bandwidth monitor driver (`bwmon`) fails to load its table. **Wi-Fi does not recover after suspend and resume**; suspend and resume are not claimed. Touchpad gesture quality is unconfirmed.
- RAR is extract-only. LibreOffice layout fidelity varies. The browsers (Helium, Zen) are unmodified third-party releases. Browsers and Waydroid need unprivileged user namespaces; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- Wine (Windows apps) is not in this build; it is not in the Arch Linux ARM repositories. QEMU is not in this build. Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.8-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu). Entry 1 is the plain image, entry 2 runs the sound set-up automatically after boot,
   entry 3 is the dev.2 style boot with the user-space touchpad driver (its boot image does not enable the internal disk). Default account: user `live`, password `live`. The live system keeps nothing after power off, except what you put on a `FROODZ_PERSIST` partition.

## Firmware, legal, source
No firmware and no Android image are included; the sound set-up copies firmware that is already on your own Windows partition (or that you supply) into memory only (`FIRMWARE.md`), and `fz-waydroid init` downloads the Android image from the Waydroid project at your request. Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, Google, The Document Foundation, Canonical, the Waydroid project, Helium or Zen. Android is a trademark of Google LLC. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose. Although the internal disk is set read-only, keep a backup of anything important on it before trying this.
