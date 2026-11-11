# FroodzOS 0.1.0-dev "Maverick" — development image for the Lenovo IdeaPad Slim 3 15Q8X10 (83N3)

**This is an early development image, not a finished distribution.** It is for one laptop only: the Lenovo IdeaPad Slim 3 15Q8X10
(83N3, Snapdragon X1-26-100). It will not boot on other machines. Use it from a USB stick; it does not touch the internal disk.

## What works (tested on one 83N3)
Boots to a KDE Plasma desktop (software rendering), keyboard, Wi-Fi, external mouse, and the built-in **touchpad in basic mouse mode**
(move, click, scroll; no tap-to-click or gestures yet).

## What does not work or is unverified
- Brightness keys change the on-screen indicator but **not** the panel brightness.
- Battery level, charging state and power management: not working or not verified.
- Audio, camera, USB-C power delivery, suspend, GPU acceleration: not claimed.
- Boot loader and kernel are unsigned: **Secure Boot must be off.** Laptop is untested with Secure Boot on.
- The exact release image (build `.2`) was booted in an emulator; the previous build `.1` (same kernel and boot files, root differs only
  by the removal of Firefox and Arch branding) was booted on the laptop.

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev-maverick-arm64-83n3-nofw.img.zst` (1.7 GB raw image).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu), choose the first entry. Default account: user `live`, password `live`.
   The second entry boots without the touchpad driver.

## Firmware
No Lenovo/Qualcomm firmware that was extracted from a Windows installation is included (it may not be redistributed). The image
contains the generic Arch Linux ARM `linux-firmware` packages for Qualcomm, Atheros and Realtek with their licences. See
`FIRMWARE.md`.

## Legal summary
Based on unmodified [Arch Linux ARM](https://archlinuxarm.org) packages (591 of 592) plus one self-built kernel package.
FroodzOS is independent and not affiliated with Arch Linux, Arch Linux ARM, CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft or
Canonical. Firefox is not included. Original code is GPL-2.0-or-later. Source code: this repository at the tag, and the written
offer in `SOURCE-OFFER.md`; package list with versions and licences: `pkglist.tsv`. Review notes and open points:
`RIGHTS-REVIEW.md`. Not legal advice.

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
