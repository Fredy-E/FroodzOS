# CachyOS-derived ARM64/Snapdragon distro — package, repo & image strategy (v2)

Checked **2026-10-07** (Asia/Beirut). Scope per latest direction: **public, multi-device Snapdragon/ARM64 distro**; milestones: (1) bootable **liveUSB with default image/apps**, (2) kernel, (3) apps + optimizations, (4) gaming; storage: **one main folder on D:**; no cloud budget or other hosts specified yet; "Oracle ARM64" placement unresolved. Packaging/repo/image strategy only — hardware/boot and Cachy components are other tracks. Quotes fetched live 2026-10-07 unless dated.

## 1. Current state (verified today)

**CachyOS:** issue #646 closed **not_planned**; staff 2025-12-18: *"There are no plans for this as of yet. x86_64 also isn't dying any time soon."* (https://github.com/CachyOS/linux-cachyos/issues/646). Staff `ptr1337` (2024-06-19, unchanged 2026): *"we would like to have an ARM(64) variant, but we would also like to base on archlinux. Since archlinuxarm is not in the best state, we are waiting that the situation improves."* (https://discuss.cachyos.org/t/arm-future-for-cachyos/727).

**Arch Linux:** only x86_64 is official; ports are *"unofficial … until they are integrated"* (https://ports.archlinux.page/). AArch64 status: *"there is no RFC for this architecture. Any packages available for this architecture are: not built with Arch Linux infrastructure, not signed by Arch Linux staff, and not hosted on Arch Linux domains/mirrors."* (https://ports.archlinux.page/aarch64/). Framework RFC 0032 is merged (https://rfc.archlinux.page/0032-arch-linux-ports/).

**ALARM today:** alive but thin. Repo synced **2026-10-07 07:38 GMT**; `glibc 2.43+r22` (built 2026-05-03), `chromium 153.0.8010.36-1`, `linux-aarch64 7.2.9-1`, `plasma-desktop 6.7.5-1` (https://archlinuxarm.org/packages/aarch64/). Countervailing: broken forum registration / ignored chromium PRs (https:[REDACTED_EMAIL]/message/3CE2E7LFXMKIRZN7YHYJEZF3RWRFWJ5R/), Sept–Oct 2025 mirror outage (https://archlinuxarm.org/forum/viewtopic.php?p=73733), keyring history: PR *"ditch the master keys, sign and trust the builder key directly"* merged 2024-04-19; `archlinuxarm-keyring 20240419-2`; DBs unsigned by design: *"the repository database files are not signed in order to limit the exposure of private keys"* (https://archlinuxarm.org/about/package-signing). Rootfs tarball `ArchLinuxARM-aarch64-latest.tar.gz` ~791 MiB, signed.

**Industrial signal:** Collabora+Valve's Holo Core: *"a pure `aarch64` port of Arch Linux to be used as the basis for the OS running on the Steam Frame"*, public binaries/containers (https://www.collabora.com/news-and-blog/news-and-events/building-an-arch-linux-aarch64-port-for-holo-core.html, 2026-07-17). Arch dev tpowa's **Archboot** ships aarch64 ALARM ISOs claiming *"reproducible bootable media"* — newest 2026.10.07, kernel 7.2.9 (https://archboot.com/).

## 2. Policy & legal gate (verified)

CachyOS Repository Usage Policy (https://wiki.cachyos.org/policy/repository_policy/): §6 — *"This policy defines 'redistribution' as the behaviors of inclusion of the CachyOS repository (and its mirrors) or packages obtained from the CachyOS repository as a part of the distributed image of the operating system or sysroots. Redistribution also includes the behaviors of Linux distributions to provide the utilities that enable CachyOS repository by users' choice, or to provide any distributed or official document that guide users to enable CachyOS repository … by their means. End users and third-party mirrors are not subject to the redistribution policy."* §7 — *"Redistribution of the CachyOS repository (and its mirrors) in any unauthorized Linux distribution … is STRICTLY PROHIBITED."* §8 permits mirrors that keep data unchanged.

Consequences for a public image: include **no** CachyOS binaries in image/sysroots; point no installer/pacman at Cachy mirrors; ship no "enable CachyOS repo" helper or guide; host everything yourself. Building from CachyOS **source** PKGBUILDs is a separate matter (the policy governs repository redistribution, not GPL rights; sources: https://github.com/CachyOS/CachyOS-PKGBUILDS — verify each repo's license before reuse; a Cachy dev's statement that PKGBUILDs are GPL-3.0 is unverified until checked per-repo). **No standalone branding policy document was found** in the wiki policy directory as of 2026-10-07 (only code_of_conduct, community-rules, privacy_policy, repository_policy, terms_of_service) — naming/logo/`os-release` branding is a **gate**: contact admin@cachyos.org before using the "CachyOS" name; use a neutral project name meanwhile (their `cachyos-branding` hook shows what must not be carried over: `ID=cachyos`, logo, URLs). Not legal advice. Net: **own ARM64 repo + own keyring is mandatory** — which also solves the AUR gap (aarch64-only packages can't live in AUR: https://www.phoronix.com/news/Arch-Linux-AUR-Requires-x86_64).

## 3. Base & resolution strategy (tradeoffs)

- **A. ALARM**: widest hardware coverage, signed pkgs; but single build key, unsigned DBs, bursty syncs, closed maintainer culture; no Calamares.
- **B. Arch Linux Ports AArch64 (drzee.net)**: built from upstream PKGBUILD tags on ARMv8.2 cloud infra, *"no cross-compilation"*, wide coverage; own key (`…/arch/extra/os/aarch64/public.key`), monthly `archlinux-bootstrap-2026.10.01-aarch64.tar.zst`, `[forge]` for aarch64-only pkgs (`archports-keyring`, `dtbsync`), `archinstall 4.5`, Plasma 6.7.5/Gear 26.08, Qt6 — but officially unsanctioned/unaudited (dashboard is JS-only tonight; RFC snapshot: core 91.32 %, extra 81.61 % of x86 set). **No Calamares** there either.
- **C. Full self-hosted rebuild**: pool alone 33–61 GiB per RFC 0032, plus archives/chroots; weeks-to-months solo. Reject as first step; grow into it via §9 gates.
- **D. Chosen shape (provisional)**: liveUSB based on **B (fallback A)** using only Arch-family packages, plus **our own signed `[overlay]` repo** carrying aarch64 builds of Cachy-style tools/settings/kernels and aarch64-only extras (FEX/Box64 etc.) — the port's own pattern (forge/`archports-keyring`), policy-clean.

## 4. Builders & cross/native constraints

`devtools` (`mkarchroot`, `makechrootpkg`, `arch-nspawn`) + `arch-install-scripts` on aarch64 is the native path; the port's open-source builder uses `makechrootpkg --ignorearch` plus a 2-stage gcc/glibc/binutils bootstrap (https://github.com/solskogen/archlinux-aarch64-builder). Cross: **distcc** is *"the official cross-compiling method used at Arch Linux ARM"* with matched crosstool-ng toolchains (https://archlinuxarm.org/wiki/Distcc_Cross-Compiling); kernel cross-builds use `ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-`; plain `makepkg` cross-runs are unsupported (target deps missing). `qemu-user-static`+binfmt works but is slow, with SUID/:FP quirks (Collabora walkthrough). Image builders: `archiso` custom profiles; **ironrobin's `archiso-aarch64`** — *"builds on Arch Linux's upstream releng profile with a thin compatibility layer powered by stubble, allowing a single image to boot across supported AArch64 laptops"* (https://codeberg.org/ironrobin/archiso-aarch64 — the Slim 3 is NOT on its device list); **Archboot** (`archboot-arm`, `qemu-user-static` for x86 hosts, pacman-aarch64-container); **mkosi** (*"a fancy wrapper around dnf --installroot, apt, pacman and zypper"*, `Architecture=arm64`, qemu boot — https://mkosi.systemd.io/). Free native CI: GitHub arm64 runners for **public** repos, 4 vCPU/16 GB (https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/) — requires publishing sources, a deliberate decision. Cheapest builder: the target Snapdragon laptops themselves (aarch64), inside a **separate WSL2 distro** (not Kali).

## 5. ABI / arch / keyring separation

Keep per-source separation: `archlinux-keyring` ≠ `archlinuxarm-keyring` ≠ `archports-keyring` ≠ our new project keyring. RFC 0032 explicitly weighed *"creating a separate keyring to more clearly separate trust"* — adopt it. PKGBUILDs: keep `arch` arrays as-is where possible; use pacman 7.1+ arch-restricted split packages or `source_aarch64=()`; `--ignorearch` is a local workaround, not an upstreaming strategy (https://ports.archlinux.page/). ISA: ports is **ARMv8.2-A+**; the one-way door matters — *"programs compiled with -march=armv8.2-a will include the LSE feature and are not expected to work in general on ARMv8-A"*. Optimized tiers must be additive. No multilib on aarch64.

## 6. Signing / update / reproducibility pipeline

Own model: offline-held master key → build key signs every package; sign DBs too (fixing the ALARM/drzee gaps: drzee `core.db.sig` 403, ALARM DBs deliberately unsigned); ship `*-keyring` + mirrorlist packages; bootstrap via `pacman-key`. Reproducibility: Arch's stated *"strong commitment towards reproducible builds"* (RFC 0032) + `archlinux-repro`; Archboot claims reproducible media; **no ARM rebuilderd instance found — unknown; plan `SOURCE_DATE_EPOCH`-clean builds anyway**. Updates: rolling `pacman -Syu` against our own mirror (policy-safe).

## 7. Qt / KDE / Calamares

KDE/Qt6 are packaged on both bases (versions in §3) — a Plasma default image is feasible. **Calamares is in neither ARM repo** (0 hits in both indexes; ALARM page 404s). CachyOS's installer is a Calamares fork (https://github.com/CachyOS/cachyos-calamares) whose Qt/KDE-Frameworks deps exist on both bases, so it can be built for aarch64 — or use `archinstall` (present on drzee; ironrobin notes installer caveats: no UKI support). Installer choice is also a branding decision (§2).

## 8. x86 gaming (no compatibility promises)

Box64: *"run x86_64 Linux programs (such as games) on non-x86_64 Linux systems, like ARM"*, DynaRec *"5 to 10 times"* interpreter speedup (https://github.com/ptitSeb/box64, manpage). FEX: *"run x86 applications on ARM64 … alongside Wine/Proton"*; needs ARMv8.0-a + FEAT_FP/FEAT_CRC32, an x86-64 rootfs, reportedly 4 KiB pages (https://fex-emu.com/, https://github.com/FEX-Emu/FEX/issues/4348). Proton ARM64 exists but is Valve's Steam-Frame branch: *"rebuilt natively for ARM instead … using a program called FEX"* (IGN interview); FEX code cache enabled on Proton Experimental (ARM) Sept 2026 (GamingOnLinux). **Anti-cheat: no** — Proton's EAC/BattlEye bridges build x86_64/i386 only; Epic docs/FEX issue say Linux Arm64 unsupported; kernel-level AC explicitly *"not currently supported"* (https://partner.steamgames.com/doc/steamhardware/proton). Adreno driver maturity is a separate risk (FEX: Snapdragon X2 "don't yet support Linux out of the box… with 7.1 or 7.2 we might even have a working GPU"). Expect: single-player/older titles maybe; ranked multiplayer no; performance below x86.

## 9. Gated MVP — liveUSB first, D: only

- **Gate 0 (answers):** budget/hosts ("Oracle ARM64" = what exactly?), maintainer/cadence, naming, first-device priority, parent's kernel/DTB/firmware status.
- **Gate 1 (zero-cost):** on the laptop, under **D:\cachyos-arm\** (single top folder; subdirs src/chroot/repo/keys/artifacts inside): import a bootstrap tarball (drzee/ALARM) into a **separate WSL2 distro** (no Kali changes) or chroot; build 3–5 packages incl. one CachyOS PKGBUILD via `makechrootpkg --ignorearch`; sign with a throwaway own key; `pacman -U` verify. Success = signed aarch64 package built at home.
- **Gate 2 (liveUSB MVP):** archiso/archboot profile (template: ironrobin) producing a bootable USB image for the first Snapdragon device(s); default apps; **only own/Arch-family packages**; no Cachy binaries. Blocked on the parent track for kernel/DTB/firmware.
- **Gate 3 (repo):** stand up the project repo + keyring + mirrorlist; publish `[overlay]`; decide DB signing; publish the policy-safe "no Cachy mirrors" statement.
- **Gate 4 (scale):** CI on free public-repo arm64 runners; reproducibility checks; then kernel/optimizations/gaming long tail.

**Estimates (clearly estimates):** rootfs 1–2 GiB (ALARM tarball 791 MiB measured; archboot ISOs 300 MB–1.0 GB measured); build workspace + chroot + cache ≈ **20–40 GiB on D:** (est.); builds want **≥4–8 GiB free RAM** (host had 1.69 GiB free — must be freed or offloaded); MVP image work ≈ **days** (est.); full multi-device port with optimized tiers ≈ **weeks–months of sustained effort** (est.).

## 10. Open questions

1. "Oracle ARM64" — free-tier builder, paid VPS, or something else? (Parent asks next.)
2. Public hosting: where do repo/ISO/signing keys live, and who owns the keys?
3. Project name/branding (gate per §2) and "unofficial port" disclosure language.
4. Device priority list + who validates each device (parent track).
5. Kernel strategy: mainline + dtbs vs carried patches; 4 KiB pages for FEX.
6. Calamares vs archinstall for the liveUSB.
7. Budget ceiling for CI/bandwidth beyond free tiers.
8. Ask admin@cachyos.org for written clarity on source-rebuild + naming before Gate 3 goes public.
