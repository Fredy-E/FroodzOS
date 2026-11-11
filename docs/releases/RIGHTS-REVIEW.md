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
