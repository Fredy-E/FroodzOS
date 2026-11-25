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

## 6. Addendum for the 0.1.0-dev.3 build (2026-11-18): live-fix tools, full upgrade, persistence

The build `maverick-public-dev-20261118.2` is derived from the pinned Phase 1 root by `builder/public-image/build-root.sh`, like the dev.2 build. It differs as follows (file-listing comparison against the dev.2 root: 112,052 to 112,914 entries; 759 pacman packages, 17 more than dev.2).

| Point | Finding | Decision |
|---|---|---|
| New packages | `kexec-tools` (GPL-2.0-or-later), `dtc` (GPL-2.0-or-later), `efibootmgr` (GPL-2.0-or-later), `git` (GPL-2.0-only), `openssh` (BSD-2-Clause, BSD-3-Clause, ISC, MIT, 0BSD and public-domain parts), `evtest` (GPL, version not stated by the package), `strace` (LGPL-2.1-or-later), `alsa-utils` (GPL-2.0-or-later), `rtkit` (GPL-3.0-or-later and MIT) and their dependencies, all from the Arch Linux ARM `core` and `extra` repositories. | Unmodified ALARM packages with their licence texts (`/usr/share/licenses/`). `pkglist.tsv` lists every package with repository and licence. |
| `wireless-regdb` | The package licence field says `custom`; the shipped `/usr/share/licenses/wireless-regdb/LICENSE` is the upstream text. The database carries radio regulation data and is not an executable. | Unmodified package with its licence text. Accepted: the exact terms are those of that file; no separate legal review was done (open point, like the other `custom` entries in `pkglist.tsv`). |
| Full system upgrade | The build upgraded the existing packages (Plasma and KDE Frameworks 6.32, `qt6-webengine` and others). The pruned `linux-firmware-*` packages were again kept out (see section 4); the listing comparison shows no vendor firmware, no Firefox, no Arch logo files and no private keys. | Same filters as dev.2. |
| Kernel and boot | The kernel package, GRUB and the boot images are those of the previous build, with two device-tree changes (`fz-dtb-fixup.py`, `fz-board-touchpad.py`, original GPL-2.0-or-later tools in this repository) applied to the compiled device tree inside the first boot entry's image. | Source of the tools in this repository at the tag; no firmware is added by them. |
| Persistence | `fz-persist` (original code) mounts a user-created ext4 partition labelled `FROODZ_PERSIST` when the kernel option `fz_persist=1` is set, and `fz-stick-autorun` runs a script from the boot stick when `fz_autorun=1` is set. | Both are off by default; the image contains no such partition and no script. Release notes state that whoever holds a stick with persistence can read what is stored there. |
| Project code | `fz-persist`, `fz-stick-autorun`, `fz-kexec-uki`, `fz-board-touchpad.py` and the overlay drop-ins are original FroodzOS code under GPL-2.0-or-later. | Source in this repository at the tag. |
| Firmware | Still none of the 83N3 vendor firmware. | See `FIRMWARE.md`. |

Open points: those of sections 2, 3 and 5, plus the licence text of `wireless-regdb` and the `GPL` (version unspecified) licence field of `evtest`.

## 7. Addendum for the 0.1.0-dev.4 build (2026-11-20): sound userspace, shutdown fixes

The build `maverick-public-dev-20261120.2` is derived like dev.3 (the dev.3 root, then three further `build-root.sh` runs with a full upgrade each). File-listing comparison against the dev.3 root: 112,914 to 113,750 entries; 782 pacman packages, 23 more than dev.3, none removed. The pruned `linux-firmware-*` packages were again kept out; the listing comparison shows no vendor firmware, no Firefox, no Arch logo files and no private keys among the added or changed entries.

