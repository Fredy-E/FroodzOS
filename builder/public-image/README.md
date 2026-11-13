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

## Graphics session (added 2026-11-12)

Plasma 6.8 (in the 0.1.0-dev.2 root) no longer accepts `KWIN_COMPOSE=Q` on the DRM platform: KWin exits and the bounded graphics session is torn
down. The original `builder/diagnostics/kestrel-graphics-env.conf` is kept unchanged as evidence; the corrected file is
`builder/diagnostics/kestrel-graphics-env.plasma68.conf` (same variables without `KWIN_COMPOSE`).

- `egltest.py` checks EGL and software OpenGL on the firmware-framebuffer DRM device (run as root); `qemu-egl.py` runs it in QEMU with a `ramfb`
  display under three environments. Result of 2026-11-12: software OpenGL works with `LIBGL_ALWAYS_SOFTWARE=1` and with no override; the Mesa
  `kms_swrast` loader override fails to initialise EGL.
- `build-gfx-variant-uki.py` replaces `/etc/kestrel-graphics-env` inside a UKI's initramfs (only `.initrd` changes). `gfx-env-A.txt` is the release
  setting; `gfx-env-C.txt` is a test variant without `LIBGL_ALWAYS_SOFTWARE`. `qemu-graphics.py` boots a variant with a framebuffer; the
  graphics supervisor's preflight fails in QEMU (it expects the laptop), so the session itself must be checked on the laptop.
- `make-menu-v10.py` builds the simple release menu (two boot entries and a firmware entry, no submenu) and the private stick menu. Both add `kestrel_graphics_unbounded=1`, which lifts the 180 s limit of the graphics session (temperature, display and session checks stay active), and `sysctl.kernel.apparmor_restrict_unprivileged_userns=0`, which lets the browser (Falkon, Chromium based) create its sandbox.

## Smart log and root overlay (added 2026-11-13)

`rootfs-overlay/` holds the files `build-root.sh` adds on top of the Phase 1 root: the Chromium default-application list, the `mpv.conf`
Wayland setting, the sysctl drop-in that lets browsers create their sandbox, the "Mount disk image" action, a system-wide
`powerdevilrc` (no idle dim, screen-off or suspend while the battery data is not live), and the **smart log**.

`/usr/local/sbin/fz-smartlog` (service `fz-smartlog.service`, enabled by the build) writes bounded, read-only facts about the whole
session to `Logs/boot-<boot id>/smart/` on the boot stick, or to `/run/fz-smartlog` when the stick cannot be written:

| File | Content |
|---|---|
| `summary.txt` | automatic findings in plain words: battery data live or not, DSP state, devices waiting for a supplier, temperatures, memory, crashes, failed units, what rose since the last snapshot |
| `history.tsv` | one line of key numbers per snapshot, for trends |
| `snap-NNN-up<s>.txt` | full snapshots at 45 s, 150 s, 400 s, then every 15 minutes, and one at shutdown (`snap-999`) |
| `event-<reason>-up<s>.txt` | extra snapshots when something goes wrong: `crash`, `failedunit`, `hot` (70 C), `lowmem`, `kernelbug`, `kernelburst` (at most 12 per boot, 2 minutes apart) |
| `kernel-warnings.log`, `journal-errors.log` | new warnings and errors every 30 s, without duplicates |
| `dmesg-*.log.gz`, `journal-*.log.gz` | the complete kernel and system logs, compressed |

On demand: `sudo systemctl kill -s USR1 fz-smartlog` or the "Save a diagnostic log now" launcher. At a terminal: `fz-smartlog once` prints
one snapshot and the summary, `fz-smartlog report` prints the newest summary. Limits: 24 MB per boot, 3 MB per growing log, time limits on
every command, no Wi-Fi names or keys. Kernel and journal text can contain file names; review a log before sharing it.
