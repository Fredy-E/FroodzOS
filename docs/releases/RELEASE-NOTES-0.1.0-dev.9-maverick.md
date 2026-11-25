# FroodzOS 0.1.0-dev.9 "Maverick" — Waydroid keeps its Android image between boots, no more automatic suspend (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick. The internal disk is visible to the live system, **read-only**; nothing in this image writes to it. It follows `0.1.0-dev.8`.
Build id `maverick-public-dev-20261125.2`.

## What is new since 0.1.0-dev.8
- **Waydroid's Android image now survives a reboot.** In dev.8 only `fz-waydroid init` connected the persistent partition to Waydroid's data folder, so a plain `waydroid init` (or a
  fresh boot followed by `waydroid session start`) used the stick's RAM overlay and downloaded the Android image again (about 800 MB) every boot. With the kernel option `fz_persist=1` and a
  `FROODZ_PERSIST` partition, the persistent `waydroid` folder is now bound over `/var/lib/waydroid` at boot, before the Waydroid service starts. The first time you still run
  `sudo waydroid init` once (or `sudo fz-waydroid init`); after that `waydroid session start` just works. Found in an owner boot of the dev.8 release candidate.
- **Suspend and hibernate are switched off.** In an owner boot, Plasma's idle handling put the laptop to sleep after about 40 minutes and the Wi-Fi chip did not come back
  (`ath12k ... failed to resume core: -110`, a kernel warning in `mac80211`; the already known "Wi-Fi after resume" problem). The power defaults shipped until now used an old Plasma setting format
  that Plasma 6 ignores. The image now forbids suspend, hibernate and hybrid sleep in systemd, and the lid switch and idle action are ignored (closing the lid no longer suspends; the screen stays on).
  Remove `/etc/systemd/sleep.conf.d/90-froodzos-nosuspend.conf` and `/etc/systemd/logind.conf.d/90-froodzos-nosuspend.conf` to try suspend yourself.
- Owner check on the laptop of the dev.8 candidate (2026-11-25): the Windows partition opens in Dolphin read-only without a password and "New Folder" is greyed out; Android started and its window was shown; sound worked. Version strings `0.1.0-dev.9`; the boot images are unchanged.

## Android apps with Waydroid (experimental, since 0.1.0-dev.8)
Waydroid runs Android 13 in a container. **The Android image is not part of FroodzOS**; `waydroid init` downloads it (about 800 MB to 1 GB) from the Waydroid project's servers at your request, and there is no Google Play.
It needs a **persistent partition**: create a second partition on the stick (ext4, label `FROODZ_PERSIST`) and boot with `fz_persist=1`; without one, `sudo fz-waydroid init --ram` keeps the image in memory and loses it at power-off.
Steps: `sudo fz-waydroid check` (reports what is missing), `sudo waydroid init` once, then as the normal user `waydroid session start &` and `waydroid show-full-ui`. If the window does not appear, run
`sudo waydroid prop set persist.waydroid.multi_windows true`, restart the session and use `waydroid app launch com.android.settings`. `sudo fz-waydroid report` collects the state and Android's error lines into the journal.
Software rendering only (no GPU acceleration); camera and sensors are untested. Android prints cgroup warnings at start; they were harmless.

## What you need for sound
Unchanged from dev.7: Windows must still be installed on the internal disk with the Qualcomm audio driver and not encrypted with BitLocker. Boot the **second** entry ("with sound setup"): after
the desktop is up, the sound card appears by itself about a minute and a half after power-on. Or run `sudo fz-sound-setup` in Konsole, then `speaker-test -c 2 -t wav -l 1`.
If "Front Left" comes from your right side, run `fz-swap-lr`. Fallback: a `FroodzOS-firmware` folder on the stick (see `FIRMWARE.md`).

## What works (tested)
**Tested on the laptop (2026-11-25), owner boot of the dev.8 release candidate** (same boot image, same polkit, udev, Waydroid and sound content as this release; from a private test stick with `fz_sound=1`, `fz_persist=1`):
the desktop started, sound worked (Windows driver files read from the internal disk, sound card and speaker sink appeared with no typing), Dolphin opened the internal Windows partition read-only with no password prompt and creating a folder was refused,
Android 13 started (`waydroid init` downloaded the image because of the bug fixed above) and its window was displayed. Idle suspend then broke Wi-Fi, which led to the second change above.
**Not tested on the laptop:** the two changes of this release (the boot-time Waydroid bind and the disabled suspend) and the released image itself; both were checked only in an emulator (QEMU, see `maverick-public-dev-20261125.2.json`): it boots, the sleep and login settings are in place, the Android binder module loads, the Waydroid tools are present and `fz-waydroid init` refuses without persistence.

## What does not work or is unverified
- **Waydroid is experimental.** No GPU acceleration (software rendering, so Android is slow and heavy), the Android window can need the multi-window setting above, camera and sensors are untested, no Google Play, ARM64 Android apps only. It needs a persistent partition and several GB of free memory.
- **The internal disk is visible**; the read-only flag is set by a udev rule when the disk appears, so there is a moment of a fraction of a second before it is applied. Do not write to the internal disk yourself. Keep a backup of anything important on it.
- **Windows in BitLocker or hibernated "fast startup" states:** an encrypted partition cannot be read; a read-only mount of a dirty NTFS volume works but may show "Correct links count" kernel messages (fixed in memory only).
- **Suspend is not supported** (disabled, see above); the Wi-Fi chip does not recover from it.
- **Left and right can come out reversed on some boots** after the sound set-up (cause not found); `fz-swap-lr` swaps them.
- **No GPU acceleration**; USB-C display output and alternate modes are not claimed (the display driver is still disabled).
- A memory-bandwidth monitor driver (`bwmon`) fails to load its table. Touchpad gesture quality is unconfirmed. `iio-sensor-proxy` fails to start (no sensors).
- RAR is extract-only. LibreOffice layout fidelity varies. The browsers (Helium, Zen) are unmodified third-party releases. Browsers and Waydroid need unprivileged user namespaces; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- Wine (Windows apps) is not in this build; it is not in the Arch Linux ARM repositories. QEMU is not in this build. Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.9-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
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