| Point | Finding | Decision |
|---|---|---|
| New packages | The sound userspace: `pipewire-audio`, `pipewire-pulse`, `pipewire-alsa`, `plasma-pa`, `pulseaudio-qt`, `alsa-card-profiles`, `libgpiod` and their dependencies (`lilv`, `lv2`, `serd`, `sord`, `sratom`, `zix`, `sbc`, `bluez-libs`, `libldac`, `liblc3`, `libfreeaptx`, `libebur128`, `libmysofa`, `spandsp`, `webrtc-audio-processing-1`, `libfdk-aac`). All unmodified Arch Linux ARM `extra` packages with their licence texts under `/usr/share/licenses/`; licences are MIT, LGPL-2.1/3.0, GPL-2.0-or-later, ISC/0BSD, BSD-3-Clause, Apache-2.0 and CC-BY-SA-4.0 (libgpiod documentation). | Accepted. `pkglist.tsv` lists every package with repository and licence. |
| `libfdk-aac` | Pulled in by the PipeWire Bluetooth codecs. Its licence is the Fraunhofer FDK AAC licence (`LicenseRef-Fraunhofer`), which allows redistribution in source and binary form under conditions, grants no patent licence and is not GPL-compatible. The licence text (`NOTICE`) is shipped by the package. | Unmodified ALARM package, shipped with its licence text; no FroodzOS code links against it. Accepted, with the patent position noted as an open point (same class as the codecs already inside `ffmpeg` and `vlc`). |
| Boot image | The first entry now uses `froodzos-maverick-dspM.efi`: the base boot image with a device tree patched by `fz-dtb-fixup.py` (rules `icc-orphan`, `orphan-usb3-phy`, `sound-nodp`, `wsa-right-gpio13`) and `fz-board-touchpad.py`, rebuilt by `builder/public-image/build-sound-uki.sh`; only the `.dtbauto` section differs from the base image. | Original GPL-2.0-or-later tools in this repository; no firmware is added. |
| Sound files | The root links `X1E80100-Romulus-tplg.bin` (already in the `linux-firmware-qcom` package that the image has carried since dev.1, reviewed in section 2) under the name the card requests, and ships board UCM profiles derived from the Qualcomm T14s profile of the `alsa-ucm-conf` package (BSD-3-Clause), without the DisplayPort parts. | UCM files keep their upstream licence header; the topology file is the unmodified package file. The audio DSP firmware itself is the laptop's own and is not shipped (`FIRMWARE.md`). |
| Project code | `fz-bootmnt-ro` (script and unit), the `iio-sensor-proxy` and `NetworkManager` stop drop-ins, the PipeWire/UCM overlay files and `build-sound-uki.sh` are original FroodzOS code under GPL-2.0-or-later. | Source in this repository at the tag. |
| Private add-ons | The sound start-up helper (ADSP reload, `fz-wsa-right` hold unit) used in the owner tests belongs to the private stick add-ons and is not shipped. | Not part of the release. |

Open points: those of sections 2, 3, 5 and 6, plus the Fraunhofer FDK AAC licence and patent position of `libfdk-aac`.

## 8. Addendum for the 0.1.0-dev.5 build (2026-11-22): sound set-up command, read-only internal drive

The build `maverick-public-dev-20261120.5` is derived from the dev.4 root by `build-root.sh` runs (three, one per build id .3 to .5) with a full upgrade (file-listing comparison in `maverick-public-dev-20261120.5.json`; no vendor firmware, no Firefox, no Arch logo files and no private keys among the added or changed entries).

