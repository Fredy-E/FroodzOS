# CachyOS-derived ARM64 distribution — porting design (v1)

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


Date: 2026-10-07. Status: **research and design only.** No image, kernel, or package has been built or boot-tested. Gates marked **UNTESTED** are goals, not results. User decisions are marked **DECIDED**; defaults applied after the round-2 questionnaire timed out are marked **PROVISIONAL** and are reversible.

Supporting evidence: `docs/research/83n3-hardware-enablement-report.md`, `research/source-index.jsonl`, `research/evidence/verified/`. Source audit: `C:/Users/USER\cachyos-arm64-port-recon.md`. Base/repo strategy: `C:/Users/USER\cachyos-arm-research\arm64-strategy-report.md`.

## 1. Goal and staged scope

**DECIDED.** A public distribution with **general ARM64 support**, carrying the CachyOS experience progressively: default applications first, then kernel/scheduler tuning, optimized package tiers, and gaming. Official CachyOS publishes x86-64 only, and its Arm request was closed `not_planned` (staff, 2025-12-18: "There are no plans for this as of yet."[34]; the maintainer position on the forum is consistent[35]). This project is therefore an **unofficial port built from public sources** — never presented as official CachyOS.

Milestones:

1. **M1 — live USB on the Lenovo 83N3 (IdeaPad Slim 3 15Q8X10):** desktop, built-in keyboard and wired input/network, USB storage, safe shutdown. Windows stays intact and default. **DECIDED** success bar; other features may be incomplete.
2. **M2 — ARM64 VirtualBox guest** on this Windows laptop. Windows 11 on Arm is listed as a VirtualBox host under "Experimental Feature"[14], and Arm hosts accept only Arm-based guests with the VMSVGA graphics controller[14].
3. **M3+ — general ARM64:** more machines, each behind a verified support tier.

## 2. What the evidence establishes

### 2.1 CachyOS source stack: portable in parts, x86-locked in others

- The live profile is x86-locked: `bootmodes=('bios.syslinux' 'uefi.grub') … arch="x86_64" pacman_conf="pacman.conf"`[22], squashfs `xz -Xbcj x86`, and the desktop package list pulls `amd-ucode`, `intel-ucode`, `memtest86+`, `syslinux`[21]. The boot cmdline assumes x86 GPUs (`i915.modeset=1 amdgpu.modeset=1`, per the source audit).
- The kernel recipe declares `arch=('x86_64') url="https://github.com/CachyOS/linux-cachyos" license=('GPL-2.0-only')`[23] and adds x86-only inputs (x86 CPU tiers `x86-64-v3/v4/znver4`, `NVIDIA-Linux-x86_64-…` sources).
- Two in-tree aarch64 precedents: the pacman fork declares `arch=('x86_64' 'aarch64') url="https://www.archlinux.org/pacman/" license=('GPL-2.0-or-later')`[24], and the kernel manager declares `arch=(aarch64 x86_64) url="https://github.com/cachyos/kernel-manager" license=(GPL-3.0-or-later)`[25]. The hardware tool remains `arch=(x86_64) url="https://github.com/cachyos/chwd" license=(GPL-3.0-or-later)`[26].
- Scheduler patches (BORE/PRJC) touch only `kernel/` and `include/linux/` paths per the source audit — arch-neutral in shape, but **untested on arm64** (G0 gate below).
- **Policy boundary:** CachyOS's repository policy states that "Redistribution of the CachyOS repository (and its mirrors) in any unauthorized Linux distribution, including other Arch-based distributions, is STRICTLY PROHIBITED ."[3] The design therefore **never embeds, mirrors, or points users at CachyOS binaries**. Source licenses are a separate matter from that repository policy — the Live-ISO repository is GPL-3.0[27] — and each reused repository's license is reviewed before any source-derived package is published.

### 2.2 ARM64 Arch-family bases

