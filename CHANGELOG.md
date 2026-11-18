# Changelog

All notable changes to FroodzOS. The product versions follow the owner-selected codename roadmap
(see [docs/releases/](docs/releases/README.md)); component, fixture, board and build identifiers are separate
namespaces and never mean a product release. Dates are record dates, not release promises.

## [Unreleased] - 0.1.0-dev "Maverick"

Status: **development, not a qualified alpha. No binaries, tag or release exist.**

### Direction (2026-11-11)
- Main goal recorded: universal file and app compatibility, as native as feasible (`docs/releases/UNIVERSAL-COMPATIBILITY.md`). Not implemented yet.

### 0.1.0-dev.3 candidate (2026-11-18)
- Version bump to `0.1.0-dev.3` (build id `maverick-public-dev-20261118.2`); first boot entry uses the device tree with both fixes (orphaned-vote removal and the real touchpad), the second entry keeps the dev.2 style user-space touchpad driver. Release notes: `docs/releases/RELEASE-NOTES-0.1.0-dev.3-maverick.md`.
- New opt-in `fz-persist` service (`fz_persist=1` on the kernel command line): mounts the ext4 partition labelled `FROODZ_PERSIST`, seeds it from the live home on first use and bind-mounts it over the live user's home and the saved NetworkManager connections, so a stick can keep a sign-in and Wi-Fi networks across reboots. Without the flag or the partition it does nothing. Whoever holds the stick can read what is stored there; the public image ships no such partition.
- `etc/environment.d/90-froodzos.conf` sets `POWERDEVIL_NO_DDCUTIL=1` (PowerDevil's DDC probe of `/dev/i2c-*` fails with EACCES on this laptop).

### First live-boot findings (2026-11-18, not released)
- Boot time: the shared-library cache is now built in the image and `ldconfig.service` is masked (it took 28 s of every live boot on the USB root; packages installed in a running session still run ldconfig through their pacman hook).
- `fz-touchpad.service` gets a drop-in `ExecCondition` so the user-space fallback driver steps aside when the kernel driver (`i2c_hid_of`) owns the touchpad; before, it failed five times with EBUSY and left systemd degraded.
- `fz-smartlog` picked the AC supply as the battery (the glob `*bat*` also matches `qcom-battmgr-ac`) and reported no battery; it now selects the supply by `type=Battery`.
- New `builder/public-image/fz-board-touchpad.py`: patches a compiled device tree so the Lenovo IdeaPad Slim 3 15Q8X10 touchpad (FocalTech FTCS0038 at I2C 0x38, interrupt TLMM GPIO 19 level-low; the board DTS wrongly lists a GXTP5100 at 0x5d without interrupt) binds the kernel `i2c_hid_of` driver. Owner-tested on the laptop 2026-11-18 (`0-0038` bound, pad works); gestures unconfirmed.
- systemd-timesyncd is enabled; `wireless-regdb rtkit alsa-utils` are installed in the r9 root (regulatory database, RTKit, ALSA tools).

### Stick autorun hook (2026-11-17, not released)
- New `fz-stick-autorun` service in the root: with `fz_autorun=1` on the kernel command line and a `FroodzOS-addons/autorun.sh` on the boot stick, it runs that script once as root late in boot (non-blocking, 300 s limit) and keeps its output in `Logs/autorun-<boot id>.txt`. Without the flag or the file it does nothing. It lets a test stick bring its own private add-ons and unattended post-boot checks without rebuilding the root; no private content is part of the repository or the public image.

### Live-fix tools (2026-11-16, not released)
- `builder/public-image/build-root.sh`: the package list can be passed in `PKGS` (r7 adds `kexec-tools dtc efibootmgr git openssh evtest strace`, about 10 MB), and the root now ships `fz-dtb-fixup.py` and the new `fz-kexec-uki` in `/usr/local/sbin`.
- `fz-kexec-uki` (experimental, untested on the laptop): extracts the kernel and initramfs from the booted unified kernel image and stages a `kexec` load with a changed device tree, so a device-tree fix can be tried from the running live session without the firmware boot menu.

### Development after dev.2 (2026-11-14, not released)
- Battery percentage, charge state and USB-C power data work on the 83N3 in an owner test: the ADSP was waiting on a bandwidth vote through a disabled NoC; `builder/public-image/fz-dtb-fixup.py` removes such orphaned
  votes from any compiled DTB and Linux then attaches to the ADSP the laptop firmware already started (no vendor firmware needed). Cause and method: `docs/hardware-dsp-battery.md`. Sound still open.
- `fz-smartlog`: counts an attached remoteproc as running, derives the battery percentage from energy values, reports wireless interface presence and battery health.

### Released (2026-11-13, 0.1.0-dev.2)
- Pre-release `v0.1.0-dev.2-maverick` (build `maverick-public-dev-20261113.4`): Phase 1 file handlers (Ark, 7zip, unrar, unzip/zip, cabextract, lhasa, unshield,
  squashfs/erofs/dosfstools/exfatprogs/ntfs-3g/mtools, Okular, Gwenview, Haruna/mpv/Elisa, Kate, LibreOffice) on a full system upgrade; **Helium and Zen Browser**
  as unmodified upstream releases; the graphics session fixed for Plasma 6.8 and no longer limited to 180 seconds (`kestrel_graphics_unbounded=1`); panel brightness
  at maximum (`fz-backlight-max`); the smart log `fz-smartlog`; a smaller root (`prune-root.sh`); release procedure `docs/releases/RELEASING.md`; handler inventory
  `docs/compat/HANDLERS-PHASE1.md`. Known gaps: no battery or power data and no sound (the ADSP does not start), no GPU acceleration, Wi-Fi does not survive suspend.
- Tools: `builder/public-image/build-root.sh`, `build-gfx-variant-uki.py` (boot image rewrites, device tree swap), `make-menu-v10.py`, `rootfs-overlay/`, `tests/test_graphics_supervisor.py`.

### Released (2026-11-11)
- Pre-release [`v0.1.0-dev-maverick`](https://github.com/Fredy-E/FroodzOS/releases/tag/v0.1.0-dev-maverick): firmware-free development image for the 83N3 (build `maverick-public-dev-20261111.2`), signed checksums, package list and source offer.

### Added (2026-11-11, release candidate)
- Firmware-free public image build tooling in `builder/public-image/`, exact-build manifest `release/manifests/maverick-public-dev-20261111.2.json`,
  rights review, source offer, firmware and signing documents (`docs/releases/`), release signing public key (`release/signing/`).
- Draft release notes: `docs/releases/RELEASE-NOTES-0.1.0-dev-maverick.md`.

### Added
- Release identity metadata: the 25 owner-selected codenames, the `0.1.0-dev` development identity, the
  Lenovo 83N3 board profile, a validator (`tools/validate_release.py`) and its tests; release policy,
  roadmap and the 0.1 Maverick scope under `docs/releases/`.
- Project licence for original FroodzOS code and tools: **GPL-2.0-or-later** (`LICENSE`, `NOTICE.md`).
- `SECURITY.md`, `CONTRIBUTING.md`, issue and pull-request templates.
- Documentation of the 29 October to 10 November work in `docs/TIMELINE.md`.
- Built-in touchpad support in basic mouse mode: user-space polling driver and service for the 83N3 (`boards/lenovo-83n3/touchpad/`, `docs/touchpad.md`), owner-tested on 2026-11-11.

### Changed
- 0.1 scope narrowed (2026-11-10) to a limited live alpha **without** the native Hermes workstation
  integration, which is parked rather than deleted (`docs/history/hermes-track-status-through-20261110.md`).
- `README.md` rewritten around the current status and evidence boundaries.
- Native observations: a private `0.1.0-dev` development candidate booted natively on the Lenovo 83N3
  (Wi-Fi, keyboard and mouse working) on 2026-11-10; the touchpad was added on 2026-11-11 (see Added). It is private and unpublished.
- Boot menu reworked on the private media (fewer entries, small font, native-mode handoff); awaiting owner
  confirmation. The default entry now includes the touchpad driver; the previous default stays as a fallback entry.

### Known limitations
- Touchpad tap-to-click, gestures and natural scrolling; audio, camera, USB-C and charging, battery diagnostics, suspend, GPU acceleration:
  not working or not accepted.
- Safe-shutdown and recovery qualification still open.
- The published image is a development image for one laptop; Arch Linux ARM publishes no explicit redistribution statement (see `docs/releases/RIGHTS-REVIEW.md`).

## History before this changelog

The development history from 7 October 2026 is in [docs/TIMELINE.md](docs/TIMELINE.md) and
[docs/history/](docs/history/README.md); the 19 October source publication is the first public state.
