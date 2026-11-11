# Main goal: open and run everything, as natively as possible

**FroodzOS aims to open every kind of file and run the apps and operating systems of other platforms directly on the user's own
machine, as natively as technically possible — starting with a few formats and growing without a fixed limit.** The targets named by
the owner include archives (`.zip` `.rar`), disk images (`.iso` `.dmg`), office documents (`.docx` `.xlsx`), Windows programs
(`.exe`), phone apps (`.apk`), and other operating systems, "literally everything".

**This is the project's direction, not a current feature.** Today the published development image has a Plasma desktop with Dolphin
(file manager) and Konsole, the command-line compression tools (`gzip`, `bzip2`, `xz`, `zstd`, `lz4`, `tar`), `bsdtar` from `libarchive`
(reads zip, 7z, ISO and some RAR), `udisks2` for mounting images, and libraries such as `ffmpeg`, `poppler`, `libraw` and `sqlite`.
It has **no** graphical archive tool, document or PDF viewer, image viewer, media player, office suite, browser, Wine, Waydroid or QEMU.
Nothing below is promised for a date, and each row says what is technically possible.

## What "native" means here

| Level | Meaning | Examples |
|---|---|---|
| Native | Runs as ordinary Linux code on the CPU, no translation. | Archives, ISO mounting, LibreOffice/OnlyOffice, ARM64 Android apps inside a container. |
| Compatibility layer | Windows/macOS API translated to Linux; x86 code translated to ARM64. Runs inside the same desktop, no VM. | Wine with FEX-Emu or Box64 for `.exe`. |
| Virtual machine | A whole guest OS on a virtual CPU. Needs the CPU's virtualisation (KVM) or is slow. | QEMU guests. |
| Not feasible | Blocked by technology or by law. | iOS apps (DRM and EULA); macOS GUI apps outside Apple hardware. |

Where physics (a different CPU instruction set) or law (a licence that forbids it) stands in the way, FroodzOS will say so instead of
claiming support. "Native" is therefore the aim for each format, not a guarantee for every one.

## Feasibility map (research of 2026-11-11, sources in the notes below)

| Category | Best approach | Ceiling | State on this project |
|---|---|---|---|
| Archives, disk images (`.zip` `.rar` `.7z` `.tar` `.iso` `.img` `.dmg`) | 7zip, unrar (non-free licence), `libarchive`/Ark, `udisks2` + loop, `dmg2img`/`hfsprogs` | Native | Partly: `libarchive`, `udisks2`; the rest not yet installed |
| Office documents (`.docx` `.xlsx` `.pptx` `.odt`) | LibreOffice, OnlyOffice Desktop Editors (ARM64 builds exist) | Native (layout fidelity varies) | Not yet installed |
| Windows ARM64 programs | Wine on ARM64 | Near-native, small app library | Not yet |
| Windows x86-64 programs (`.exe` `.msi`) | Wine + FEX-Emu or Box64, DXVK/VKD3D, Proton ARM64 | Compatibility layer (CPU cost, no kernel drivers or anti-cheat) | Not yet; GPU translation on Adreno is experimental |
| Android apps (`.apk`) | Waydroid (ARM64 apps need no CPU translation), kernel binder support | Native container; unofficial on this hardware | Not yet; needs kernel options and testing |
| Other operating systems | QEMU/KVM guests | Virtual machine; KVM on this laptop class needs an EL2-capable boot path | Not yet |
| macOS (`.dmg` apps) | Darling for command-line tools only | Mostly not feasible (Apple EULA, no arm64 app path) | Out of scope for GUI apps |
| iOS (`.ipa`) | none practical (touchHLE runs a few old 32-bit games only) | Not feasible | Out of scope |
| "Open anything" integration | `binfmt_misc`, file associations (`xdg-mime`), one launcher that picks the right handler | Native glue | Design only |

## The catalogue (grows without limit)

[`docs/compat/formats.tsv`](../compat/formats.tsv) lists every extension the project aims to handle — **372 in 18 categories** at the
time of writing (summary: [SUMMARY.md](../compat/SUMMARY.md)): archives, disk images, documents, e-books, images, audio, video, fonts,
3D/CAD, data, mail, security, packages, executables, mobile apps, macOS, emulation, other-OS images, web and scripts. For each
extension it records the realistic ceiling, the phase, candidate handlers, whether the published image can do anything with it
today, and the constraint (licence, DRM, fidelity). The file is generated from `tools/compat-catalogue.py`; CI fails if the two
differ. **To add an extension**, add it to a group in that script (or a new group), run the script, and send the pull request.

## "Open Anything" design

1. **Identify** by content (libmagic) and extension, not by name alone; unknown types are reported with the sniffed type.
2. **Choose** the handler with the highest native level that is installed; if none is, offer the best candidate from the catalogue and say what
   it needs (package, licence, size) before installing.
3. **Run** natively, else through a compatibility layer, else in a virtual machine — and show which one, with the cost (speed, features).
4. **Isolate**: foreign executables run unprivileged in a sandbox (separate prefix or container), never as root, and never from a
   downloads folder without an explicit user action.
5. **Record**: the catalogue row, the handler used and the result feed the "what works today" table, so claims stay honest.

## Quality gates for each new format

A format moves from *planned* to *supported* only when: a handler is in the image (rights review repeated for new packages), it has been
tested on real sample files on the laptop, its limits are written in the release notes, and the catalogue row says so.

## Phases

The phases are mapped onto the selected codenames in [ROADMAP.md](ROADMAP.md) (Phase 1 aimed at 0.2 Chaffee, Phase 2 from 0.3 Hellcat, Phase 3 by 0.5 Raptor, Phase 4 at 1.3 Corsair).

1. **Files** — add archive, disk-image and office handlers to the image, file associations and an "open with the right tool" launcher;
   test on real files. Licences: `unrar` has a custom licence (check redistribution before bundling).
2. **Windows programs** — Wine for ARM64 and x86-64 (FEX-Emu/Box64), Vulkan translation on the Adreno GPU, per-app test list.
3. **Android apps** — kernel binder/PSI/FUSE options, Waydroid with an ARM64 image, test apps; document the licensing limits (no Google Play).
4. **Virtual machines** — find a boot path that leaves Linux at EL2 for KVM on this laptop; QEMU guests.
5. **Widen** — more formats and platforms as they become feasible; macOS command-line tools via Darling.
6. **Never promised** — iOS apps and macOS GUI apps, unless the technology and the law change.

Each phase needs: the kernel options in the board configuration, the packages in the image (with the rights review in
[RIGHTS-REVIEW.md](RIGHTS-REVIEW.md) repeated for anything new), tests on hardware, and honest limitations in the release notes.

## Notes and sources

Research by an automated survey on 2026-11-11 (not legal advice; verify before relying): FEX-Emu ARM64EC notes
(wiki.fex-emu.com), OnlyOffice ARM64 announcement (onlyoffice.com, January 2026), Waydroid project and its open issues on
Snapdragon X (waydro.id, github.com/waydroid/waydroid), Darling Q4 2026 report (blog.darlinghq.org), touchHLE FAQ (touchhle.org),
Snapdragon X Linux notes on EL2/KVM (community repositories). Items marked "unofficial" or "experimental" there are unproven on this laptop.
