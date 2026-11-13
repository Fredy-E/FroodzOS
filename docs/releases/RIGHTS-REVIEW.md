# Rights review for the public image (2026-11-11)

This is a good-faith engineering review for a free hobby release, **not legal advice**. It records what was checked, the sources,
and the decisions taken. Items marked *uncertain* stay open and are repeated in the release notes.

## 1. What the image contains

Of 592 packages, 591 are unmodified Arch Linux ARM (ALARM) binary packages from `core` and `extra` (firmware split packages
included) and 1 is the project's own kernel package `linux-froodzos-arm64` (GPL-2.0-only, source and patches in this repository).
No CachyOS repository binary is present. The boot loader is the unmodified ALARM `grub` package (GPL-3.0-or-later).
See [PACKAGE-ORIGIN-AUDIT.md](PACKAGE-ORIGIN-AUDIT.md) and the shipped `pkglist.tsv`.

## 2. Findings and decisions

| Topic | Finding (sources) | Decision |
|---|---|---|
| ALARM redistribution | archlinuxarm.org publishes no repository-wide licence, FAQ or redistribution prohibition; it describes ALARM as a port whose packages are "released as-is" and mirrored. Redistribution therefore rests on each package's upstream licence. (https://archlinuxarm.org/about) *Absence of a statement is not a grant.* | Ship the packages unmodified, keep every licence file, attribute ALARM, state non-affiliation. Treat as accepted risk; documented here. |
| Arch / ALARM branding | The Arch trademark policy allows "based on / derived from Arch Linux" but not the marks as the product name or logo, and not implied endorsement (https://terms.archlinux.org/docs/trademark-policy). | Product name is FroodzOS. `os-release` (both copies) no longer says Arch; `LOGO=` removed; the four `archlinux-logo*` pixmaps are removed. `ID_LIKE=arch` stays as a descriptive compatibility field (*uncertain* whether it needs permission; it can be dropped on request). |
| Firefox | Mozilla's distribution policy covers unaltered copies from Mozilla; an ALARM-built, Firefox-branded binary is not clearly covered (https://www.mozilla.org/en-US/foundation/trademarks/distribution-policy/). | **Firefox is removed** from the public image. Users can install a browser themselves. |
| Firmware | Qualcomm (`LICENSE.qcom`), Atheros and Realtek firmware licences allow unmodified binary redistribution if the licence text and notices are kept and marks are not used (linux-firmware tag 20260309). | Ship only `linux-firmware-qcom`, `-atheros`, `-realtek`, `-whence` unmodified, with `/usr/share/licenses/linux-firmware-*`. Vendor 83N3 firmware from a Windows installation is **not** included. Whether `.zst` packaging counts as modification is *uncertain*; it is how ALARM ships them. |
| GPL source | GPL-2.0 s3(c) and GPL-3.0 s6(c) pass-along is not available (no upstream offer received). Links to third-party servers are enough for GPL-3.0 s6(d) but not clearly for GPL-2.0 s3(a). A written offer under s3(b) is valid but carries a real three-year duty (GPL FAQ, SFLC compliance guide). | Publish a written offer ([SOURCE-OFFER.md](SOURCE-OFFER.md)), the package list with versions and licences, and this repository (kernel, patches, tools). The maintainer commits to supply sources on request for three years after the last distribution. |
| GRUB (GPL-3.0) | An unsigned boot loader is not a licence problem; Installation Information duties apply to "User Products" sold with the software, which this is not (*least certain point*). | Ship GRUB unmodified from ALARM; no lock-in. Secure Boot is not supported. |
| Maintainer duty | Written-offer duty needs the maintainer to be able to deliver sources for three years. | To be confirmed by the maintainer in writing at release approval. Sources can be fetched from the ALARM PKGBUILD repository and the upstream URLs in `pkglist.tsv`; the maintainer will archive on request. |

## 3. Open points

1. ALARM has no explicit redistribution statement; a derivative that wants certainty should ask the ALARM maintainers.
2. `ID_LIKE=arch`, the `.zst` firmware packaging and the GRUB "User Product" scope are interpretations, not confirmed rulings.
3. The image ships default live accounts of the development image; they are documented in the release notes.

## 4. Addendum for 0.1.0-dev.2 (2026-11-11): file handlers added

The Phase 1 build adds 150 packages from the Arch Linux ARM `core` and `extra` repositories (the full list with versions and licences is the shipped
`pkglist.tsv`; the handler subset is in [../compat/HANDLERS-PHASE1.md](../compat/HANDLERS-PHASE1.md)) and upgrades 229 installed packages, because a partial
upgrade is not supported and the mirror keeps only current versions. Licences as recorded in the sync databases:

| Point | Finding | Decision |
|---|---|---|
| UnRAR licence | `unrar` and the RAR code in `7zip` use `LicenseRef-UnRAR`: decompression and redistribution are allowed, building a RAR compressor is not. | Ship unmodified with the licence files; the release notes and HANDLERS-PHASE1 say RAR is extract-only. *Uncertain:* DFSG-style distributions treat this licence as non-free; it does not forbid our use. |
| Info-ZIP | `zip` (`LicenseRef-Info-ZIP`) and `unzip` (custom) permit redistribution with notices. | Ship unmodified with licence files. |
| LibreOffice | MPL-2.0 and LGPL-3.0-or-later; The Document Foundation's name rules apply to modified builds. | Unmodified ALARM package, name kept; no FroodzOS branding added. |
| QtWebEngine and Falkon | `qt6-webengine` is pulled in by Okular and Gwenview; it bundles Chromium code under several licences listed in the package's licence files. Falkon is GPL-2.0-or-later. | Unmodified ALARM packages with their licence files. No Mozilla code. |
| Firmware | The full upgrade would have re-installed the ten pruned `linux-firmware-*` packages through the `linux-firmware` meta package. | The build keeps the old meta package (`--ignore linux-firmware`) and upgrades only the Qualcomm, Atheros, Realtek and licence packages; verified: no NVIDIA, Intel, AMD, MediaTek or other pruned firmware in the image. |
| Branding | The upgrade did not touch the `filesystem` package, so the FroodzOS `os-release` and the removal of the Arch logo files remain. | Verified in the emulator test (`no_arch_logo`, identity strings). |

Open points are unchanged from sections 2 and 3 (no explicit ALARM redistribution statement; `ID_LIKE=arch`; the GRUB "User Product" scope).

## 5. Addendum for the final 0.1.0-dev.2 build (2026-11-14): browsers, size reduction, diagnostics

The published build `maverick-public-dev-20261113.4` differs from the earlier dev.2 candidate as follows.

| Point | Finding | Decision |
|---|---|---|
| Falkon and Chromium | Falkon aborts under the kernel's user-namespace restriction; Chromium (tested in an intermediate build) was removed again to save space at the owner's request. | Neither is in the published image. |
| Helium 0.21.2.1 | Official `linux-aarch64` release tarball of imputnet/helium-linux, GPL-3.0 with Chromium components (BSD-3-Clause and others), signed; the tarball hash matches the hash GitHub shows and the signature verifies against the key in the project repository (fingerprint BE67 7C19 89D3 5EAB 2C5F 26C9 3516 01AD 01D6 378E). The key is not otherwise certified. | Shipped unmodified in `/opt/helium` (translations other than English, Arabic and French removed), licence texts and a source note in `/usr/share/licenses/helium/`, source offer extended in `SOURCE-OFFER.md`. Its name and logo are those of the upstream release; no separate trademark review was done (open point). |
| Zen Browser 1.24.2b | Official `linux-aarch64` release tarball of zen-browser/desktop, MPL-2.0; Firefox-based but not Firefox-branded, so the Mozilla trademark policy that required removing Firefox does not apply in the same way. The release tag ends in "b", which may mean a beta. | Shipped unmodified in `/opt/zen`, licence text and source note in `/usr/share/licenses/zen-browser/`. Branding terms of Zen's artwork were not reviewed separately (open point). |
| User namespaces | `kernel.apparmor_restrict_unprivileged_userns=0` (boot option and `/etc/sysctl.d` file) lets browsers create their sandbox. | Disclosed in the release notes; it is the normal setting on most distributions. |
| Pruning | The build removes firmware for other Qualcomm chip families and older Wi-Fi generations, translations except English, Arabic and French, documentation and manual pages, development headers and the two kernel images inside the root. Licence texts are kept. | Reduces what is redistributed; the package database still lists the removed files (`pacman -Qk` reports them missing). |
| Project code | `fz-smartlog`, `fz-backlight-max`, `fz-mount-image`, the supervisor change and the other overlay files are original FroodzOS code under GPL-2.0-or-later. | Source in this repository at the tag. |
| Firmware | Still none of the 83N3 vendor firmware; the experimental boot entry for the ADSP needs files the owner stages privately and is not part of the release. | See `FIRMWARE.md`. |

Open points: those of sections 2 and 3, plus the trademark and artwork terms of Helium and Zen, and the missing certification of the Helium signing key.
