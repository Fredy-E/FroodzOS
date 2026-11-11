# Source code for the FroodzOS development image

The image combines the project's own components with **unmodified binary packages from Arch Linux ARM** (ALARM). Most are
licensed under the GNU General Public License (GPL), the GNU Lesser General Public License (LGPL) or compatible free licences.
This page says where the corresponding source is and how to get it.

## Written offer (GPL-2.0 section 3(b), GPL-3.0 section 6(b))

For at least **three years after the last date on which we distribute this image**, we will give anyone who asks a complete
machine-readable copy of the corresponding source code of every GPL- or LGPL-licensed component contained in it, for a charge
no more than the cost of physically performing the distribution. Ask by opening an issue at
<https://github.com/Fredy-E/FroodzOS/issues> with the release name (for example `v0.1.0-dev-maverick`). This offer is valid for
anyone who received the image, from us or from someone who passed it on.

## Where the source is

| Component | Source |
|---|---|
| FroodzOS code, tools, board files, kernel patches, device tree, touchpad driver | This repository at the release tag. |
| Linux kernel (package `linux-froodzos-arm64`) | The pinned upstream tree and the cumulative patches in `reproducibility/` and `pkgs/`; build recipe in `pkgs/linux-cachyos-arm64/PKGBUILD` (the package was renamed after the build). |
| Unified kernel image stub (stubble) | `third_party/stubble/` licence and the pinned source in `reproducibility/`. |
| GRUB EFI binary and modules | Unmodified ALARM package `grub` (version in `pkglist.tsv`), GPL-3.0-or-later; source via the ALARM PKGBUILD and the upstream GRUB tarball. |
| Every other package | `pkglist.tsv` lists name, version, repository, licences and upstream URL. Sources are the ALARM package sources (`https://github.com/archlinuxarm/PKGBUILDs`, one directory per package) and the upstream archives those recipes reference. |

## What is not in the image

No firmware extracted from a Windows installation, no CachyOS repository package, no Firefox. See `FIRMWARE.md` and
`docs/releases/RIGHTS-REVIEW.md`.

## Verify what you have

`SHA256SUMS` and its signature `SHA256SUMS.asc` accompany the release; the signing key is described in
`docs/releases/SIGNING.md`. `pkglist.tsv` lists the contents of the root file system. This text is a good-faith statement of
the project's obligations, not legal advice.
