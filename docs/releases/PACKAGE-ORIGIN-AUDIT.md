# Package origin audit of the Maverick candidate root (2026-11-11)

Source: `output/airootfs.sfs` (sha256 `c5f93c71193030ec0008d4182d18b403f19ab6f28034c1963f84bdd0d987fdca`), pacman local and sync
databases, listing of all 179,477 entries. Tool: `tools/pkg-audit.py`; raw data: `output/pkg-audit.json` (private).

## Result

| Question | Finding |
|---|---|
| How many packages? | 603 |
| From the CachyOS binary repository? | **None.** The only `cachyos-arm64` repo entry is a local overlay (`file:///srv/cachyos-arm64`) with one package. |
| Arch Linux ARM packages | 602 (core 168, extra 434), unmodified; packager "Arch Linux ARM Build System". |
| Project-built packages | 1: `linux-cachyos-arm64 7.3.0rc3-1` (GPL-2.0-only, empty `source=()`, built locally from the pinned kernel tree plus the project's own Snapdragon patches). "CachyOS" is a name only. |
| Proprietary-licence fields | None found. 65 packages carry `custom`/`LicenseRef-*` fields (sudo, krb5, Qt dual licence, fonts, `linux-firmware-*`); all are free or redistributable-with-notice licences except the firmware set below. |
| Firmware in the root | 7,247 files under `/usr/lib/firmware`. Most come from Arch's `linux-firmware-*` split packages (WHENCE licences, redistributable with their licence texts). **Not publishable:** `/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/` (15 entries), staged from the owner's Windows installation. The UKI initramfs can also embed it (`kestrel_firmware` hook). |
| Branding strings | `cachyos` appears in 11 path names (kernel package, `/boot/vmlinuz-*`, dtbs directory, `/srv/cachyos-arm64`), none under `kestrel`. |

## What this changes

1. The earlier assumption that the image contains CachyOS repository binaries is **wrong**; the CachyOS repository-redistribution policy is
   not triggered by this root. The remaining CachyOS dependence is naming and any future use of CachyOS source or repo.
2. The real blockers for a public image are: the Windows-extracted 83N3 firmware (root and UKI), Arch Linux ARM terms and trademark use,
   the licence notices for the redistributed `linux-firmware-*` packages, and the GPL source offer for 602 + 1 packages.
3. The image is also much larger than needed: `linux-firmware-qcom` 536 MB, `-intel` 403 MB, `-nvidia` 152 MB, `-atheros` 140 MB, plus
   `-amd*`, `-broadcom`, `-mediatek`, `-realtek` and others. This laptop needs the Qualcomm (GPU/DSP) and Atheros (ath12k Wi-Fi) sets.
   Dropping the rest shrinks the squashfs and the licence surface and helps stay under GitHub's 2 GiB release-asset limit.

## Recommended replacement path (input to step 2)

- Rename the project-built kernel package and overlay repo (`linux-froodzos-arm64`, `/srv/froodzos-arm64`) so no CachyOS name is implied;
  update `/boot` file names, the dtbs directory, the UKI build and GRUB entries together, then retest.
- Keep Arch Linux ARM packages unmodified and pinned; publish the package list with versions, `pacman` database copy and a source offer.
- Build firmware-free: no `updates/qcom/x1p42100/LENOVO/83N3`, no embedded firmware in the UKI; keep `tools/setup-local-firmware.sh` for users.
- Prune `linux-firmware-*` to what this board needs; keep each retained package's licence files.
- Resolve ALARM branding: do not present the image as Arch Linux ARM; keep package names and mirror attribution as they are.

## Not verified

Exact Arch Linux ARM redistribution terms (to be read from their site and recorded), Mozilla trademark conditions for the branded
Firefox build, and which firmware files Wi-Fi/GPU/DSP need once pruned (needs a native test).
