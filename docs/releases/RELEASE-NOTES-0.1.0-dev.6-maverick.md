# FroodzOS 0.1.0-dev.6 "Maverick" — the sound set-up starts by itself after boot, left/right swap command (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev.5`.
Build id `maverick-public-dev-20261122.1`.

## What is new since 0.1.0-dev.5
- **The second boot entry now reaches the desktop.** In dev.5 the entry with the kernel option `fz_sound=1` never got to the desktop on the laptop (5 of 5 boots: the
  login screen's display server stopped). In dev.6 the sound set-up is no longer a unit inside the boot sequence: a timer (`fz-sound-setup.timer`) starts it once, about
  75 seconds after boot, and only with `fz_sound=1`. In one owner boot of this build the desktop started and the set-up ran by itself (details below). The cause of the dev.5
  problem was never proven, so this is a change that worked once, not a proven fix.
- **`fz-sound-setup --dry-run` is a true dry run** now, also when the firmware files are already staged (in dev.5 it went on to restart the audio DSP).
- **New command `fz-swap-lr`** swaps the left and right speaker channels (a WirePlumber rule in your own config folder); run it again to undo it. On some boots the channels come
  out reversed and on others not (cause still not found).
- A full system upgrade of the root: 35 packages have newer versions (gnutls, gpgme, harfbuzz, hwloc, libmspub and the VLC package group); no package was added or removed.
  Version strings `0.1.0-dev.6`. The boot loader and the kernel images are unchanged.

## What you need for sound
The image contains **no** firmware (`FIRMWARE.md`). You need the audio firmware of **your own** laptop, from your own Windows installation:
1. In Windows, open `C:\Windows\System32\DriverStore\FileRepository\` and copy the whole folder whose name starts with `qcsubsys_ext_adsp8380`
   (use one version folder; the April 2026 driver was the one tested) into a new folder `FroodzOS-firmware` on the USB stick (the stick shows up as a
   normal drive in Windows). Do not share the copied files.
2. Boot the second entry ("with sound setup"): after the desktop is up, the sound card appears by itself about a minute and a half after power-on. Or boot the first entry,
   open Konsole and run `sudo fz-sound-setup` (read its messages). Then `speaker-test -c 2 -t wav -l 1`. If "Front Left" comes from your right side, run `fz-swap-lr`.

## What works (tested)
**Tested on the laptop (2026-11-23), one boot, owner test:** the boot image of this release (identical file) with the root of this release (identical file) from a private test
stick that has the firmware folder: with the second-entry kernel options (`fz_sound=1`) the desktop started on its own, the timer ran `fz-sound-setup` about 75 seconds after boot,
it staged all six files from the stick folder, the audio DSP went to running, and the sound card (`X1E80100-LENOVO-Ideapad-3`) and the built-in speaker sink appeared with no typing.
The private stick menu used a 3 GB RAM overlay instead of 2 GB and a root folder of another name; the kernel options are otherwise those of the released second entry.
This record does not say that sound was audible on that boot; sound after `fz-sound-setup` was heard in earlier owner tests (dev.5, many boots: both speakers, left/right order varied).
**The released image itself was tested only in an emulator** (QEMU, 306.6 s, see `maverick-public-dev-20261122.1.json`); it was not written to a stick and booted on the laptop.

## What does not work or is unverified
- **The second boot entry was verified on one boot only.** In dev.5 the same option failed 5 of 5 times; if it fails for you, use the first entry and run `sudo fz-sound-setup`.
- **Left and right can come out reversed on some boots** after the sound set-up (cause not found); `fz-swap-lr` swaps them.
- **The internal drive is invisible to the live system** (the shipped device tree keeps its PCIe controller disabled), so `fz-sound-setup` cannot read the firmware
  from your Windows partition directly; copy it to the stick as above. An experiment that enables the controller (`--enable-nvme`) trained the link and then crashed the
  kernel in the GPIO core and lost Wi-Fi and sound on the 83N3; it is **not** part of this image.
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
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.6-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu). Entry 1 is the plain image, entry 2 runs the sound set-up automatically after boot (needs the `FroodzOS-firmware` folder),
   entry 3 is the dev.2 style boot with the user-space touchpad driver. Default account: user `live`, password `live`. The live system keeps nothing after power off.

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