- Only x86_64 is an official Arch architecture: "There is no official Port for this architecture."[28] and the ports RFC exists to change that[43]. Anything we use is community infrastructure.
- The drzee.net port builds "Packages … for devices supporting the ARMv8.2 (and later) instruction sets only."[28] **This conflicts with the DECIDED ARMv8-A baseline**, so drzee is not our base. Candidate bases: Arch Linux ARM[29], the ARMv8/8.1 community repo[28], or a self-rebuilt base with `-march=armv8-a`. Gate **G0b** decides with measurement, not assumption.
- Arch Linux ARM signs packages with a single build-system key but "the repository database files are not signed in order to limit the exposure of private keys and because it is technically unnecessary."[29] **Our repository closes that gap: signed packages *and* signed databases** (PROVISIONAL key model, §3 ADR-7).
- Precedent and industrial signal: the community `nabu-cachyos` project pairs an Arch Linux ARM base with CachyOS kernel patches (per the source audit), and Collabora/Valve built "a pure aarch64 port of Arch Linux"[51].
- Build tooling: ALARM documents distcc cross-compiling[44]; the ARM64 archiso derivative exists as a live-image builder template[46]; GitHub offers arm64 runners for public repositories[47] (publication-dependent; not authorized).

### 2.3 The Lenovo 83N3 enablement picture (device #1)

- Ubuntu Concept 26.10 lists initial enablement: "New X1 machines Lenovo IdeaPad Slim 3"[36]. Experimental, and **unverified on this unit**.
- The firmware ships no usable Linux ACPI; boot uses stubble, which embeds device trees in the kernel image and "If no device-tree has been installed by the firmware, hardware ID values (HWIDs) in the SMBIOS table are used to select one of the appended device-trees."[32] The Slim 3 HWID entry merged in stubble PR #69[40].
- The board device tree is community-maintained (BSD-3-Clause), `model = "Lenovo IdeaPad Slim 3 15Q8X10";`[30]; it is not upstream.
- **Firmware gap:** Ubuntu's own extractor rejects this model — "error: Device is currently not supported"[33] — and Ubuntu states it cannot distribute the firmware ("Some features require additional firmware files that we can not distribute in Ubuntu until they are available under a suitable license."[36]). **Consequence: firmware is staged locally from the machine's own Windows installation and never redistributed; no public image ships it.**
- Known hardware hazards from the evidence set: some touchpad variants need an unpublished GPIO IRQ mux driver[37]; the EC node was disabled after a firmware update broke fan control ("after firmware update fan would cease to function"[54]). **Thermal monitoring is mandatory in every first-contact session.**
- Wi-Fi variant discipline: this unit has FastConnect 7800 (WCN7850/ath12k), matching the DTS (`compatible = "pci17cb,1107"`[30]); sibling units with WCN6855 need a different DTB[40]. Board profiles must record the variant.

## 3. Architecture decision records

