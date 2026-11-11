# FroodzOS

**An unofficial, experimental ARM64 Linux distribution project, starting with native bring-up on the Lenovo IdeaPad Slim 3 15Q8X10 (83N3 / Snapdragon X1-26-100).**

| | |
|---|---|
| Current version | **`0.1.0-dev`, codename Maverick** (development; **not** a qualified alpha) |
| Target milestone | FroodzOS 0.1 Maverick - ARM64 Alpha: a limited live alpha for one laptop |
| Binaries | One signed **development image** for the 83N3 only, as a GitHub pre-release ([`v0.1.0-dev-maverick`](https://github.com/Fredy-E/FroodzOS/releases/tag/v0.1.0-dev-maverick)). No vendor firmware, no installer |
| Licence | Original FroodzOS code and tools: **GPL-2.0-or-later** (see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md)); third-party material keeps its own licences |

> **Early development.** A live desktop on one laptop is not general ARM64 compatibility, and not yet a finished operating system.
> Release dates are not assigned; see the [release policy](docs/releases/POLICY.md).

## Main goal

**FroodzOS must open every kind of file and run the apps and operating systems of other platforms directly on your own machine —
as natively as technically possible — starting with a few formats and growing without a fixed limit:**
`.zip` `.rar` `.iso` `.docx` `.xlsx` `.exe` `.apk` `.dmg` and, over time, literally everything: office files, archives, disk images,
Windows programs, phone apps and other operating systems.

This is the direction of the project, **not something it does today**: the current image is a desktop with a working Wi-Fi, keyboard and
touchpad on one laptop. The plan, what "native" can mean for each format (native, compatibility layer, virtual machine, or not feasible
because of technology or law), and the phases are in [docs/releases/UNIVERSAL-COMPATIBILITY.md](docs/releases/UNIVERSAL-COMPATIBILITY.md).

## What this repository is

The source, development history, diagnostic revisions, failed experiments, tests and evidence from the
first research on **7 October 2026** onward. It documents how a CachyOS-derived, Arch Linux ARM based live
system was brought up natively on the 83N3 laptop, and how the first release (0.1 Maverick) is being
qualified. Failed and rejected revisions are kept on purpose; nothing is retroactively relabelled as a pass.

## Download (development image)

A firmware-free **development image for the Lenovo IdeaPad Slim 3 15Q8X10 (83N3) only** is available as a signed GitHub pre-release:
[`v0.1.0-dev-maverick`](https://github.com/Fredy-E/FroodzOS/releases/tag/v0.1.0-dev-maverick) (1.43 GB compressed raw USB image,
SHA256SUMS and signature, package list, source offer). Read the release notes first: Secure Boot must be off, brightness keys,
battery and audio do not work or are not claimed, and writing the image erases the target USB stick. Verification steps are in
[docs/releases/SIGNING.md](docs/releases/SIGNING.md); rights and open points in [docs/releases/RIGHTS-REVIEW.md](docs/releases/RIGHTS-REVIEW.md).

## Status (evidence as of 11 November 2026)

| Area | Evidence-backed status |
|---|---|
| Native USB boot and live root | Verified on the 83N3: boot chain, writable live overlay, systemd, interactive console. A private `0.1.0-dev` candidate also booted natively on 2026-11-10. |
| Desktop and display | Owner saw Plasma with software rendering; the panel is 1920x1200. A fix so the kernel receives the native mode instead of a 1024x768 menu mode was applied on 2026-11-10 and awaits owner confirmation. **No accelerated GPU claim.** |
| Input | Keyboard and external mouse work. **The built-in touchpad works in basic mouse mode** in the private candidate through a user-space polling driver ([`docs/touchpad.md`](docs/touchpad.md)); tap-to-click and gestures are not available yet. |
| Networking | **Built-in Wi-Fi works** (WCN7850 / ath12k). USB Ethernet is unexercised. |
| Persistence | A 32 GiB ext4 USB partition was written in full and read back; a HOME file canary was accepted across two different native boots. Full settings and tools persistence is not proved. |
| Thermal | All 20 required CPU/cpuss sensor types observed. That is not cooling or fan-control validation. |
| Audio, camera, USB-C and charging, battery, suspend | Not accepted. They would be documented limitations of a limited 0.1. |
| Safe shutdown and recovery qualification | Open. |
| Hermes workstation integration | Out of the 0.1 scope (owner decision 2026-11-10); parked, not deleted. |
| Public binary image | Not available. Rights for a public image (CachyOS repository terms, vendor firmware, base-system terms) are unresolved; see [NOTICE.md](NOTICE.md). |
| Other boards / general ARM64 | A project goal, not established support. |

Details and the evidence classes behind each row are in [docs/releases/CURRENT.md](docs/releases/CURRENT.md).

## Versions and codenames

The owner selected 25 version and codename pairings (0.1 Maverick through 4.0 Banshee); they are kept
exact, for example `1.0 Sherman` is not `1.5 Super Sherman`. Component, fixture, board and build identifiers
are separate namespaces and never mean a product release. See [docs/releases/](docs/releases/README.md),
the [roadmap](docs/releases/ROADMAP.md) and the [changelog](CHANGELOG.md).

## Start here

- [Main goal and compatibility plan](docs/releases/UNIVERSAL-COMPATIBILITY.md)
- [Release status, evidence boundaries and blockers](docs/releases/CURRENT.md)
- [Download the development image](https://github.com/Fredy-E/FroodzOS/releases/tag/v0.1.0-dev-maverick) and its [release notes](docs/releases/RELEASE-NOTES-0.1.0-dev-maverick.md)
- [0.1 Maverick scope](docs/releases/0.1-maverick.md) and [promotion policy](docs/releases/POLICY.md)
- [Changelog](CHANGELOG.md)
- [Documentation index](docs/README.md)
- [Project timeline](docs/TIMELINE.md), [task list](docs/TASKS.md), [complete history index](docs/history/README.md)
- [Native desktop evidence](docs/dt26-native-desktop-success.md)
- [Source inputs, pins and replayable deltas](reproducibility/README.md)
- [Publication scope, exclusions and provenance](docs/PUBLICATION.md)
- [Security policy](SECURITY.md) and [contributing](CONTRIBUTING.md)

## Repository layout

| Path | Contents |
|---|---|
| `builder/` | Build recipes, initramfs hooks, platform gates, supervisors and logger sources. |
| `pkgs/` | Packaging records and the retained numbered diagnostic-patch history. Some old patch documents are malformed; do not replay them blindly. |
| `boards/lenovo-83n3/` | Captured kernel configuration, board device-tree source and the touchpad polling driver. |
| `reproducibility/` | Pinned upstream references and byte-tested cumulative source deltas. |
| `release/` | Machine-readable development identity, the 25 codenames and the board profile. |
| `testing/` | Diagnostic and test scripts and reviewed receipts, including failed runs. |
| `docs/` | Decisions, research, phase reports, current state, release documents and chronological history. |
| `third_party/` | Applicable upstream licence texts and notices; no vendor firmware. |
| `tools/`, `tests/` | Publication integrity verification, the release-metadata validator, SPDX and privacy helpers, and tests. |
| `research/` | Raw research data (JSON and JSONL); not documentation. Prose research is under `docs/research/`. |
| `.github/` | Issue and pull-request templates, CODEOWNERS and CI workflows. |

## Verification

```bash
python tools/verify-publication.py        # every file listed in SHA256SUMS, no binaries or private paths
python tools/validate_release.py          # release identity and codename catalogue consistency
python -m unittest discover -s tests      # portable fixture tests
```

These checks establish record consistency and publication hygiene, **not** hardware, package or release
readiness. Do **not** run the historical scripts as an unattended installer: some modify a dedicated builder,
create fixtures or write specifically authorised removable-media targets, and they retain absolute
workspace paths. No script here is permission to change Windows, firmware, security settings or internal storage.

## Upstream credit and licensing

FroodzOS is not affiliated with or endorsed by CachyOS, Arch Linux, Arch Linux ARM, Lenovo, Qualcomm,
Ubuntu, KDE or Nous Research. The bring-up uses a pinned community hardware-enablement kernel and stubble
with an Arch Linux ARM based userland. Kestrel is the historical implementation name; working USB labels,
boot identifiers and logger contracts have intentionally not been renamed.

Original FroodzOS source code and tools are licensed **GPL-2.0-or-later** (owner decision, 2026-11-10).
Files that carry their own licence headers, upstream kernel code, the board device tree and stubble keep
those terms. Documentation prose has no separate licence selected yet; see [NOTICE.md](NOTICE.md).
Private firmware, keys and raw private machine logs are not covered or redistributed by this archive.
