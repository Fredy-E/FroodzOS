# FroodzOS 0.1.0-dev.4 "Maverick" — sound-ready boot image, 10 second shutdown and a clean stick (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick; it does not touch the internal disk. It follows `0.1.0-dev.3`.
Build id `maverick-public-dev-20261120.2`.

## What is new since 0.1.0-dev.3
- **Both speakers, in the device tree.** The laptop has two WSA884x speaker amplifiers on one SoundWire bus, but they do not share a reset line:
  gpio12 of the audio pin controller releases the left amplifier, gpio13 the right one. The upstream-derived board file used gpio12 for both, so the right
  speaker never came out of reset. The first boot entry now carries a device tree that moves the right amplifier's reset to gpio13
  (`builder/public-image/fz-dtb-fixup.py --wsa-right-gpio13`, test in `tests/test_dtb_fixup.py`), and removes the two DisplayPort links of the sound card
  that can never complete while the display driver is disabled (`--sound-nodp`). Owner test on the laptop (2026-11-20, same boot image, private stick
  and this laptop's own audio firmware): left, right and both speakers play, from the start of the boot, with no helper service.
  `builder/public-image/build-sound-uki.sh` rebuilds that boot image from the base image.
- **Sound userspace is in the root:** PipeWire with the ALSA plugin, PulseAudio compatibility, the Plasma volume applet, a board UCM profile for this
  card (speakers, headphones, headset and internal microphones) and the Romulus topology link the card needs.
- **Shutdown takes about 10 seconds instead of more than 90.** `iio-sensor-proxy` waited for a sensor registry that does not exist and ignored the stop
  signal; NetworkManager and the smart log now have short stop limits.
- **A clean stick after power-off.** The new `fz-bootmnt-ro` service remounts the boot stick read-only at shutdown, so Windows does not ask to repair it
  (the FAT "not properly unmounted" flag stays clear). It never touches PID 1 or systemd, does nothing when the image is not running from a stick,
  and cannot block the shutdown.
- `fz-kexec-uki --exec` now asks for `--i-accept-a-black-screen` (the arm64 kernel hand-over loses the framebuffer).
- A full system upgrade of the root (version strings `0.1.0-dev.4`).

## What works (tested)
**Tested on the laptop (2026-11-20), owner test:** the first-entry boot image of this release (identical file) with the root of this release family
(r12 and then r13, the previous build and this one differ only by the shutdown service; the released r13 root is the one tested last) from a private test
stick that also supplied this laptop's own audio firmware: both speakers, battery, native touchpad, Wi-Fi, 10 s shutdown, stick left clean.
**The released image itself was tested only in an emulator** (QEMU, see `maverick-public-dev-20261120.2.json`); it was not written to a stick and booted
on the laptop. Because the released image contains no firmware and no ADSP start-up script, **it does not start the audio DSP and shows no sound card**.

## What does not work or is unverified
- **No sound out of the box.** The parts are in place (device tree, topology, UCM profile, PipeWire) but the audio DSP must be started with this
  machine's own firmware, which the image does not contain: `FIRMWARE.md`. The sound start-up helper used in the test is part of the private stick
  add-ons and is not shipped.
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
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.4-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
3. Write the raw image to a USB stick of at least 4 GB with `dd` or a raw-image writer (Rufus in DD mode, balenaEtcher).
   **This erases the whole stick. Double-check the target device.**
4. Boot the laptop from the stick (firmware boot menu), choose the first entry. Default account: user `live`, password `live`.
   The second entry is the dev.2 style boot with the user-space touchpad driver. The live system keeps nothing after power off unless you set up
   the optional persistence (`fz_persist=1`, see the dev.3 notes).

## Firmware, legal, source
No firmware extracted from a Windows installation is included (`FIRMWARE.md`). Based on unmodified Arch Linux ARM packages plus one
self-built kernel package, and the unmodified Helium (GPL-3.0) and Zen Browser (MPL-2.0) releases; not affiliated with Arch Linux, Arch Linux ARM,
CachyOS, Mozilla, Qualcomm, Lenovo, Microsoft, The Document Foundation, Canonical, Helium or Zen. Mozilla Firefox is not included. Original code is
GPL-2.0-or-later. Source: this repository at the tag and the written offer in `SOURCE-OFFER.md`; package list: `pkglist.tsv`; review notes and
open points: `RIGHTS-REVIEW.md` (addenda for this build).

## Use at your own risk
Development software with no warranty. Do not use it as your only operating system or on data you cannot lose.
