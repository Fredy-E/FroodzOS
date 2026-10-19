# CachyOS-derived ARM64 distribution: project brief

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


Current status (2026-10-18): **native interactive dt25b text boot and all 20 required CPU/cpuss thermal readouts verified on Lenovo 83N3**. Systemd, live overlay, tty1 Bash and a saved typed command are proven; CPU readings were 30.2–36.5 C across 62 complete samples. Plasma/full M1 and final shutdown remain open. The cleaned USB menu uses **#1 current text** and **#2 a distinct dt24 text recovery image**. See [current tasks](TASKS.md), [project progress](project-progress.md) and [latest native evidence](dt25b-native-thermal-check.md).

Current naming decision (2026-10-18): the user selected **FroodzOS** as the public project name. This supersedes the historical open-name shortlist below, not the existing Kestrel boot/logger/USB identifiers. No remote publication or runtime rename was authorized by the naming question. See [publication path and rough progress estimate](froodzos-publication.md).

The initial planning/authorization snapshots below are historical, not a current claim that nothing was built or a new permission grant. Current work remains native-first, file-only on the approved USB, with protected Windows/internal disks/boot settings unchanged and publication separately gated.

## Decisions from the user

- Goal: a public distribution with general ARM64 support, not limited to Snapdragon or this Lenovo. No additional physical test models have been named; hardware validation must not be overstated.
- Sequence: first make the live image boot; then port/validate the kernel, applications, optimizations and the rest of the CachyOS experience progressively.
- First hardware milestone: bootable live USB on the current Lenovo laptop, not an internal installation.
- Next target, clarified: Oracle VirtualBox, running an ARM64 guest on this Windows laptop. Verify current native Windows-on-Arm host support before designing this test; it is not OCI and not Oracle Linux.
- Applications: default applications first. Eventual hardware requirements include accelerated graphics, Wi-Fi, speakers/microphone, camera, suspend, battery life, external monitors and diagnostic USB devices.
- Workspace: one organized main folder on D:. This workspace is `D:\CachyOS-ARM64`.
- Test equipment: user has a 64 GB USB 3.0 drive and all wired peripherals. No permission to erase it has been given.
- No build-storage cap, cloud budget, public project name or maintenance commitment has been confirmed yet.

## Live host inventory (2026-10-07, read-only)

- Lenovo 83N3, IdeaPad Slim 3 15Q8X10.
- Snapdragon X X126100 / X1-26-100, ARM64, 8 cores.
- RAM: 15.61 GiB reported usable; 1.69 GiB available at the inventory instant. This is a transient reading, not a permanent capacity limit.
- Windows 11 Enterprise build 26200; BIOS RVCN21WW.
- Qualcomm FastConnect 7800 Wi-Fi 7 HBS; this exact Wi-Fi variant matters for device-tree/firmware validation.
- Two separate 238.47 GiB NVMe disks. C: 36.23 GiB free; D: 147.67 GiB free at inspection. No spare USB disk was detected.
- WSL, VirtualMachinePlatform and Hyper-V enabled; Kali WSL2 is already installed and must remain untouched.
- Secure Boot currently off; Windows TESTSIGNING currently on. These belong to the existing Windows setup and are not permission to change boot security.
- BitLocker inventory reported 0% encryption and protection off on C: and D:. No recovery keys were read.

## Research tracks

1. CachyOS source stack: image builder, installer, package manifests, tools, kernel changes and x86 assumptions.
2. Exact Lenovo hardware enablement: known boot chain, kernel, device tree, firmware, graphics and peripherals.
3. ARM64 bootstrap/package base, signing/update infrastructure, reproducibility and gaming compatibility.
4. Parent review: local resources, redistribution boundaries, source/branding provenance, staged acceptance gates and detailed user interview.

## Known constraints to carry into the design

- An ARM64 root filesystem, an ARM64 kernel, a bootable laptop image and a maintainable distribution are different deliverables; prove each separately.
- Reuse hardware-enablement research from Ubuntu or other sources where its license permits, without silently changing the requested final distribution to Ubuntu.
- Treat source-code licenses separately from CachyOS's published binary repository/mirror usage policy. Inspect each component's actual license; do not assume open source grants unrestricted branding, firmware redistribution or use of upstream package-hosting services.
- A public port needs its own verified ARM64 package/update strategy. Never disable signature checking as a bootstrap shortcut.
- Do not equate a VM boot with physical Snapdragon graphics, power, audio or USB validation.
- Keep the first media non-installing and non-persistent on internal disks. No automatic NVMe mounts, EFI-variable changes, installer writes or firmware/security updates.

## Authorization boundaries

Allowed now: public read-only research, local read-only inventory, and planning/evidence documents under this main folder.
Not authorized now: installing a builder, changing Kali, fetching large images/source trees, compiling/executing upstream code, formatting media, repartitioning, rebooting, changing firmware/boot/security settings, paid resources, contacting maintainers, publishing or pushing repositories.

## Pending artifacts

- Source-cited feasibility and architecture report.
- Hardware support/test matrix with proven versus unknown status.
- Architecture decisions and open-question log.
- Gated implementation plan after the remaining decisions are answered.

## Decision log (second interview, 2026-10-07)

- CPU baseline: ARMv8-A generic first; optimized tiers additive later.
- Kernel: hardware-enablement kernel first; CachyOS schedulers benchmarked only after stable boot.
- M1 success bar: desktop, built-in keyboard + wired input/network, USB storage, safe shutdown; other features may lag.
- Build envelope: local-only, up to 60 GiB on D:, 6 GiB builder RAM, limited parallelism; separate WSL2 builder distro, Kali untouched.
- Control test first: Ubuntu Concept live session before our own image.
- Signing: own offline master + build key; packages AND repository databases signed; local-only until approval.
- Publication: nothing public until the user approves each artifact.
- Test fleet: this Lenovo only; support tiers say one verified machine.
- Upstream contact: agent drafts the admin@cachyos.org message; the user reviews and sends.
- Name: OPEN — shortlist Kestrel Linux / Aster64 / Peregrine Linux / Lumen64 awaiting the user's pick.

Delivered: `docs/porting-design.md` (cited design, gates G0–G6) and `docs/implementation-plan.md` (task-by-task plan). Nothing built yet; Phase 1 (builder setup) awaits the user's go.
