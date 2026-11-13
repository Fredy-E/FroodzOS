# Releasing FroodzOS

This is the maintainer procedure for every FroodzOS version and build. The owner rule of 2026-11-11 is that every
version/build must be uploaded to GitHub as a git tag and/or a GitHub release, marked as a pre-release until it is
qualified. A build that exists only on the builder or on local media is not released.

The authority for promotion gates is [POLICY.md](POLICY.md). Publishing constraints are in
[PUBLISHING-IMAGES.md](PUBLISHING-IMAGES.md), signing in [SIGNING.md](SIGNING.md), and the rights position in
[RIGHTS-REVIEW.md](RIGHTS-REVIEW.md). The build tools are documented in
[`builder/public-image/README.md`](../../builder/public-image/README.md).

## 1. Names

| Item | Format | Example |
|---|---|---|
| Product development version | `0.1.0-dev`, then `0.1.0-dev.2`, `0.1.0-dev.3`, ... | `0.1.0-dev.2` |
| Development tag | `v<version>-<codename-slug>` | `v0.1.0-dev-maverick`, `v0.1.0-dev.2-maverick` |
| Build id | `<codename-slug>-public-dev-YYYYMMDD.N` | `maverick-public-dev-20261111.2` |
| Qualified alpha tag | `v0.1.0-alpha.1`, as proposed in POLICY.md | no such tag exists yet |

The validator accepts `-dev` with a `.N` counter. Start with the plain `-dev` version and increment the counter for
each later development build of the same version; never reuse a number. The codename slug is the selected codename
in lower case with spaces replaced by hyphens, as recorded in `release/codenames.json`.

A patch keeps its series codename: product `1.0.1` is Sherman and product `1.5.1` is Super Sherman. Component,
fixture, board and build identifiers are separate namespaces and never become a product release. For a qualified
alpha, use the exact proposed display **FroodzOS 0.1 Maverick — ARM64 Alpha**; do not silently promote a development
build to it. See [POLICY.md](POLICY.md).

## 2. Release checklist

- [ ] **Confirm scope and rights.** The image is for the Lenovo IdeaPad Slim 3 15Q8X10 (83N3) only. Repeat the rights
  review for every package added since the last release. Confirm that the image contains no vendor firmware (no 83N3
  firmware extracted from Windows), no Firefox and no Arch logos, and that the source offer covers everything GPL- or
  LGPL-licensed in the image.
- [ ] **Build the candidate.** Use the tools in `builder/public-image/`: `build-public-root.sh` for the filtered root,
  `build-public-uki.py` for the UKIs, `make-menu-public.py` for the GRUB menu and `make-usb-image.sh` for the raw USB
  image. Record the exact source revision, toolchain and input hashes.
- [ ] **Compare file listings.** Run `sfs-delta.py` on every build and review every difference. A silent truncation is
  possible if the filter stops early; it happened once during development.
- [ ] **Emulator test.** Run `qemu-public.py` against a copy of the image. Record what it checked. This is an emulator
  test, not a hardware test.
- [ ] **Native test.** Boot the exact candidate on the 83N3 and record the result. If the exact image cannot be tested
  natively, say so in the release notes and state which build was tested instead.
- [ ] **Compress the image.** Compress the raw image with `zstd -19`. A single GitHub release asset must be under
  2 GiB; check the compressed size before uploading. If it is too large, split it and document how to rejoin, or use
  the alternative hosting route in [PUBLISHING-IMAGES.md](PUBLISHING-IMAGES.md).
- [ ] **Generate the package list.** Produce `pkglist.tsv` from the built root. The read-only `pkg-audit.py` supplies
  package names, versions, repositories, packagers and licences for the list.
- [ ] **Write the build manifest.** Create `release/manifests/<build-id>.json` from measured values with
  `make-build-manifest.py`. It must bind the source revision and any dirty delta, pins, toolchain, artifact paths,
  byte counts, digests, test receipts and known limitations. Do not use placeholders or copy an old approval.
- [ ] **Create checksums and signature.** From the directory holding the release assets:

  ```
  sha256sum <assets> > SHA256SUMS
  gpg --local-user 1432DC7DB54196FF471EFD57A558604E9E92C7EA \
    --armor --detach-sign --output SHA256SUMS.asc SHA256SUMS
  ```

  The checksum file covers every uploaded asset except `SHA256SUMS` and `SHA256SUMS.asc`. Sign with the release key
  described in [SIGNING.md](SIGNING.md), not a personal key.
- [ ] **Update the documentation.** Add the release to [CHANGELOG.md](../../CHANGELOG.md) and create
  `docs/releases/RELEASE-NOTES-<version>-<codename>.md` using the list in section 5 below.
- [ ] **Open the pull request.** The ruleset on `main` requires a pull request and 8 checks: the jobs in `integrity`,
  `tests` (four matrix jobs), `lint` (two jobs) and `privacy`.
