# FroodzOS 0.1.0-dev.5 "Maverick" — sound set-up from your own firmware, read-only internal disk (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev.4`.
Build id `maverick-public-dev-20261120.5`.

## What is new since 0.1.0-dev.4
- **Sound set-up from the image: `fz-sound-setup`.** dev.4 had the speaker device tree, PipeWire and the card profile, but no way to start the audio DSP,
  so no sound card appeared. The new command copies six audio firmware files that you supply (see below) into the live system's memory, restarts the audio DSP
  and the audio session, and reports the sound card and the speaker sink. Nothing is written to the stick or to Windows, and nothing leaves the machine; the files
  vanish at power-off. Run it from the desktop: application menu ("Set up sound (laptop firmware)") or `sudo fz-sound-setup`. `--dry-run` shows what it would do.
  (A kernel option `fz_sound=1` and the second boot entry run it automatically, but that entry does not reach the desktop at present, see below.)
- **The internal drive is read-only and hidden.** A udev rule marks the internal NVMe drive read-only and keeps it out of the desktop's mount offer, so a live
  session cannot write to your Windows installation by accident. (The shipped device tree does not make the internal drive visible at all yet, see below.)
- **A second boot entry** "with sound setup" (the first entry is unchanged: same boot image as dev.4). **Do not use it yet: it does not reach the desktop on the laptop, see below.**
- Development tools in the repository: `fz-dtb-fixup.py --enable-nvme` (experimental, not used by this release, see below) and a hook in
  `builder/public-image/build-sound-uki.sh` for extra fix-up rules.
- A full system upgrade of the root (version strings `0.1.0-dev.5`).

## What you need for sound
The image contains **no** firmware (`FIRMWARE.md`). You need the audio firmware of **your own** laptop, from your own Windows installation:
1. In Windows, open `C:\Windows\System32\DriverStore\FileRepository\` and copy the whole folder whose name starts with `qcsubsys_ext_adsp8380`
   (use one version folder; the April 2026 driver was the one tested) into a new folder `FroodzOS-firmware` on the USB stick (the stick shows up as a
   normal drive in Windows). Do not share the copied files.
2. Boot the **first** entry, wait for the desktop, open Konsole, run `sudo fz-sound-setup` (read its messages), then `speaker-test -c 2 -t wav -l 1`.
   Left and right may be swapped (see below).

## What works (tested)
**Tested on the laptop (2026-11-22), owner test:** the boot image of this release (identical file) with the root of this release (identical file) from a private test stick
that has the firmware folder and extra add-ons: `fz-sound-setup` found the six files in the stick folder, restarted the audio DSP and the sound card appeared
(`X1E80100-LENOVO-Ideapad-3`); the stick was left clean after shutdown. Left, right and both speakers had been heard in the dev.4 test with the same device tree and
firmware but with a private start-up script; **audible output through `fz-sound-setup` itself is not confirmed in this record.**
A second owner test (2026-11-22, same boot image and root, first-entry kernel options, no firmware stick add-ons): the desktop started, `sudo fz-sound-setup` from the desktop worked and sound played on both speakers, **but left and right were swapped**.
**The released image itself was tested only in an emulator** (QEMU, see `maverick-public-dev-20261120.5.json`); it was not written to a stick and booted on the laptop.

## What does not work or is unverified
- **The second boot entry (kernel option `fz_sound=1`) does not reach the desktop** on the laptop: in 5 of 5 owner tests on 2026-11-22 the login screen's display server stopped and no desktop session started; the same system without that option starts the desktop. Cause not yet found. Use the first entry and run `sudo fz-sound-setup` from the desktop.
- **Left and right speaker channels are swapped** after `fz-sound-setup` in the first-entry test (cause not yet found; an earlier private start-up script gave the right order).
- **The internal drive is invisible to the live system** (the shipped device tree keeps its PCIe controller disabled), so `fz-sound-setup` cannot read the firmware
  from your Windows partition directly; copy it to the stick as above. An experiment that enables the controller (`--enable-nvme`) trained the link and then crashed the
  kernel in the GPIO core (NULL pointer in `gpio_shared_add_proxy_lookup`) and lost Wi-Fi and sound on the 83N3; it is **not** part of this image.
- `fz-sound-setup --dry-run` is only a true dry run while it still has files to copy; if the firmware is already staged it goes on to restart the audio DSP (known issue, to be fixed in a later build).
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
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.5-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu). Entry 1 is the plain image, entry 2 is meant to run the sound set-up automatically but does not reach the desktop at present (use entry 1),
   entry 3 is the dev.2 style boot with the user-space touchpad driver. Default account: user `live`, password `live`. The live system keeps nothing after power off.

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
