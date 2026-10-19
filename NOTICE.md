# Licensing and third-party notices

## No blanket relicensing

Publication was requested by the project owner on 19 October 2026. A new project
license was asked about but no choice was received. **No MIT, GPL or other
blanket license is being applied to the whole repository.** Existing explicit
per-file grants remain valid; otherwise no additional reuse grant is asserted
for original unlicensed material. The owner may make that choice separately.
Public visibility and GitHub's hosting/fork terms are not a substitute for a
software license.

## Components

| Material | Provenance / applicable terms |
|---|---|
| Linux kernel code and driver deltas | Pinned `jglathe/linux_ms_dev_kit` at `3f0d8691afa098ba378d7d5a3968f03219887719`; GPL-2.0 as governed by each source file and the kernel's COPYING / SPDX rules. See `third_party/linux/`. No compiled kernel is distributed here. |
| Lenovo 83N3 board DTS | Preserved `BSD-3-Clause` SPDX header and Qualcomm Innovation Center, Linaro and Jens Glathe copyright notices. See `third_party/linux/BSD-3-Clause`. The kernel tree contains other separately licensed includes; obtain them from the pinned upstream source. |
| stubble `linux.c` / alignment delta | `ubuntu/stubble` at `9f11278e080a5c4a77db6acf4c8f75c14412087a`; preserved `LGPL-2.1-or-later` SPDX header. See `third_party/stubble/LICENSE.LGPL2.1`. |
| `builder/initcpio/install/filesystems` | Derived from mkinitcpio 42.2; preserved `GPL-2.0-only` SPDX notice. GPL version 2 text is also included under `third_party/linux/GPL-2.0`. |
| Other source files with SPDX headers | Their existing file-specific licenses apply. These are not overridden by this notice or the absence of a root LICENSE. |
| Original research/history/test documentation and unlicensed scripts | Owner-created engineering material; no new blanket license has been selected. Keep provenance and existing notices. |

Historical filenames and local package names containing `cachyos` or `kestrel`
record development provenance; they do not establish affiliation, trademark
permission, upstream binary-repository access rights or an adopted public distro
identity. No upstream logos are bundled.

## Excluded material

No Windows-extracted/vendor firmware, bootable UKI, ISO/squashfs/VHDX, private
signing key, credential store, password database or raw private machine journal
is redistributed. Referencing a firmware filename is not a redistribution
license. A public bootable image needs its own component-by-component rights
and corresponding-source review; this source archive is not that release.

Full third-party fetched web pages are not copied merely because they were used
for research; authored analysis and source URLs are retained. Any quoted upstream
material retains its original authorship and terms.
