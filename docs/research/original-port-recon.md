# CachyOS → ARM64 (unofficial): source/build reconnaissance

Date: 2026-10-07. Method: read-only inspection of public CachyOS GitHub org repos via API + raw file fetches. No clones, no code execution, nothing built or tested. All claims below are either quoted from fetched sources (URLs in Appendix) or labeled as inference.

Tree/commit identifiers at inspection (branch → tree SHA):
- CachyOS-Live-ISO `master` → `3215497d2e8c`
- CachyOS-PKGBUILDS `master` → `03924f78cd52`
- linux-cachyos `master` → `7ded3a8b97d1`; kernel source fork CachyOS/linux default branch `7.0/cachy`
- kernel-patches `master` → `17bb0bb818d2`
- chwd `master` → `2d963e942bbd`
- cachyos-calamares `cachyos` → `5f098957d35f` (PKGBUILD builds from `cachyos-dev`)
- devtools `master` → `8f0d146f8aae`

Host build constraints (given): 16 GB RAM total / ~1.69 GiB currently available; C: 36.23 GiB free; D: 147.67 GiB free.

## 1. Official stance (scope, not impossibility)

- Issue [CachyOS/linux-cachyos#646 "Arm support"](https://github.com/CachyOS/linux-cachyos/issues/646) — closed `not_planned` 2025-12-18. Team comment (1Naim): "There are no plans for this as of yet. x86_64 also isn't dying any time soon." A later user re-ask (2026-01-19) is unanswered.
- Nothing ARM64 is published in their download channels; README statements and repo tooling are x86-64-only (below). However, two in-tree precedents show partial aarch64 awareness: the `pacman` PKGBUILD declares `arch=('x86_64' 'aarch64')` with an `source_aarch64` patch, and `cachyos-kernel-manager` declares `arch=(aarch64 x86_64)`.

## 2. How CachyOS is built today (the forks that matter)

**ISO/profile.** CachyOS-Live-ISO is an archiso-style profile with custom driver scripts (`buildiso.sh`, `util-iso*.sh`; CI also calls `mkarchiso`). Hard x86 assumptions:
- `arch="x86_64"`; `bootmodes=('bios.syslinux' 'uefi.grub')`; squashfs `xz -Xbcj x86`. `/archiso/profiledef.sh`
- `util-iso.sh` copies `packages_desktop.x86_64` → `packages.x86_64` and renames output to `...-x86_64.iso`. (lines 145, 193-194)
- Single package list `packages_desktop.x86_64` includes `amd-ucode`, `intel-ucode`, `memtest86+`, `memtest86+-efi`, `syslinux`, `refind`, `hyperv`, `occt`, `linux-atm`; `bootstrap_packages.x86_64` = `arch-install-scripts base`.
- `pacman.conf` = `[cachyos] Server=https://mirror.cachyos.org/repo/$arch/$repo` + Arch core/extra.
- EFI boot entry cmdline assumes x86 GPUs: `i915.modeset=1 amdgpu.modeset=1`.
- CI: x86_64 `archlinux:base-devel` container; quicktest matrix (grub/systemd-boot/refind/limine × btrfs/xfs/ext4/f2fs/zfs) via quickemu; `testiso.sh` uses a VirtualBox `ArchLinux_64` VM.

**Installers.**
- Calamares fork `cachyos-calamares` (packaged as `cachyos-calamares-next` 3.4.2, `arch=('x86_64')`, pinned to branch `cachyos-dev`; separate branches exist per bootloader: `cachyos-systemd`, `cachyos-grub`, `cachyos-refind`, `cachyos-limine-qt6`, …). Custom module `src/modules/chwd/main.py` runs `arch-chroot <root> chwd --autoconfigure` (plus an AI-SDK path when `packagechooser_bootloader == refind-ai`).
- New CLI net-installer (`New-Cli-Installer`, C++23/FTXUI → pkg `cachyos-cli-installer-new`, `arch=(x86_64)`, deps `fzf gawk chwd cachyos-rate-mirrors … gptfdisk cryptsetup`).

**Hardware/kernel tooling.**
- `chwd` (Rust; `arch=(x86_64)`; deps `pciutils libusb lua pacman`): PCI-ID profile DB under `profiles/pci/…` installs GPU/NIC driver profiles; GPL-3.0.
- `cachyos-hello` welcome app (Rust; `arch=('x86_64')`); `kernel-manager` (Qt6; `arch=(aarch64 x86_64)`); `systemd-boot-manager` (`any`); `cachyos-settings`, `cachyos-hooks` (branding/os-release hooks), `cachyos-rate-mirrors`, `cachyos-mirrorlist`, `cachyos-keyring` — all `arch=('any')`; `cachy-chroot` (`x86_64`).

**Kernel.**
- `linux-cachyos` PKGBUILD: `arch=('x86_64')`; builds from `CachyOS/linux` release tarballs + `kernel-patches/<major>`; variants: bore, bmq, hardened, eevdf, rc, rt-bore, server, deckify, lts, default.
- Options: `_cpusched` ∈ {bore, bmq, hardened, cachyos (default, EEVDF), eevdf, rt, rt-bore}; `_processor_opt` ∈ {native, zen4, generic} (zen4 = znver4 x86 tuning); `_use_llvm_lto:=thin` default; O3 (`_cc_harder`), HZ=1000, full tickless, full preempt, THP=always; optional AutoFDO/Propeller/BOLT; optional ZFS, NVIDIA open module (`NVIDIA-Linux-x86_64-…`), r8125 NIC driver.
- Kernel config is an x86 config: `CONFIG_X86_64=y`, `CONFIG_X86_64_VERSION=1`, `CONFIG_GENERIC_CPU=y`, `CONFIG_LOCALVERSION_AUTO=y`.
- Build automation `script.sh` / `script-v3-v4.sh` / `script-znver4.sh`: sed `_processor_opt` to GENERIC/GENERIC_V3/GENERIC_V4, build in `pttrr/docker-makepkg[-v3|-v4]` containers, then `mv */*-x86_64{,_v3,_v4}.pkg.tar.zst*` into `repo/x86_64{,_v3,_v4}/…` and `repo-manage-util -p <repo> update`.

**Repositories / CPU tiers.** CachyOS sells four x86 tiers. README: "All CachyOS kernels are available in multiple architecture optimizations: `x86-64`, `x86-64-v3`, `x86-64-v4`, and `znver4`" (znver4/v4/v3 = full package sets; x86-64 = kernels only). Repo-add script detects ISA via `/lib/ld-linux-x86-64.so.2 --help | grep "<level> (supported, searched)"` and installs `install-repo.awk`/`install-v4-repo.awk`/`install-znver4-repo.awk` accordingly; key `F3B607488DB35A47`.

**Build infra.** Forked `devtools` ships `config/makepkg/x86_64.conf`, `x86_64_v3.conf` (+ `.d/`), `config/pacman/*-x86_64_v3.conf`, `setarch-aliases.d/x86_64_v3` — no aarch64 profiles. `repo-manage-util` (Rust) manages repo DBs.

**Handheld edition** targets x86 handhelds; README: "all packages compiled with avx2/avx512 including auto detection for cpu support"; Steam Deck OLED kernel patches.

## 3. Component/porting matrix

| # | Component (source path) | x86-specific content | ARM64 verdict |
|---|---|---|---|
| 1 | ISO profile `archiso/profiledef.sh` + `util-iso.sh` | `arch="x86_64"`, syslinux BIOS bootmode, xz BCJ x86, hard-coded `packages_desktop.x86_64`/`*-x86_64.iso` | Rewrite: UEFI-only, systemd-boot/GRUB arm64-efi; BCJ `arm64` or none; drop syslinux/memtest |
| 2 | Package list `archiso/packages_desktop.x86_64` | ucode pkg (amd/intel), memtest86(+efi), syslinux, refind, hyperv, linux-atm | Curate ARM list; keep/extend `linux-firmware` (incl. Qualcomm); add ARM firmware |
| 3 | `archiso/pacman.conf`, `cachyos-mirrorlist` | `[cachyos]` x86 mirrors only | Port: add `[cachyos-arm64]`, keep `$arch` substitution |
| 4 | `cachyos-repo-add-script` (`cachyos-repo.sh`, `install-*.awk`) | ISA test via x86-64 dynamic loader; tiers v3/v4/znver4 | Rewrite: ARM tier undefined; needs new repo-add flow |
| 5 | Calamares fork (`cachyos-calamares`, branches `cachyos*`) | pkg `x86_64`; bootloader-specific branches; netinstall lists imply x86 pkgs | Port + audit: rebuild aarch64; bootloader module for arm64; exclude refind/syslinux paths |
| 6 | CLI installer (`New-Cli-Installer`) | pkg `x86_64` | Port: C++23 portable; fix lists/pkg arch |
| 7 | `chwd` | pkg `x86_64`; PCI profiles for x86 GPUs/NICs/handhelds | Port: Rust builds; audit `--autoconfigure` on Snapdragon; no ARM profiles yet |
| 8 | `cachyos-hello` (CachyOS-Welcome) | pkg `x86_64` | Port: rebuild |
| 9 | `cachyos-kernel-manager` | — (already `arch=(aarch64 x86_64)`) | Ready |
| 10 | `cachyos-settings`, `cachyos-hooks`, `cachyos-rate-mirrors`, `systemd-boot-manager`, `mirrorlist`, `keyring` | `any`; sysctl/udev review needed; mirrorlist x86 entries | Mostly ready; review + ARM mirror wiring |
| 11 | `pacman` fork | `arch=('x86_64' 'aarch64')`; `source_aarch64=(fix-alpm-crate-for-aarch64.patch)` (adds `generate` feature to alpm crate in repo-add) | Ready (already aarch64-aware) |
| 12 | `linux-cachyos` kernel | `arch=('x86_64')`; x86 config; LTO/AutoFDO/BOLT x86 toolchain; zdumps: amd/intel-pstate, r8125, NVIDIA x86_64 | Port: arm64 config + target platform enablement; portable patch subset; defer LTO |
| 13 | `kernel-patches/<ver>/sched/*` (BORE, PRJC) | BORE touches 13 files, all `kernel/…`+`include/linux…` (no `arch/`); PRJC: 22 `kernel/sched/` files, 0 `arch/` | Port candidate: arch-neutral paths — but rebase/apply-test on arm64 required (inference, not validation) |
| 14 | `kernel-patches` misc x86 families (amd-pstate: `arch/x86/...`+`drivers/cpufreq/amd-pstate`; intel-pstate; i915-rt; t2; asus; itmt; nvidia IBT/BOLT; clang-polly; r8125) and device patches (Steam Deck, ROG Ally, Lenovo Go HID, amdgpu) | x86 device/toolchain-specific | Exclude from ARM v0 |
| 15 | `devtools` + docker-makepkg + repo tooling | makepkg/pacman confs + setarch only x86_64/x86_64_v3; x86 CI images | Port infra: add aarch64 confs; aarch64 build image or qemu-user chroot |
| 16 | Handheld/gaming stack (gamescope, jupiter-*, scx, ZFS default) | x86 handheld focus | Exclude v0 (revisit later) |

## 4. Artifact model (bounded overlay — not a whole-distro rebuild)

Delta accounting: upstream ~300 PKGBUILDs / 843 packaging files; the target is a delta of roughly 15–30 aarch64 packages on top of an existing aarch64 Arch base (Arch Linux ARM bootstrap tarball; site reachable at inspection). Everything else comes from the base distro's repos.

**A1 — bootable target-specific image** `cachyos-arm64-<date>.img`:
- Raw GPT disk image: FAT32 ESP with systemd-boot (or GRUB arm64-efi) + `vmlinuz-linux-cachyos-arm64` + initramfs; btrfs/ext4 root; UEFI-only (no syslinux/memtest/ucode artifacts). ISO/El-Torito not assumed on ARM firmware; `.img` is the primary medium.
- Target-specific = built for the Lenovo 83N3 / Snapdragon X1-26-100: arm64 kernel config with that platform's drivers/firmware, tuned cmdline; contains the CachyOS identity delta (branding hooks, settings, pacman fork, keyring, mirrorlist, systemd-boot-manager, chwd).
- "Truly bootable" is claimed only after gate G2 (device boot). Explicitly NOT: a renamed generic ArchLinuxARM rootfs, a renamed x86 ISO, an Ubuntu substitute, or anything implying official CachyOS support.

**A2 — the ARM repo** `cachyos-arm64`:
- Pacman repo layout `repo/aarch64/cachyos-arm64/` with signed `.db` built by their Rust repo-add (their pacman fork already carries the aarch64 patch) or `repo-manage-util`; hosts exactly the delta packages.
- Wired into the image via `pacman.conf` alongside base repos: `Server = file:///srv/cachyos-arm64/repo/aarch64` (or LAN) for v0; publishing/hosting = governance decision, deferred.

Build method (planning only): assemble an aarch64 chroot on **D:** (147 GiB free; keep C: at 36 GiB), build delta packages with `makepkg` inside it. Cross-build from the x86_64 host via qemu-user + binfmt is a candidate but **unvalidated**; native/on-device build is the fallback. Non-LTO GCC kernel build preferred (LTO thin default upstream is RAM-hungry; ~1.69 GiB free RAM today forces swap/sequencing).

## 5. Recommended minimal vertical slice (V0) — plan, untested

1. **S1 base**: aarch64 chroot from base distro bootstrap on D:; snapshot it.
2. **S2 kernel**: one package `linux-cachyos-<ver>-aarch64`: arm64-derived config + Snapdragon X platform enablement; GCC, no LTO/AutoFDO/BOLT; `_cpusched` = one of {eevdf, bore}; patch set = portable subset only (BORE/EEVDF sched, optionally bbr3/ntsync/zstd/hardened; exclude all x86 families from matrix row 14). Output = patch-subset decision + build recipe (not yet built).
3. **S3 boot**: mkinitcpio (udev + necessary firmware early), systemd-boot on ESP, minimal cmdline; UKI optional later.
4. **S4 identity/userland delta**: `pacman` fork, `cachyos-keyring`, `cachyos-mirrorlist`(+ARM), `cachyos-settings`, `cachyos-hooks`, `systemd-boot-manager`, `chwd`; optional: `cachyos-hello`, `kernel-manager` (already aarch64-capable).
5. **S5 artifacts**: seed A2; assemble A1; document build.

**Validation gates** (all currently UNTESTED): G0 patch-subset applies + builds on arm64 tree; G1 `qemu-system-aarch64` smoke boot of A1 (virt only — no device claims); G2 USB/UEFI boot on the 83N3 to a login prompt (Windows intact; Secure Boot policy decided); G3 baseline I/O (display + network at least); G4 `pacman -Sy/-Su` against A2 + base with signatures; G5 clean rebuild reproduces artifacts (checksums).

## 6. Blockers (ranked)

1. **Target enablement** (83N3 / X1-26-100): firmware, drivers, machine quirks — independent of CachyOS porting and the hardest gate; must be re-verified live per fact-check rules before relying on it.
2. **Kernel patch rebase**: portable subset needs arm64 apply/build; x86-only families excluded; BORE introduces `kernel/sched/bore.c` (434 lines) + hooks in fork/exit/futex — build-break risk until G0 passes.
3. **Toolchain divergence**: no LTO/AutoFDO/Propeller/BOLT/znver4; arm64 toolchain adoption; their scripts sed x86 optimizer switches.
4. **Installer fork**: aarch64 rebuild + module audit (bootloader config, netinstall lists, refind-ai path).
5. **Build infra**: devtools/docker-makepkg are x86-only; aarch64 equivalents or qemu chroot needed; RAM/disk constraints (build on D:, swap).
6. **chwd/mirror/keyring plumbing**: audit so `--autoconfigure` never pulls x86-only driver profiles; mirrorlist/keyring flow for ARM.
7. **Naming/governance**: unofficial build; CachyOS marks; licenses (GPL-2/3 mixes) — parent-owned.

## 7. Unanswered decisions

- Base distro: Arch Linux ARM bootstrap vs self-built aarch64 base; dependency policy.
- v0 scheduler: EEVDF (default, lower risk) vs BORE.
- Kernel version floor for the target; ACPI vs DT specifics; extra machine quirks allowed.
- v0 installer: image-only vs CLI installer vs Calamares fork.
- Boot: systemd-boot vs GRUB; UKI vs classic; Secure Boot policy.
- Repo hosting/signing authority (device-local vs LAN); when/if to publish.
- Whether LTO/per-SoC build variants are ever in scope.
- Live ISO-like UX vs installable image only.

## Appendix — key evidence URLs (fetched 2026-10-07; quotes abridged)

- https://github.com/CachyOS/linux-cachyos/issues/646 — closed `not_planned`; 1Naim: "There are no plans for this as of yet."
- https://raw.githubusercontent.com/CachyOS/CachyOS-Live-ISO/master/archiso/profiledef.sh — `arch="x86_64"`, `bootmodes=('bios.syslinux' 'uefi.grub')`, `-Xbcj x86`
- https://raw.githubusercontent.com/CachyOS/CachyOS-Live-ISO/master/archiso/packages_desktop.x86_64 — `amd-ucode intel-ucode memtest86+ memtest86+-efi syslinux refind …`
- https://raw.githubusercontent.com/CachyOS/CachyOS-Live-ISO/master/util-iso.sh — `packages_desktop.x86_64 → packages.x86_64`; `cachyos-…-x86_64.iso`
- https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/PKGBUILD — `arch=('x86_64')`; `_cpusched:=cachyos`; `NVIDIA-Linux-x86_64-…`
- https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/config — `CONFIG_X86_64=y`; `CONFIG_X86_64_VERSION=1`
- https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/script-v3-v4.sh — `GENERIC/GENERIC_V3/GENERIC_V4`; `mv */*-x86_64_v3.pkg.tar.zst* …/repo/x86_64_v3/cachyos-v3/`
- https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/README.md — "…multiple architecture optimizations: x86-64, x86-64-v3, x86-64-v4, and znver4"; tier table
- https://raw.githubusercontent.com/CachyOS/kernel-patches/master/7.0/sched/0001-bore-cachy.patch — 13 files, none under `arch/`
- https://raw.githubusercontent.com/CachyOS/kernel-patches/master/7.0/sched/0001-prjc.patch — 22 `kernel/sched/` files, 0 `arch/`
- https://raw.githubusercontent.com/CachyOS/kernel-patches/master/6.14/0001-amd-pstate.patch — `arch/x86/…`, `drivers/cpufreq/amd-pstate*`
- https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDS/master/pacman/PKGBUILD — `arch=('x86_64' 'aarch64')`; `source_aarch64=(fix-alpm-crate-for-aarch64.patch)`
- https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDS/master/cachyos-kernel-manager/PKGBUILD — `arch=(aarch64 x86_64)`
- https://raw.githubusercontent.com/CachyOS/CachyOS-PKGBUILDS/master/chwd/PKGBUILD — `arch=(x86_64)`
- https://raw.githubusercontent.com/CachyOS/cachyos-repo-add-script/develop/cachyos-repo.sh — ISA check `/lib/ld-linux-x86-64.so.2 --help`
- https://raw.githubusercontent.com/CachyOS/cachyos-calamares/cachyos/src/modules/chwd/main.py — `arch-chroot … chwd --autoconfigure`
- https://raw.githubusercontent.com/archlinux/archiso/master/README.rst — "Currently creating the images is only supported on Arch Linux…" (BIOS/UEFI artifacts)