| ADR | Decision | Status |
|---|---|---|
| ADR-1 | **CPU baseline ARMv8-A** for every project package (`-march=armv8-a` or toolchain baseline); optimized tiers (e.g. ARMv8.2/LSE) come later as additive repos, never replacements. This is why drzee-based bases are excluded. | **DECIDED** |
| ADR-2 | **Base = Arch Linux ARM rootfs + our own signed overlay repo** carrying the CachyOS-style delta (kernel, settings/hooks, keyring, mirrorlist, boot manager, pacman fork). Whole-distro self-rebuild is deferred (33–61 GiB pool, weeks–months per the strategy report). Base baseline is proven or replaced at G0b. | **PROVISIONAL** shape |
| ADR-3 | **Hardware-enablement kernel first** (Linux 7.3-line with the Slim 3 DTS + platform patches), shipped as a stubble UKI. CachyOS scheduler/optimization patches land only after stable boot, each benchmarked. | **DECIDED** |
| ADR-4 | **Boot:** FAT32 ESP + systemd-boot; UKI = stubble + kernel + DTBs + HWID JSON (`stubble build --linux=… --hwids=… --devicetree-auto=…` per its README[32]). A second plain UEFI/ACPI boot entry covers VMs and recovery. No BIOS/syslinux/memtest artifacts. | **PROVISIONAL** |
| ADR-5 | **Firmware:** local-only staging from the Windows DriverStore (read-only copy) into `/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/` matching the DTS names (e.g. `qcadsp8380.mbn`, `adsp_dtbs.elf`, `qcdxkmsucpurwa.mbn`[30]). Never uploaded, never packaged into public artifacts. | **DECIDED** by license reality |
| ADR-6 | **Installer:** none in M1 (live session only). `archinstall`/CLI installer in M2–M3. Calamares fork only after naming + licensing clarity from CachyOS (it runs `chwd --autoconfigure`, which has no ARM profiles yet[26]). | **PROVISIONAL** |
| ADR-7 | **Signing:** project keyring with an offline master key + build key; **packages and repository databases both signed** (fixing the ALARM gap[29]). Everything stays local; **nothing is published without per-artifact approval**. | **DECIDED** 2026-10-07 |
| ADR-8 | **Naming/branding:** working title `CachyOS-ARM64` for this folder only; public name = user pick from shortlist (Kestrel Linux / Aster64 / Peregrine Linux / Lumen64) before publication; artifacts carry neutral identity (`/etc/os-release` ID ≠ `cachyos`, no CachyOS logos/URLs). A permission question to [REDACTED_EMAIL]` is drafted by the agent and **sent only by the user**. | **OPEN (name only)** |
| ADR-9 | **Builder:** native ARM64 builds on this laptop inside a **separate WSL2 distro** (not Kali) with its VHDX under `D:\CachyOS-ARM64\builder\`; envelope ≤ 60 GiB disk, ≤ 6 GiB RAM, low parallelism. Native compilation — no qemu emulation for builds; qemu-system-aarch64 only for smoke boots and the ARMv8-A baseline proof. | **DECIDED** envelope |
| ADR-10 | **Testing:** Ubuntu Concept control test first (isolates firmware/driver questions from our own image), then our image. Support tiers: **T1** verified on real hardware, **T2** boots with documented gaps, **T3** initial enablement. This Lenovo is the only machine above T3 until more hardware is verified. | **DECIDED** order |

## 4. Milestone gates (all UNTESTED except G0)

| Gate | Proof required | Status |
|---|---|---|
| G0 | Source pins + evidence ledger + this design reviewed | **done (research only)** |
| G0b | Base rootfs proven ARMv8-A-clean (boot under `qemu-system-aarch64 -cpu cortex-a53`, or measured package `-march`); otherwise base is rebuilt or swapped | UNTESTED |
| G1 | Signed aarch64 package built in the WSL builder, verified with `pacman -U` + signature check | UNTESTED |
| G2 | Kernel+DT+stubble-UKI package builds; `qemu-system-aarch64` smoke boot of the rootfs (virt only — proves nothing about the laptop) | UNTESTED |
| G3 | Image assembles and boots on the Lenovo to a desktop (USER gate; USB erase requires explicit approval) | UNTESTED |
| G4 | M1 checklist on the Lenovo: keyboard, wired input/network, USB storage, safe shutdown, thermal log acceptable | UNTESTED |
| G5 | `pacman -Syu` against our signed overlay + base repos with signature verification; clean rebuild reproduces checksums | UNTESTED |
| G6 | Same image boots as an ARM64 VirtualBox guest (VMSVGA; experimental host support[14]) | UNTESTED |

## 5. Risks and mitigations

- **Thermal/EC:** fan behavior under Linux is unverified and the EC node was disabled after a firmware update broke fan control[54]. Mitigation: control test first, live temperature readout in every session, no sustained loads until the fan path is proven, power off on any anomaly.
- **Touchpad:** unpublished GPIO IRQ mux dependency for some variants[37] → M1 success bar uses built-in keyboard + wired input (user's choice); touchpad becomes its own tracked item.
- **Firmware licensing:** the image cannot be self-contained for GPU/audio/battery; each machine stages its own firmware. Document this prominently in the release notes draft.
- **VirtualBox on Windows Arm is experimental[14]** and can conflict with Hyper-V (already enabled on this host). Mitigation: M2 is diagnostic; QEMU smoke boots carry the CI-style load.
- **Base-maintenance exposure:** ALARM's cadence and unsigned DBs[29] are tolerated only as a base; our signed overlay and pinned manifest keep releases reproducible regardless.
- **Naming/legal:** no CachyOS branding; repository policy respected (no Cachy mirrors/guides)[3]; upstream permission question goes out only with explicit user authorization.
- **Gaming expectations:** kernel-level anti-cheat titles are unsupported on ARM Proton[48]; FEX/Box64 are post-MVP experiments[49][50] with no compatibility promises.

## 6. Interview decisions (second round answered 2026-10-07)

1. **Naming:** OPEN — user shortlisted names to pick: Kestrel Linux / Aster64 / Peregrine Linux / Lumen64. Working title `CachyOS-ARM64` until picked; availability/trademark sanity check runs on the pick before any public use.
2. **Signing:** **DECIDED** — own offline master key + local build key; packages and repository databases both signed; everything stays local until the user approves publication.
3. **Publication:** **DECIDED** — nothing is published until the user approves each artifact individually.
4. **Test fleet:** **DECIDED** — this Lenovo is the only verified machine; support tiers state exactly one verified device.
5. **Upstream contact:** **DECIDED** — the agent drafts a message to [REDACTED_EMAIL]` (source-rebuild + naming questions); the user reviews and sends it. The agent never sends it.

