# FroodzOS

**An unofficial, experimental ARM64 Linux distribution project — starting with native bring-up on the Lenovo IdeaPad Slim 3 15Q8X10 (83N3 / Snapdragon X1-26-100).**

This repository preserves the source, development history, diagnostic revisions,
failed experiments, tests and evidence from the first research on **7 October
2026** through the **current 26 October 2026 state**: native desktop,
owner-confirmed built-in Wi-Fi, a fully written and read-back 32 GiB USB
persistence partition, and a separate guarded CLI image validated through EFI
in QEMU and applied to the USB. Its first native boot and reboot persistence
remain open.

> **Source and engineering archive, not an installable OS release.** No ISO,
> firmware-bearing image, package repository, private signing key or installer is
> distributed here. A desktop on one laptop is not general ARM64 compatibility.

The implementation snapshot in this archive remains the 19 October source
publication. Later timeline/status entries describe newer local engineering
work; this documentation update does not publish the workstation or native
validator implementation, its private logs or boot images.

## What works, and what does not

| Area | Evidence-backed status |
|---|---|
| ARM64 bootstrap and virtual baseline | Dedicated ARM64 builder; signed-package/repository rehearsals; Cortex-A53 QEMU baseline recorded. Virtual proof only. |
| Native USB boot and live root | Verified on this Lenovo: boot chain, writable live overlay, systemd and interactive console. |
| Native desktop | Owner saw Plasma; both recovered dt26 boots passed the real CPU/DRM preflight and accepted a live Wayland session. |
| Display | Firmware framebuffer / simpledrm, connected 1920 × 1200 output; software rendering. **No accelerated GPU claim.** |
| Input | Keyboard and external mouse work per owner; **built-in touchpad does not**. |
| Thermal observation | All 20 required CPU/cpuss types recorded. Readout and bounded monitoring are not cooling/fan-control validation. |
| Networking | **Built-in Wi-Fi works** (owner-confirmed; WCN7850/ath12k activation and DHCP on `wlP4p1s0`). USB Ethernet drivers are present but unexercised. |
| Persistence | 32 GiB ext4 USB partition written in full and independently read back; native reboot persistence is **not yet proved**. |
| Guarded CLI workstation | Separate image reviewed and applied; one uninterrupted real EFI/QEMU A/B/C run passes all 50 checks. **Native boot/login still open.** |
| Cleanup / power | One native run captured owned graphical-session cleanup; final physical poweroff remains unproven. |
| Hermes Agent | Not installed natively. Internet, persistent workspace and a suitable safe work session are prerequisites. |
| Other boards / general ARM64 | Project goal, not established support. |

**Existing graphical diagnostic limits remain:** 180-second graphical session,
guarded CPU readings, owned-only GUI cleanup and a volatile 512 MiB overlay.
The separate opt-in text workstation uses the USB ext4 overlay and a continuous
thermal/space guard; its native acceptance is not established. Neither mode is
a daily-driver recommendation.

## Start here

- [Project timeline, 7–26 October 2026](docs/TIMELINE.md)
- [Current status and safety boundaries](docs/STATUS.md)
- [Complete development-history index](docs/history/README.md)
- [Current task list](docs/TASKS.md)
- [Native desktop evidence and remaining prerequisites](docs/dt26-native-desktop-success.md)
- [Architecture / original design](docs/porting-design.md) — historical, not current execution instructions
- [Source inputs, pins and recovered replayable deltas](reproducibility/README.md)
- [Publication scope, exclusions and provenance](docs/PUBLICATION.md)
- [License and third-party notices](NOTICE.md)

## Repository layout

| Path | Contents |
|---|---|
| `builder/` | Build recipes, initramfs hooks, platform gates, text/graphics supervisors and logger sources. |
| `pkgs/` | Packaging records and the complete retained numbered diagnostic-patch history. Some old patch documents are malformed; do not replay them blindly. |
| `boards/lenovo-83n3/` | Captured kernel configuration and board DTS source. |
| `reproducibility/` | Pinned upstream references and forward/reverse byte-tested cumulative source deltas recovered from the actual builder. |
| `testing/` | Diagnostic/test scripts and reviewed structured receipts, including failed runs. |
| `docs/` | Decisions, research, phase reports, current state and chronological history. |
| `third_party/` | Applicable upstream license texts and notices; no vendor firmware. |
| `tools/` | Reviewed local tooling and publication integrity verification. |

## Development and verification

Do **not** execute the historical scripts as an unattended installer. Some
modify a dedicated builder, create fixtures, or write specifically authorized
removable-media / owned-firmware targets. They retain historical assumptions and
absolute workspace paths. Review their scope, prerequisites and current safety
contracts first. No script here is permission to change Windows, firmware,
security settings, internal storage or another WSL distribution.

The portable publication-integrity checks and fixture tests are documented in
[verification](docs/VERIFICATION.md). Full OS-image reproducibility, a maintained
update trust chain and binary redistribution clearance remain separate gates.

## Upstream credit and licensing

FroodzOS is not affiliated with or endorsed by CachyOS, Arch Linux, Arch Linux
ARM, Lenovo, Qualcomm, Ubuntu, KDE or Nous Research. The bring-up uses the pinned
community hardware-enablement kernel and stubble, with an Arch Linux ARM-based
userland. Ubuntu Concept was a control/reference, not a substitution for the
project's requested base. Kestrel is the historical implementation name; working
USB labels, boot identifiers and logger contracts have intentionally not been
renamed for presentation.

Existing per-file and upstream licenses remain in effect. **No new blanket
project license has been selected or applied.** See [NOTICE.md](NOTICE.md).
Private firmware, keys and raw private machine logs remain local; they are not
covered or redistributed by this source publication.
