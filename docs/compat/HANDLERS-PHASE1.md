# File handlers in the Phase 1 build (dev.2)

This page records the file-handling packages added in the Phase 1 build, product version `0.1.0-dev.2` (build id
`maverick-public-dev-20261111.3`). It is a package and format inventory, not a test report. It does not claim that any
handler was tested on the laptop; the verification procedure is at the end.

Extensions below are cross-checked against [`formats.tsv`](formats.tsv). Licences are as recorded in the Arch Linux
ARM sync databases. A package being present does not, by itself, prove a desktop file association, a working decoder
or a correct result.

## Packages

| Package | Licence | File types (examples from formats.tsv) | Interface | Main limit |
|---|---|---|---|---|
| `ark` | GPL-2.0-or-later | Archives: `.zip` `.zipx` `.7z` `.tar` `.gz` `.bz2` `.xz` `.zst` `.lz4` `.lzma` `.rar` `.r00` `.lha` `.lzh` `.cpio` `.ar` `.shar` | GUI | RAR is extract-only; creating RAR is not supported. |
| `7zip` | LGPL-2.1-or-later AND LicenseRef-UnRAR AND BSD-3-Clause AND BSD-2-Clause | `.7z` `.zip` `.zipx` `.tar` `.gz` `.bz2` `.xz` `.zst` `.lz4` `.lzma` `.rar` `.r00` | Command line | RAR extraction only; it cannot create RAR. |
| `unrar` | LicenseRef-UnRAR | `.rar` `.r00` | Command line | Decompression only; the licence forbids building a RAR compressor. |
| `unzip` | custom Info-ZIP | `.zip` | Command line | Extracts only; it does not create archives. |
| `zip` | LicenseRef-Info-ZIP | `.zip` | Command line | Creates and updates ZIP only; no RAR, 7z or ZIPX creation. |
| `cabextract` | GPL-2.0-or-later | `.cab` | Command line | Extraction only; it is not a cabinet creator. |
| `lhasa` | ISC | `.lha` `.lzh` | Command line | Extraction only; older LHA/LZH variants. |
| `unshield` | custom | `.cab` (InstallShield cabinets) | Command line | Extracts InstallShield cabinets only; not Microsoft CAB and no creation. |
| `squashfs-tools` | GPL-2.0-or-later | `.squashfs` `.sfs` | Command line | Creates and extracts images; no in-place editing, rebuild instead. |
| `erofs-utils` | Apache-2.0 GPL-2.0-or-later | `.erofs` | Command line | Creates and extracts images; mounting needs kernel EROFS support. |
| `dosfstools` | GPL-3.0-or-later | FAT12/16/32 filesystems and `.img` images | Command line | FAT only; no exFAT or NTFS. |
| `exfatprogs` | GPL-2.0-or-later | exFAT filesystems and `.img` images | Command line | exFAT only; no FAT or NTFS. |
| `ntfs-3g` | GPL-2.0-or-later | NTFS volumes and NTFS `.img` images | Command line / FUSE | Userspace FUSE driver; some NTFS features and performance differ from Windows. |
| `mtools` | GPL-3.0-or-later | FAT filesystems inside `.img` images | Command line | FAT only; not a general disk-image or partition editor. |
| `okular` | GPL-2.0-or-later LGPL-2.0-or-later | `.pdf` `.ps` `.eps` `.xps` `.oxps` `.djvu` `.djv` `.epub` `.mobi` `.azw` `.azw3` `.fb2` `.cbz` `.cbr` `.cb7` | GUI | DRM-protected e-books are not supported. |
| `gwenview` | GPL-2.0-or-later LGPL-2.0-or-later | `.png` `.jpg` `.jpeg` `.gif` `.bmp` `.ico` `.webp` `.tif` `.tiff` `.heic` `.heif` `.avif` `.jxl` `.jp2` `.j2k` | GUI | HEIC, AVIF and JPEG XL depend on optional codecs and plugins. |
| `kimageformats` | LGPL-2.0-only LGPL-3.0-only | Image plugins for KDE and Qt apps: `.webp` `.apng` `.heic` `.heif` `.avif` `.jxl` `.jp2` `.j2k` `.exr` `.hdr` `.tga` `.pcx` | Library/plugins (GUI) | Only used by applications that load KImageFormats plugins; codec coverage varies by build. |
| `libheif` | LGPL-3.0-or-later | `.heic` `.heif` `.avif` | Library and CLI tools | HEVC-based HEIC may need a patent-encumbered decoder. |
| `libjxl` | BSD-3-Clause | `.jxl` | Library and CLI tools | JPEG XL is newer; support depends on the application using the library. |
| `libavif` | LicenseRef-libavif | `.avif` | Library and CLI tools | AVIF support depends on the available AV1 codec and its features. |
| `haruna` | GPL-3.0-or-later | Video: `.mp4` `.m4v` `.mkv` `.avi` `.mov` `.webm` `.wmv` `.asf` `.flv` `.mpg` `.mpeg` `.ts` `.m2ts` `.3gp` `.ogv` `.vob` | GUI | Hardware decoding depends on the GPU driver; no DRM-protected video. |
| `mpv` | GPL-2.0-or-later AND LGPL-2.1-or-later | Video, audio and subtitles: `.mkv` `.mp4` `.webm` `.avi` `.mp3` `.flac` `.ogg` `.opus` `.wav` `.srt` `.ass` `.vtt` | GUI/CLI | Hardware decoding depends on the GPU driver; no DRM-protected media. |
| `elisa` | LGPL-2.0-or-later | Audio: `.mp3` `.flac` `.ogg` `.oga` `.opus` `.wav` `.aac` `.m4a` `.alac` `.wma` `.aiff` `.ape` | GUI | Audio only; codec coverage depends on the KDE multimedia backend. |
| `kate` | GPL-2.0-or-later LGPL-2.0-or-later | Text and code: `.txt` `.md` `.rst` `.log` `.csv` `.tsv` `.ini` `.cfg` `.conf` `.tex` `.bib` `.org` `.adoc` | GUI | Plain-text editor; not a word processor and no office layout fidelity. |
| `ffmpegthumbs` | GPL-2.0-or-later LGPL-2.0-or-later | Video thumbnails in Dolphin: `.mp4` `.mkv` `.avi` `.webm` `.mov` `.wmv` | Thumbnailer plugin (GUI) | Thumbnails only; no playback or full format coverage. |
| `kdegraphics-thumbnailers` | GPL-2.0-or-later LGPL-2.0-or-later | Thumbnails for document and graphics files, for example `.pdf` `.ps` `.raw` `.cbz` | Thumbnailer plugin (GUI) | Previews only; depends on the corresponding graphics libraries. |
| `falkon` | GPL-2.0-or-later | Web: `.html` `.htm` `.xhtml` `.mht` | GUI | A young browser on QtWebEngine (Chromium-based); not every site or extension works. |
| `libreoffice-fresh` | MPL-2.0 LGPL-3.0-or-later | Documents, sheets and presentations: `.docx` `.doc` `.odt` `.rtf` `.xlsx` `.xls` `.ods` `.pptx` `.ppt` `.odp` `.csv` | GUI (also CLI `soffice`) | Layout fidelity varies; fonts are substituted and macros may differ. |

