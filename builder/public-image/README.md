# builder/public-image/ — firmware-free public image tools

These are the exact scripts used to produce build `maverick-public-dev-20261111.1` from the private development candidate.
They are published for transparency and review. They expect the maintainer's builder environment (a WSL2 distribution
`CachyOSBuilder` on Windows, ARM64, with `squashfs-tools` 4.7, `grub`, `dosfstools`, `sfdisk`, `zstd`, `qemu-system-aarch64`)
and the pinned private inputs named at the top of each script; paths are hard-coded on purpose and are not a general installer.

Order of use:

1. `build-public-root.sh` mounts the pinned root squashfs read-only and streams it through `public-root-filter.py`
   (tar to tar) into `sqfstar`, so nothing is unpacked to disk. The filter removes vendor firmware staged from a Windows
   installation, ten unneeded `linux-firmware-*` packages, the pacman keyring's private key, and CachyOS-named paths, and renames the
   project-built kernel package. It writes a report of every removal and rewrite.
2. `sfs-delta.py` compares `unsquashfs -ll` listings of input and output and classifies every difference. **Run it on every
   build**: a silent truncation is possible if the filter stops early (it happened once during development).
3. `build-public-uki.py` rebuilds the unified kernel images with a firmware-free initramfs (only the `.initrd` section changes;
   `uki-inspect.py` and `uki-initrd-list.py` show what a UKI contains).
4. `make-menu-public.py` derives the GRUB menu; `make-usb-image.sh` builds the GRUB EFI binary from the Arch Linux ARM `grub`
   package and assembles the raw GPT/FAT32 image (no root needed except for the loop mount).
5. `qemu-public.py` boots a copy of the image in QEMU (only `grub.cfg` is replaced in the copy) and checks identity, pruning
   and the touchpad driver self-test. This is an emulator test, not a hardware test.
6. `pkg-audit.py` lists packages with repository, packager and licences; `make-build-manifest.py` writes the exact-build
   manifest from measured sizes and hashes.

Licence: GPL-2.0-or-later. See `docs/releases/PUBLISHING-IMAGES.md` for the publishing checklist.
