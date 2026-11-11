# Changelog

All notable changes to FroodzOS. The product versions follow the owner-selected codename roadmap
(see [docs/releases/](docs/releases/README.md)); component, fixture, board and build identifiers are separate
namespaces and never mean a product release. Dates are record dates, not release promises.

## [Unreleased] - 0.1.0-dev "Maverick"

Status: **development, not a qualified alpha. No binaries, tag or release exist.**

### Direction (2026-11-11)
- Main goal recorded: universal file and app compatibility, as native as feasible (`docs/releases/UNIVERSAL-COMPATIBILITY.md`). Not implemented yet.

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