## Notes

- **Archive creation and extraction are not the same.** `zip` creates ZIP archives; `7zip` creates 7z and ZIP and
  extracts RAR. `unrar`, `unzip`, `cabextract`, `lhasa` and `unshield` extract only. `ark` is the graphical front end,
  but RAR remains extract-only because of the UnRAR licence.
- **Filesystem tools are not archive handlers.** `squashfs-tools`, `erofs-utils`, `dosfstools`, `exfatprogs`,
  `ntfs-3g` and `mtools` work on filesystem images or devices. Mounting may need kernel support, and none of them is a
  partition editor.
- **Libraries are not applications.** `libheif`, `libjxl`, `libavif` and `kimageformats` provide decoding or plugins
  to other programs. HEIC is often HEVC-based and may need a patent-encumbered decoder; AVIF and JPEG XL support
  varies with the application and codec build.
- **Document fidelity is limited.** `libreoffice-fresh` opens office formats but layout, fonts and macros can differ.
  `kate` is a text editor only. `okular` handles PDF and several e-book formats, but DRM-protected books do not work.
- **Licence points to carry forward.** `unrar` and `7zip` include `LicenseRef-UnRAR`; the UnRAR licence forbids using
  the code to build a RAR compressor. `zip` and `unzip` carry Info-ZIP terms, and `libavif` uses
  `LicenseRef-libavif`. Repeat the rights review before redistribution.

## Not in this build

| Not included | Effect in this build |
|---|---|
| `vlc` | Not installed; `mpv` and `haruna` are the video players. |
| `calibre` | Not installed; `okular` opens some e-book formats, but DRM-protected books do not work. |
| Firefox | Removed for trademark reasons. The build includes the Falkon browser (GPL-2.0-or-later) on QtWebEngine, which Okular and Gwenview pull in as a dependency. |
| Wine | No Windows `.exe` or `.msi` support in this build. |
| Waydroid | No Android `.apk` support in this build. |
| QEMU | No guest operating system or VM image support in this build. |

These are later phases of the compatibility plan in
[UNIVERSAL-COMPATIBILITY.md](../releases/UNIVERSAL-COMPATIBILITY.md), not features promised for this build.

## How to verify a handler works

1. Confirm the package is installed; this proves package presence only:

   ```
   pacman -Q ark 7zip unrar unzip zip cabextract lhasa unshield squashfs-tools erofs-utils dosfstools \
     exfatprogs ntfs-3g mtools okular gwenview kimageformats libheif libjxl libavif haruna mpv elisa kate \
     ffmpegthumbs kdegraphics-thumbnailers libreoffice-fresh falkon
   ```

2. Use a sample file of each type you intend to claim. Prefer samples you may legally keep; if one cannot be
   redistributed, describe it in the record instead of adding it to the repository.
3. Open the sample the way a user would: Dolphin for a GUI handler, the package command for a command-line handler,
   or the GUI application that uses a library (`okular`, `gwenview`, `haruna`, `mpv`, `elisa`, `libreoffice-fresh`).
4. Check the content, not just that a window opened: list or extract an archive, render a page or image, play the
   media, load the document and inspect the layout.
5. Record the package, version, sample, result (works, partial or fails), the exact limitation, and whether the test
   was on the laptop or in an emulator. Put the results in the release notes for the build.
6. Do not describe a format as supported until a real sample has been tested on the laptop and its limits are written
   in the release notes. Package presence and an emulator result are not hardware proof.
