# Decision record (ADR summary) - Kestrel OS ARM64 port

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


Status date: 2026-10-08. All decisions provisional/reversible until publication gates (G-D).

## Task 1.4 - ARMv8-A baseline verdict (2026-10-08)
- ALARM makepkg.conf sets `CFLAGS="-march=armv8-a"`; gcc defaults to armv8-a on this toolchain.
- Runtime proof: kernel 7.3.0-cachyos-arm64 booted under QEMU `-cpu cortex-a53` (ARMv8-A core) - G0b runtime PASS.
- Verdict: **ARMv8-A baseline accepted** for the first package set. Optimized tiers (armv8.2-a+) deferred to an additive repo, never replacing the baseline.

## Task 4.1 - Image assembler choice
- Chosen: **manual assembly** - our own squashfs live rootfs (`airootfs.sfs`) + stubble HWID-matched UKI (`BOOTAA64.EFI`) on a FAT32 stick, using mkinitcpio-archiso hooks for the overlay/boot semantics.
- Not chosen: ironrobin/archiso-aarch64 profile adaptation (deferred; its stubble integration premise is already satisfied by our own UKI; revisit if full ISO tooling is wanted for release media).
- Rationale: full control of kernel/UKI/repo wiring; avoids depending on an unpinned third-party profile for the M1 milestone.

## Confirmed decisions (second interview, 2026-10-07; re-asked and answered 2026-10-08)
- Signing: own keyring (master offline-held + builder build key); packages and DBs signed; local-only until per-artifact approval.
- Publication: per-artifact approval only; nothing published (G-D closed).
- Name: neutral provisional "Kestrel OS" (pick from Kestrel/Aster64/Peregrine/Lumen64 before publication; trivially changeable).
- Test fleet: this Lenovo (83N3) = sole verified hardware.
- Upstream message to admin@cachyos.org: agent drafts, user sends; NOT sent.
- Firmware: staged from this machine's Windows DriverStore, never redistributed (ADR-5).

## Operational notes (2026-10-08)
- WSL `--root` pacman operations with the download sandbox fail on 700-mode /home paths; offline verification used `--disable-sandbox`. Booted systems are unaffected.
- USB stick writes: raw/sector writes blocked by endpoint filter; FAT32 file-copy path is the supported method.
- Repo trust: builder + target keyrings carry master (100A8D5D...B61B722F) + build key, locally signed; `SigLevel = Required DatabaseOptional` for [cachyos-arm64].
