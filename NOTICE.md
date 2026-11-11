# Licensing and third-party notices

## Project licence (decided 2026-11-10)

The project owner selected **GPL-2.0-or-later** for **FroodzOS's own original source code and tools**
(for example the scripts under `builder/`, `tools/`, `testing/`, `tests/` and the original project sources
that carry no other licence). The licence text is in [LICENSE](LICENSE) (GNU General Public License,
version 2); "or later" means you may also use those files under any later version published by the Free
Software Foundation. New original source files should carry
`SPDX-License-Identifier: GPL-2.0-or-later`; adding that header to the existing original files is tracked
as follow-up work and the licence applies to them meanwhile.

This does **not** relicense third-party material. Existing explicit per-file grants and upstream licences
remain exactly as they are (see the table below). Documentation prose, research notes and history are
owner-created engineering material for which **no separate licence has been selected yet**; keep
provenance and existing notices. Public visibility and GitHub's hosting terms are not a substitute for a
licence.

## Components

| Material | Provenance / applicable terms |
|---|---|
| Linux kernel code and driver deltas | Pinned `jglathe/linux_ms_dev_kit` at `3f0d8691afa098ba378d7d5a3968f03219887719`; GPL-2.0 as governed by each source file and the kernel's COPYING / SPDX rules. See `third_party/linux/`. No compiled kernel is distributed here. |
| Lenovo 83N3 board DTS | Preserved `BSD-3-Clause` SPDX header and Qualcomm Innovation Center, Linaro and Jens Glathe copyright notices. See `third_party/linux/BSD-3-Clause`. The kernel tree contains other separately licensed includes; obtain them from the pinned upstream source. |
| stubble `linux.c` / alignment delta | `ubuntu/stubble` at `9f11278e080a5c4a77db6acf4c8f75c14412087a`; preserved `LGPL-2.1-or-later` SPDX header. See `third_party/stubble/LICENSE.LGPL2.1`. |
| `builder/initcpio/install/filesystems` | Derived from mkinitcpio 42.2; preserved `GPL-2.0-only` SPDX notice. GPL version 2 text is also included under `third_party/linux/GPL-2.0`. |
| `testing/boot-failure/control-reference/boot/grub/grub.cfg` | A captured Ubuntu control-image GRUB configuration kept as comparison evidence; Canonical/Ubuntu and GRUB terms apply, not the project licence. |
| `testing/boot-failure/uefi-package/usr/share/qemu/firmware/*.json` | QEMU firmware descriptor files from the EDK2/QEMU packages (upstream licences apply); retained as test-fixture evidence. |
| `boards/lenovo-83n3/kernel.config` | A captured Linux kernel configuration; the Linux kernel's GPL-2.0-only terms apply. |
| `pkgs/*/PKGBUILD` and patches | Packaging recipes derived from the CachyOS and Arch Linux ARM packaging; their upstream terms apply and the `license=` field describes the packaged software, not the recipe. Origin of each recipe is recorded in its history. |
| Original scripts under `builder/`, `tools/`, `tests/`, `testing/control/`, `boards/lenovo-83n3/touchpad/` | Tagged `SPDX-License-Identifier: GPL-2.0-or-later` (`tools/add-spdx-headers.py`). Frozen evidence under `testing/boot-failure/` is intentionally not edited (hash-pinned) and is covered by this project licence unless a file says otherwise. |
| Other source files with SPDX headers | Their existing file-specific licences apply. They are not overridden by the project licence above. |
| FroodzOS original code and tools | **GPL-2.0-or-later**, see above. |
| Original research, history and documentation prose | Owner-created; no separate licence selected yet. |

Historical filenames and local package names containing `cachyos` or `kestrel` record development
provenance; they do not establish affiliation, trademark permission, upstream binary-repository access
rights or an adopted public distribution identity. No upstream logos are bundled.

## Excluded material and rights for binaries

No Windows-extracted/vendor firmware, bootable kernel image, ISO/squashfs/VHDX, private signing key,
credential store, password database or raw private machine journal is redistributed. Referencing a
firmware filename is not a redistribution licence.

A **public bootable image is not available and is blocked on rights**, component by component:
the CachyOS repository policy prohibits redistributing its repository in other distributions; vendor
firmware extracted from an owner's own Windows installation carries no redistribution grant; the Arch Linux
ARM base-system terms and trademark/branding use have not been reviewed. Private owner-only development
images exist; they are not part of this archive. A public image needs its own component-by-component rights
and corresponding-source review.

Full third-party fetched web pages are not copied merely because they were used for research; authored
analysis and source URLs are retained. Any quoted upstream material retains its original authorship and terms.
