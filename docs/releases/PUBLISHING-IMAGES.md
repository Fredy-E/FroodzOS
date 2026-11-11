# Publishing an OS image: checklist and best practice

Status: **no image is published and none may be until the gates below pass.** This page is a plan, not an announcement.
The authority for gates is [POLICY.md](POLICY.md); rights are summarised in [NOTICE.md](../../NOTICE.md).

## 1. What exists today (and what is not an ISO)

The private development candidate is a **USB layout**: a GRUB menu, a unified kernel image (UKI) with a board device tree
selected per entry, and an Arch-style live root `airootfs.sfs` (about 1.75 GB). It is not an ISO9660 image. The build
scripts under `builder/` produce the squashfs root and the UKI; there is **no** pipeline yet for an ISO (xorriso/El Torito),
for a raw disk image, for signing, or for an SBOM. The current build can also embed vendor firmware
(`--require-local-firmware`); an image built that way **must never be published**.

## 2. Blockers that no packaging trick removes

1. **CachyOS repository content:** its policy prohibits redistributing the repository in other distributions. A public image
   needs a rebuild from source or replacement of every CachyOS-derived package, or written permission.
2. **Vendor firmware** (Qualcomm/Lenovo, extracted from the owner's Windows): no redistribution grant. Ship **firmware-free**
   and let the user stage their own with `tools/setup-local-firmware.sh`. Expect Wi-Fi, GPU and DSP to need that step.
3. **Arch Linux ARM base and branding:** terms and trademark use are unreviewed.
4. **GPL source:** shipping binaries requires the complete corresponding source or a valid written offer, for the kernel,
   GRUB, mkinitcpio/archiso hooks and every GPL package in the image.
5. Policy gates in [POLICY.md](POLICY.md): build manifest, exact-candidate retest, safe shutdown and recovery, owner authorisation.

## 3. Recommended release shape

| Item | Recommendation |
|---|---|
| Format | A compressed **raw USB disk image** (`.img.zst`, or `.img.xz`) written with `dd` or Rufus/balenaEtcher fits this laptop's layout best. A hybrid `.iso` is possible later but needs a new build pipeline. |
| Name | `FroodzOS-0.1.0-dev-maverick-arm64-83n3-<build-id>.img.zst`; the volume label and build id match the build manifest. |
| Where | **GitHub Releases** marked *pre-release*, not the git history. A single release asset is limited to **2 GiB**; split with `zstd` frames or `split -b 1900M` (document how to rejoin), or host the image elsewhere (Internet Archive, SourceForge or your own storage) and link it from the release notes. Never commit images to git (permanent history, 100 MB file limit, LFS quotas). |
| Integrity | `SHA256SUMS` in the release **and** a detached signature (`minisign` or GPG). Publish the public key and its fingerprint in the repository (`SECURITY.md`) and on your profile, never only next to the download. |
| Provenance | The build manifest `release/manifests/<build-id>.json` (source revision, pins, toolchain, digests, test receipts, limitations); an SBOM or plain package list; the exact commit tag. |
| Source offer | `SOURCE-OFFER.md` plus source tarballs (or exact upstream pins) for every GPL component, kept available for at least three years. |
| Firmware | Not included. A `FIRMWARE.md` explains the user-side staging and that the image works without it, with reduced hardware support. |
| Notes | Release notes with the support matrix from [CURRENT.md](CURRENT.md): what works, what does not, and the unsigned-boot caveat. |
| Verification | Download the asset from the public URL on a clean machine, check the hash and signature, write it to a spare USB stick and boot it, before announcing. |

## 4. Order of work

1. Decide the rights route with the owner (rebuild CachyOS-derived content, firmware-free runtime, branding).
2. Build a firmware-free image from pinned sources in the CachyOSBuilder environment and record the build manifest.
3. Add the missing pieces: raw-image assembler, signing, SBOM generator, source-offer bundle, release workflow.
4. Retest the exact candidate natively with the firmware-staging step; run the privacy and verification tools.
5. Owner authorisation, tag, pre-release upload, post-upload verification.
