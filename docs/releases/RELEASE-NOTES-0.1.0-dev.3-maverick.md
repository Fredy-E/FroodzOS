# FroodzOS 0.1.0-dev.3 "Maverick" — development image with a native touchpad, working battery data and a 15 second boot (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev.2`.
Build id `maverick-public-dev-20261118.2`.

## What is new since 0.1.0-dev.2
- **Native touchpad.** The board's device tree declared the wrong touchpad (a Goodix at I2C address 0x5d, without an interrupt). The real one is a
  FocalTech FTCS0038 at 0x38 whose interrupt is TLMM GPIO 19. The first boot entry now uses a device tree patched for it
  (`builder/public-image/fz-board-touchpad.py`), so the kernel's `i2c_hid_of` / `hid-multitouch` drivers run the pad. The user-space polling driver
  stays as the fallback in the second entry and steps aside when the kernel driver owns the pad.
- **Battery works:** level, charge state and USB-C power data (qcom battmgr). The audio DSP starts in "attached" mode without any vendor firmware once
  the device tree no longer asks for the unavailable memory-bus vote (`builder/public-image/fz-dtb-fixup.py`, `docs/hardware-dsp-battery.md`).
  Also fixed in the device tree: a USB port that failed to bind (it now runs as USB 2.0) and serial-engine votes of the same kind.
- **Boot in 15 seconds instead of 43.** `ldconfig` ran on every boot and took 28 s of the 36 s userspace boot; the cache is now built into the image.
- **Network time** is on, the regulatory database (`wireless-regdb`), `rtkit` and ALSA tools are installed.
- **Smart log fixes:** the battery is found by type (it reported "no battery" before); the self-test noise is gone.
- **Opt-in extras, off by default:** `fz_autorun=1` runs `FroodzOS-addons/autorun.sh` from the boot stick once after boot (for private add-ons and
  unattended checks); `fz_persist=1` with an ext4 partition labelled `FROODZ_PERSIST` makes the home directory and saved Wi-Fi networks persistent
  (`mkfs.ext4 -L FROODZ_PERSIST /dev/sdXN`; whoever holds the stick can read what is stored there).
- **Live-fix tools** (about 10 MB): `kexec-tools`, `dtc`, `efibootmgr`, `git`, `openssh`, `evtest`, `strace`.

## What works (tested)
**Tested on the laptop (2026-11-18), owner test:** the first-entry boot image of this release (identical file) with the previous build of this
root (r9: same build script, without the persistence service and the PowerDevil environment file), from a private test stick: native touchpad
bound and working, keyboard, Wi-Fi, battery (92 to 100%, charging), USB 3 devices, 4 of 4 USB controllers, 0 failed units, 0 crashes, userspace boot
9.6 s. Gesture quality of the touchpad is not confirmed. **The released image itself was tested only in an emulator** (QEMU: boots to the login,
identity, pruning and handler checks pass; see `maverick-public-dev-20261118.2.json`); it was not written to a stick and booted on the laptop before
release. The persistence option is new and was only dry-run tested; it is off in the released menu.

## What does not work or is unverified
- **No sound** (needs the audio DSP started with this machine's own firmware, which the image does not contain: `FIRMWARE.md`).
- **No GPU acceleration** (software rendering); USB-C display output and alternate modes are not claimed (the display driver is still disabled).
- A memory-bandwidth monitor driver (`bwmon`) fails to load its table; 11 devices stay deferred (sound parts and bwmon). **Wi-Fi does not recover
  after suspend and resume**; suspend and resume are not claimed.
- RAR is extract-only. LibreOffice layout fidelity varies. The browsers (Helium, Zen) are unmodified third-party releases.
- Browsers need unprivileged user namespaces; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- Wine, Waydroid and QEMU are not in this build. Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.3-maverick-arm64-83n3.img.zst` (1.9 GB raw image; the download is 1.63 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu), choose the first entry. Default account: user `live`, password `live`.
   The second entry is the dev.2 style boot with the user-space touchpad driver. The live system keeps nothing after power off unless you set up
   the optional persistence above.

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