## 7. Explicitly out of scope for M1–M2

Installer, internal-disk writes, BIOS updates, Secure Boot/TESTSIGNING changes, Kali modifications, firmware redistribution, public repositories/ISOs, CachyOS mirrors or branding, gaming compatibility claims, and any additional hardware claims.

## Sources

[3] https://wiki.cachyos.org/policy/repository_policy — Repository Usage Policy
    > "End users and third-party mirrors are not subject to the redistribution policy."
    > "Redistribution of the CachyOS repository (and its mirrors) in any unauthorized Linux distribution, including other Arch-based distributions, is STRICTLY PROHIBITED ."
[14] https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/installation.html — Installing VirtualBox
    > "Virtual machines must use an Arm-based guest operating system. Running an x86-based guest operating system on an Arm host platform is not supported."
    > "Only VMSVGA is supported as a graphics controller."
    > "Windows 11 with Arm processors (Experimental Feature"
[21] https://raw.githubusercontent.com/CachyOS/CachyOS-Live-ISO/master/archiso/packages_desktop.x86_64 — CachyOS desktop live package manifest
    > "alsa-utils amd-ucode arch-install-scripts"
    > "memtest86+ memtest86+-efi mesa micro mkinitcpio"
    > "sudo syslinux systemd-resolvconf tcpdump"
    > "intel-ucode inxi irssi"
[22] https://raw.githubusercontent.com/CachyOS/CachyOS-Live-ISO/master/archiso/profiledef.sh — CachyOS live ISO profile source
    > "bootmodes=('bios.syslinux' 'uefi.grub') ## systemd-boot #bootmodes=('bios.syslinux' 'uefi.systemd-boot') arch="x86_64" pacman_conf="pacman.conf""
[23] https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/PKGBUILD — CachyOS kernel package recipe
    > "arch=('x86_64') url="https://github.com/CachyOS/linux-cachyos" license=('GPL-2.0-only')"
[24] https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDs/master/pacman/PKGBUILD — CachyOS pacman architecture declarations
    > "arch=('x86_64' 'aarch64') url="https://www.archlinux.org/pacman/" license=('GPL-2.0-or-later')"
[25] https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDs/master/cachyos-kernel-manager/PKGBUILD — CachyOS kernel-manager package recipe
    > "arch=(aarch64 x86_64) url="https://github.com/cachyos/kernel-manager" license=(GPL-3.0-or-later)"
[26] https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDs/master/chwd/PKGBUILD — CachyOS hardware-manager package recipe
    > "arch=(x86_64) url="https://github.com/cachyos/chwd" license=(GPL-3.0-or-later)"
[27] https://api.github.com/repos/CachyOS/CachyOS-Live-ISO/license — CachyOS live ISO repository license metadata
    > ""name":"GNU General Public License v3.0""