- [ ] **Merge only when all eight checks are green.** Do not merge a red or pending pull request.
- [ ] **Tag the merge commit.** On `main`, confirm the commit is the merge commit, then create and push an annotated
  tag once:

  ```
  git switch main
  git pull --ff-only
  git log -1 --oneline
  git tag -a v0.1.0-dev.2-maverick -m "FroodzOS 0.1.0-dev.2 Maverick"
  git push origin v0.1.0-dev.2-maverick
  ```

- [ ] **Create the GitHub release.** Use the tag, mark it as a pre-release, use the release notes file and upload all
  required assets:

  ```
  gh release create v0.1.0-dev.2-maverick \
    --prerelease \
    --title "FroodzOS 0.1.0-dev.2 Maverick" \
    --notes-file docs/releases/RELEASE-NOTES-0.1.0-dev.2-maverick.md \
    FroodzOS-0.1.0-dev.2-maverick-arm64-83n3-nofw.img.zst \
    SHA256SUMS SHA256SUMS.asc maverick-public-dev-20261111.2.json \
    pkglist.tsv FIRMWARE.md SOURCE-OFFER.md RIGHTS-REVIEW.md \
    froodzos-release-public.asc
  ```

  The asset names above are examples; use the actual image name, build id and files from this build. The image is a
  release asset, never a git object.
- [ ] **Verify the published release.** Download the assets from the public URL on a clean machine with a clean
  keyring, not from the signing environment:

  ```
  export GNUPGHOME="$(mktemp -d)"
  gpg --import froodzos-release-public.asc
  gpg --fingerprint 1432DC7DB54196FF471EFD57A558604E9E92C7EA
  gpg --verify SHA256SUMS.asc SHA256SUMS
  sha256sum -c SHA256SUMS --ignore-missing
  ```

  Compare the fingerprint with [SIGNING.md](SIGNING.md) as it appears at the tag and, if possible, with a second
  source. Compare each local digest with the asset digest GitHub shows. If verification fails, do not move or delete
  the tag; publish a new version instead.

## 2b. Graphics check (lesson of 0.1.0-dev.2)

A full system upgrade can change the Plasma/KWin version and break the bounded graphics session even though the emulator boot passes (the
graphics supervisor's preflight fails in QEMU, so the emulator never starts a session). Before publishing any build that upgraded Plasma, boot it on
the laptop and read the `kestrel-graphics-supervisor` lines in the boot log (`KESTREL_GRAPHICS_SESSION_ACCEPTED_MONITORING` must not be followed by
`MONITOR_SESSION_LOST`), and run `egltest.py` for the EGL chain. See `builder/public-image/README.md`.

## 3. Required release assets

| Asset | Content |
|---|---|
| image `.img.zst` | Compressed raw USB image for the 83N3; under 2 GiB per GitHub asset. |
| `SHA256SUMS` | Digests of the other release assets. |
| `SHA256SUMS.asc` | Detached OpenPGP signature over `SHA256SUMS`, made with the release key. |
| `<build-id>.json` | Exact-build manifest from `release/manifests/<build-id>.json`. |
| `pkglist.tsv` | Package list with versions, repositories and licences. |
| `FIRMWARE.md` | Firmware-free statement and user-side firmware staging. |
| `SOURCE-OFFER.md` | Written source-code offer and source locations. |
| `RIGHTS-REVIEW.md` | Rights review and its open points. |
| public key | `froodzos-release-public.asc`, the release public key. |

The release notes are the body of the GitHub release, not a separate required asset.

## 4. Rules

- **One tag and one release per version/build.** Every version/build is published; do not leave a build only on the
  builder or on local media.
- **Never move or delete a published tag.** If a mistake is found after publication, keep the tag and release and
  issue a new version with a new build. Do not rewrite history.
- **Pre-release until qualified.** Development and candidate releases use `--prerelease`. Only omit it after the owner
  declares a qualified release under [POLICY.md](POLICY.md).
- **No forbidden content.** No vendor firmware (including the 83N3 firmware extracted from Windows), no Firefox and no
  Arch logos in any image. Follow [RIGHTS-REVIEW.md](RIGHTS-REVIEW.md) for every package added.
- **Source offer duty.** The three-year written source-offer duty runs from the last distribution of each release,
  not from its build date. See [SOURCE-OFFER.md](SOURCE-OFFER.md).
- **Authorization.** Do not tag or publish an exact build without the owner's explicit authorization for that build.
- **No images in git.** Release images and archives are GitHub release assets, never committed objects.

## 5. What a release note must say

Every release note must state:

- **Supported laptop only.** The Lenovo IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100). It will not boot on
  other machines.
- **What works and what does not.** Use the tested scope, not the project goal. State which exact build was tested on
  the laptop and which was tested only in an emulator; label unverified items as unverified.
- **Secure Boot must be off.** The boot loader and kernel are unsigned.
- **How to verify.** The release-key fingerprint, the `gpg --verify SHA256SUMS.asc SHA256SUMS` step and
  `sha256sum -c SHA256SUMS --ignore-missing`.
- **How to write the image.** Decompress the `.img.zst`, use a raw-image writer (`dd`, Rufus in DD mode or
  balenaEtcher), and state clearly that **writing erases the whole USB stick**; tell the reader to double-check the
  target device.
