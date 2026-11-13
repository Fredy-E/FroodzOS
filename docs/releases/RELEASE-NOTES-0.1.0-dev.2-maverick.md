# FroodzOS 0.1.0-dev.2 "Maverick" — development image with file handlers, a working desktop session and two new browsers (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev` (the first development image).
Build id `maverick-public-dev-20261113.4`.

## What is new since 0.1.0-dev
- **File handlers (Phase 1 of the main goal):** archives and disk images (Ark, 7zip, unrar, unzip/zip, cabextract, lhasa, unshield, plus
  squashfs, EROFS, FAT, exFAT, NTFS and mtools utilities); documents and e-books (Okular, **LibreOffice** for `.docx` `.xlsx` `.pptx` and
  OpenDocument); images (Gwenview with HEIF/AVIF/JPEG XL plugins); media (Haruna, mpv, Elisa); text (Kate). Inventory, licences and limits:
  `docs/compat/HANDLERS-PHASE1.md`. A "Mount disk image" action for `.img` and `.iso` files is included but was not tested.
- **Two browsers:** **Helium** (Chromium based, default) and **Zen Browser** (Firefox based), both unmodified official releases.
- **The desktop session works with the upgraded system.** The Plasma 6.8 upgrade had broken the bounded graphics session (KWin rejects the old
  `KWIN_COMPOSE=Q` setting); fixed in the boot images. The session no longer ends after 180 seconds (the temperature, display and session
  checks still stop it).
- **Brightness:** the panel now starts at full brightness and the keys change the real brightness.
- **Smart log:** `fz-smartlog` records bounded facts about the whole session to the boot stick (`Logs/` folder) with an automatic summary, and a
  "Save a diagnostic log now" launcher. Details: `builder/public-image/README.md`.
- **A smaller image:** other chips' firmware, unused translations, documentation and development files were removed (1.5 GB less
  uncompressed). The system was upgraded to the current Arch Linux ARM packages (742 packages).
- The extension catalogue (372 extensions) and the roadmap mapping are in the repository; the catalogue is a plan.

## What works (tested)
**Tested on the laptop (2026-11-13):** the same root file system and boot images, from a test stick, booted to the desktop; the owner reported both
boot entries as normal. The smart log shows Wi-Fi connected, brightness 4095 of 4095, the graphics session running without a deadline, no crash
and no failed service. Earlier builds of this series ran the session for 20 minutes and more, and opened archive, image, document and audio sample
files. **The released image itself was tested in an emulator** (boot reaches the multi-user state, package and branding checks pass); the only
differences from the tested stick are the boot menu and the packaging. Helium and Zen are installed; their use was not individually verified.

## What does not work or is unverified
- **Battery level, charging state and power management do not work** (the battery shows 0%). The processor that supplies this data (the ADSP) does
  not start: the device tree used for this laptop keeps the memory-bus part it needs disabled (probing it resets the machine), and the image has no
  firmware for this exact machine (`FIRMWARE.md`). **No sound** for the same reason. The cause and the next steps are in the repository history.
- No GPU acceleration (software rendering). Camera and USB-C power delivery are not claimed. The touchpad works in basic mouse mode only.
- **Wi-Fi does not recover after suspend and resume**; suspend and resume are not claimed.
- RAR is **extract-only** (the UnRAR licence forbids building a RAR compressor). HEIC may need a patent-encumbered decoder.
- LibreOffice layout fidelity varies. The browsers are third-party releases: their trademark and artwork terms were not reviewed separately.
- Browsers need unprivileged user namespaces for their sandbox; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- The standalone `mpv` fix is unverified. Wine (Windows `.exe`), Waydroid (Android `.apk`) and QEMU are **not** in this build.
- Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.2-maverick-arm64-83n3.img.zst` (about 2.2 GB raw image; the download is 1.6 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu), choose the first entry. Default account: user `live`, password `live`.
   The second entry boots without the touchpad driver. The live system keeps nothing after power off.

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