[28] https://ports.archlinux.page/aarch64 — Arch Linux Ports AArch64 status and ISA baseline
    > "There is no official Port for this architecture."
    > "Packages are built for devices supporting the ARMv8.2 (and later) instruction sets only."
[29] https://archlinuxarm.org/about/package-signing — Arch Linux ARM package-signing policy
    > "the repository database files are not signed in order to limit the exposure of private keys and because it is technically unnecessary."
[30] https://raw.githubusercontent.com/jglathe/linux_ms_dev_kit/jg/ubuntu-qcom-x1e-7.3rc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts — Lenovo 83N3 community device tree
    > "model = "Lenovo IdeaPad Slim 3 15Q8X10";"
[32] https://raw.githubusercontent.com/ubuntu/stubble/main/README.md — stubble boot stub documentation
    > "Loading machine specific device trees embedded within a kernel image."
    > "If no device-tree has been installed by the firmware, hardware ID values (HWIDs) in the SMBIOS table are used to select one of the appended device-trees."
[33] https://git.launchpad.net/ubuntu/+source/qcom-firmware-extract/tree/?h=ubuntu/stonking — Ubuntu firmware extractor source tree
    > "error: Device is currently not supported"
[34] https://github.com/CachyOS/linux-cachyos/issues/646 — CachyOS issue #646: Arm support (closed not_planned)
    > "There are no plans for this as of yet."
[35] https://discuss.cachyos.org/t/arm-future-for-cachyos/727 — CachyOS forum: ARM future for CachyOS
    > "Generally, we would like to have an ARM(64) variant, but we would also like to base on archlinux."
[36] https://discourse.ubuntu.com/t/ubuntu-concept-26-10-snapdragon-edition/88518 — Ubuntu Concept 26.10 Snapdragon announcement
    > "New X1 machines Lenovo IdeaPad Slim 3"
    > "Some features require additional firmware files that we can not distribute in Ubuntu until they are available under a suitable license."
[37] https://bugs.launchpad.net/bugs/2114876 — Launchpad #2114876: Add support for Lenovo Ideapad Slim 3
    > "The touchpad wont work without a GPIO IRQ MUX driver which I have written but have not published yet."
    > "IdeaPad Slim 3 15Q8X10"
[40] https://github.com/ubuntu/stubble/pull/69 — stubble PR #69: HWIDs for IdeaPad Slim 3
    > "hwids: Add Lenovo IdeaPad Slim 3 15Q8X10"
[43] https://rfc.archlinux.page/0032-arch-linux-ports — Arch Linux RFC 0032: Arch Linux Ports
    > "strong commitment towards reproducible builds"
[44] https://archlinuxarm.org/wiki/Distcc_Cross-Compiling — ALARM distcc cross-compiling guide
    > "the official cross-compiling method used at Arch Linux ARM"
[46] https://codeberg.org/ironrobin/archiso-aarch64 — archiso-aarch64 image builder
    > "builds on Arch Linux's upstream releng profile with a thin compatibility layer powered by stubble, allowing a single image to boot across supported AArch64 laptops"
[47] https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available — GitHub arm64 hosted runners for public repos
    > "Starting today, Linux and Windows arm64 standard hosted runners in public repositories are generally available."
[48] https://partner.steamgames.com/doc/steamhardware/proton — Steam partner docs: Proton and anti-cheat
    > "not currently supported"
[49] https://fex-emu.com — FEX-Emu x86-on-ARM64
    > "run x86 applications on ARM64"
[50] https://github.com/ptitSeb/box64 — Box64 x86_64 emulation on ARM
    > "Box64 enables running x86_64 Linux programs, including games, on non-x86_64 Linux systems such as Arm (64-bit little-endian host system required)."
[51] https://www.collabora.com/news-and-blog/news-and-events/building-an-arch-linux-aarch64-port-for-holo-core.html — Collabora: Arch Linux aarch64 port for Holo Core
    > "a pure aarch64 port of Arch Linux to be used as the basis for the OS running on the Steam Frame"
[54] https://discourse.ubuntu.com/t/48800/1998.json — Discourse 48800/1998: Slim 3 EC driver / fan behavior
    > "after firmware update fan would cease to function"
