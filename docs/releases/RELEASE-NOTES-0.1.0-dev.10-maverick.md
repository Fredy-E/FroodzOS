# FroodzOS 0.1.0-dev.10 "Maverick" — smart log v3: a flight recorder from the first boot line (Lenovo 83N3 only)

**Early development image, for one laptop only:** the Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
other machines. Use it from a USB stick. The internal disk is visible to the live system, **read-only**; nothing in this image writes to it. It follows `0.1.0-dev.9`.
Build id `maverick-public-dev-20261125.3`.

## What is new since 0.1.0-dev.9
- **Smart log v3.** The on-device flight recorder (`fz-smartlog`) was rewritten. It starts before `basic.target`, reads the kernel ring buffer from its first line, the journal, systemd, udev, network and power events, and writes
  one line of JSON per record into segment files that are flushed about once a second. `fz-smartlog status` shows where it writes and how much; the boot folder holds a `summary.txt`, snapshots on events and a heartbeat file (`alive.txt`).
  **Public default:** the recorder writes only these bounded basic streams into RAM (`/run/fz-smartlog`); nothing is written to your stick unless it carries the marker file used for the project's own test sticks. A watchdog restarts it if it hangs.
- **Record mode, only with the kernel option `fz_record=full`** (not in the public boot entries): the journal at debug level and kernel printk at maximum, **every terminal** (Konsole tabs, text consoles, ssh) recorded through `script`
  and rendered to a transcript, with each command, its exit code and its duration, when the terminal is closed; the UI journal, KWin state, a screenshot every 60 s (only with a graphical session and not while the screen is locked), Waydroid's Android log, bounded core dumps.
  Passwords and tokens are filtered on a best-effort basis; **treat such logs as private**: they can contain what you typed and what was on your screen. They stay on your stick (or in RAM) and are never uploaded.
- `fz_debug=` kernel debug profiles (`fz-debug`), the documented kernel command line (`docs/smartlog/KERNEL-CMDLINE.md`) and the tools `fz-digest.py` (summary of a boot folder), `fz-sigscan.py` (known failure signatures), `fz_redact.py` and a new CI gate `tools/check-log-leaks.py` in the repository.
- Core dumps are now bounded (`Storage=none`, the backtrace goes to the journal); before, they were unbounded in RAM. The screenshot tool `spectacle` was added to the image. Version strings `0.1.0-dev.10`; the boot images are unchanged.

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
**Tested on the laptop:** nothing of this release yet. The previous owner test (dev.8 candidate, 2026-11-25) covered the desktop, sound, read-only internal disk and Android start; suspend then broke Wi-Fi (disabled in dev.9).
**Emulator only (QEMU, see `maverick-public-dev-20261125.3.json`):** the released image boots to the multi-user target with the recorder running; in record mode the kernel stream starts at the first kernel line, the journal stream fills, a typed terminal command, its exit code and a masked fake password appear in the terminal stream (the fake secret is nowhere in the folder), size caps hold, and after a simulated power cut the already-written lines are readable. 248 unit tests pass.
**Not tested anywhere yet:** terminal recording inside Konsole, UI capture, screenshots and KWin dumps (they need the real desktop), Waydroid's Android log, the verbose boot on the laptop and its effect on boot time, a real power cut.

## What does not work or is unverified
- **Record mode is for the project's test sticks.** It slows the boot (verbose lines go to the screen), screenshots and terminal text are sensitive, and the terminal transcript is written when a terminal closes (a crash or power cut loses the open terminal's text, not the rest).
- **Waydroid is experimental.** No GPU acceleration (software rendering, so Android is slow and heavy), the Android window can need the multi-window setting above, camera and sensors are untested, no Google Play, ARM64 Android apps only. It needs a persistent partition and several GB of free memory.
- **The internal disk is visible**; the read-only flag is set by a udev rule when the disk appears, so there is a moment of a fraction of a second before it is applied. Do not write to the internal disk yourself. Keep a backup of anything important on it.
- **Windows in BitLocker or hibernated "fast startup" states:** an encrypted partition cannot be read; a read-only mount of a dirty NTFS volume works but may show "Correct links count" kernel messages (fixed in memory only).
- **Suspend is not supported** (disabled since dev.9); the Wi-Fi chip does not recover from it.
- **Left and right can come out reversed on some boots** after the sound set-up (cause not found); `fz-swap-lr` swaps them.
- **No GPU acceleration**; USB-C display output and alternate modes are not claimed (the display driver is still disabled).
- A memory-bandwidth monitor driver (`bwmon`) fails to load its table. Touchpad gesture quality is unconfirmed. `iio-sensor-proxy` fails to start (no sensors).
- RAR is extract-only. LibreOffice layout fidelity varies. The browsers (Helium, Zen) are unmodified third-party releases. Browsers and Waydroid need unprivileged user namespaces; the image sets `kernel.apparmor_restrict_unprivileged_userns=0`.
- Wine (Windows apps) is not in this build; it is not in the Arch Linux ARM repositories. QEMU is not in this build. Boot loader and kernel are unsigned: **Secure Boot must be off.**

## Get it
1. Download all assets. Verify: `gpg --import froodzos-release-public.asc`, compare the fingerprint
   `1432 DC7D B541 96FF 471E FD57 A558 604E 9E92 C7EA` with `docs/releases/SIGNING.md` in the repository,
   `gpg --verify SHA256SUMS.asc SHA256SUMS`, then `sha256sum -c SHA256SUMS --ignore-missing`.
2. Decompress: `zstd -d FroodzOS-0.1.0-dev.10-maverick-arm64-83n3.img.zst` (raw image about 1.9 GB).
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