| Point | Finding | Decision |
|---|---|---|
| `fz-sound-setup` | Original GPL-2.0-or-later script, unit and launcher. It copies six audio firmware files that the user supplies (searched in this order: `--source`, the machine's own Windows partition mounted read-only, a folder on the stick) into the live system's RAM overlay, `/usr/lib/firmware/updates/`. The files are the owner's own copies of Lenovo/Qualcomm drivers installed on the same laptop; they are not in the image, the release assets or the repository, are not uploaded, and vanish at power-off. | Accepted: same position as `tools/setup-local-firmware.sh` (section 2): the user stages their own firmware for their own use. `FIRMWARE.md` says not to share the files. |
| Read-only internal drive | A udev rule sets `ro=1` on `nvme*n*` block devices and `UDISKS_IGNORE=1`. | Original FroodzOS code; protects the user's data. |
| Boot image | Unchanged from dev.4 (`froodzos-maverick-dspM.efi`, same sha256); the experimental `--enable-nvme` boot image (`dspN`) is not shipped. | No change. |
| `--enable-nvme` | Experimental device-tree rule, off by default; tested on the 83N3 on 2026-11-22: kernel NULL-pointer oops, Wi-Fi and sound lost. Kept in the repository as a documented dead end. | Not part of any release image. |
| Private add-ons | The stick add-ons (autorun, persistence helpers, Claude Code add-on, firmware folder) used in the owner tests are not shipped. | Not part of the release. |

Open points: those of sections 2, 3, 5, 6 and 7.

## 9. Addendum for the 0.1.0-dev.6 build (2026-11-23): sound timer, swap command

The build `maverick-public-dev-20261122.1` is derived from the dev.5 root (r16) by one `build-root.sh` run (r17) with a full upgrade (file-listing comparison in `maverick-public-dev-20261122.1.json`; no vendor firmware, no Firefox, no Arch logo files and no private keys among the added or changed entries). The package set is unchanged (782 packages, 35 version updates, no new package).

| Point | Finding | Decision |
|---|---|---|
| `fz-sound-setup.timer` and changed service | Original GPL-2.0-or-later unit files; the sound set-up starts about 75 s after boot instead of inside the boot transaction. No new data is read or written. | Accepted. |
| `fz-swap-lr` | Original GPL-2.0-or-later script; writes one WirePlumber rule file in the user's own config directory and restarts the user's WirePlumber. | Accepted. |
| Boot image, firmware handling | Unchanged from dev.5 (same boot loader and kernel images); no firmware in the image, the release assets or the repository. | No change. |

Open points: those of sections 2, 3, 5, 6, 7 and 8.

## 10. Addendum for the 0.1.0-dev.7 build (2026-11-23): internal disk visible read-only, firmware read from Windows

The build `maverick-public-dev-20261123.1` is derived from the dev.6 root (r17) by one `build-root.sh` run (r18) with a full upgrade (file-listing comparison in `maverick-public-dev-20261123.1.json`; no vendor firmware, no Firefox, no Arch logo files and no private keys among the added or changed entries). The package set is unchanged (782 packages; `libseccomp` and `at-spi2-core` updated).

| Point | Finding | Decision |
|---|---|---|
| Boot image `froodzos-maverick-dspN2.efi` | The dev.4 sound boot image plus a device-tree change (internal NVMe PCIe controller and PHY enabled, interconnect votes dropped, one duplicated GPIO property deleted) made by the original GPL-2.0-or-later tool `fz-dtb-fixup.py --enable-nvme`; all other sections byte-identical to the base image. | Accepted; tested on the laptop in two owner boots. |
| Firmware from the user's Windows partition | `fz-sound-setup` mounts the Windows partition read-only and copies six audio firmware files into the live system's RAM overlay. They are the user's own copies of the vendor driver on the same machine; they are not in the image, the release assets or the repository, are not uploaded, and vanish at power-off. | Accepted: same position as section 8 (the user stages their own firmware for their own use). |
| Read-only rule | The dev.5/dev.6 udev rule (`ATTR{ro}`) did not take effect; the new rule runs `blockdev --setro` on the disk and its partitions. The correction is stated in the release notes and changelog. | Original FroodzOS code; protects the user's data. |

Open points: those of sections 2, 3, 5, 6, 7, 8 and 9.

## 11. Addendum for the 0.1.0-dev.8 build (2026-11-25): Waydroid, internal disk shown read-only

The build `maverick-public-dev-20261125.1` is derived from the dev.7 root (r18) by one `build-root.sh` run (r20) that adds packages and original overlay files (file-listing comparison and package audit in `maverick-public-dev-20261125.1.json`; no vendor firmware, no Android image, no Firefox, no Arch logo files and no private keys among the added entries).

| Point | Finding | Decision |
|---|---|---|
| `waydroid`, `lxc`, `dnsmasq`, `libgbinder`, `libglibutil`, `python-gbinder`, `python-dbus`, `python-gobject`, `gobject-introspection-runtime`, `libgirepository`, `rsync` and `wget` (12 packages added, 794 in total) | Unmodified Arch Linux ARM packages (Waydroid GPL-3.0-or-later, LXC LGPL-2.1-or-later, dnsmasq GPL-2.0-or-later, python-gbinder GPL-3.0-only; licences are in the packages and in `pkglist.tsv`), redistributed in the root image with source available from Arch Linux ARM; same position as the other packages (section 2). | Accepted. |
| Android system image | **Not included.** `fz-waydroid init` runs `waydroid init`, which downloads the LineageOS-based Android image from the Waydroid project's servers to the user's own persistent partition at the user's request; nothing is uploaded and no Google software (Play Store, GApps) is installed or downloaded by the script. | Accepted: the user obtains it themselves under its own licences; the notes say so and carry the Android trademark line. |
| `fz-waydroid`, polkit rule `90-froodzos-mount-internal.rules`, udev rule change | Original FroodzOS code, GPL-2.0-or-later. The polkit rule grants only the mount action to a local, active session; the mount is read-only (`ro,nosuid,nodev,noexec`) and the block device is flagged read-only by udev. | Accepted; protects the user's data. The earlier "hidden from the desktop" statement is superseded. |

Open points: those of sections 2, 3, 5, 6, 7, 8 and 9 (the polkit rule was later owner-tested on the dev.8 candidate: Dolphin opens the read-only disk without a password).

## 12. Addendum for the 0.1.0-dev.9 build (2026-11-25): persistent Waydroid data, suspend disabled

The build `maverick-public-dev-20261125.2` is derived from the dev.8 root (r20) by one `build-root.sh` run (r21) with a full system upgrade (file-listing comparison in `maverick-public-dev-20261125.2.json`; no vendor firmware, no Android image, no Firefox, no Arch logo files and no private keys among the added entries). The package set is unchanged (794 packages; nine versions updated).

| Point | Finding | Decision |
|---|---|---|
| `fz-persist`, `fz-persist.service` | Original FroodzOS code, GPL-2.0-or-later: binds a folder on the user's own FROODZ_PERSIST partition over `/var/lib/waydroid` so the user's downloaded Android image is kept; nothing is uploaded. | Accepted. |
| systemd `sleep.conf.d` and `logind.conf.d` drop-ins | Original configuration files, GPL-2.0-or-later; they switch suspend and hibernate off. | Accepted. |

Open points: those of sections 2, 3, 5, 6, 7, 8 and 9.
