# FroodzOS 0.1.0-dev.2 "Maverick" — development image with the first file handlers (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev` (the first development image).

## What is new
- **First file handlers (Phase 1 of the main goal):** archives and disk images (Ark, 7zip, unrar, unzip/zip, cabextract, lhasa, unshield, plus
  squashfs, EROFS, FAT, exFAT, NTFS and mtools utilities); documents and e-books (Okular for PDF/EPUB/DjVu, **LibreOffice** for
  `.docx` `.xlsx` `.pptx` and OpenDocument); images (Gwenview with HEIF/AVIF/JPEG XL plugins); media (Haruna, mpv, Elisa); text (Kate);
  and the **Falkon** web browser. Inventory, licences and limits: `docs/compat/HANDLERS-PHASE1.md`.
- **The system was upgraded** to the current Arch Linux ARM packages (229 existing packages updated; 150 added; 742 in total).
- The handler list and the extension catalogue (372 extensions) are in the repository; the catalogue is a plan.

## What works (tested)
Everything in the previous release (desktop, Wi-Fi, keyboard, touchpad in basic mouse mode) was tested on the laptop **before this upgrade**.
**This build was booted only in an emulator** (it reaches the multi-user state, the touchpad driver self-test passes, packages and branding
checks pass). **None of the new handlers has been tested on real sample files on the laptop**; treat them as installed, not verified.

## What does not work or is unverified
- Brightness keys change the on-screen indicator, not the panel brightness. Battery level and power management are not working or not verified.
  Audio, camera, USB-C power delivery, suspend and GPU acceleration are not claimed.
- RAR is **extract-only** (the UnRAR licence forbids building a RAR compressor). HEIC may need a patent-encumbered decoder.
- LibreOffice layout fidelity varies; fonts are substituted. Falkon is a young browser; not every site works.
- Wine (Windows `.exe`), Waydroid (Android `.apk`) and QEMU are **not** in this build.
- Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.2-maverick-arm64-83n3.img.zst` (2.1 GB raw image).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu), choose the first entry. Default account: user `live`, password `live`.
   The second entry boots without the touchpad driver.

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package; not affiliated with Arch Linux, Arch Linux ARM, CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document
Foundation or Canonical. Firefox is not included. Original code is GPL-2.0-or-later. Source: this repository at the tag and the written
offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and open points: `RIGHTS-REVIEW.md` (addendum for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
