#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Single source of truth for the FroodzOS universal-compatibility catalogue (docs/compat/formats.tsv).

Every row is a file extension the project aims to open or run. The catalogue is a PLAN: nothing here is a promise of support.
Columns:
  extension        without the dot, lower case
  category         archive | disk-image | document | ebook | image | audio | video | font | 3d-cad | data | mail | security |
                   package | executable | mobile-app | macos | emulation | script | web | other-os
  ceiling          the best realistic level: native | compat (compatibility layer) | vm (virtual machine) | limited | notfeasible
  phase            1-5 (see docs/releases/UNIVERSAL-COMPATIBILITY.md) or never
  candidate_handlers  software that could handle it on ARM64 Linux (candidates, not verified packages)
  in_image_today   partial = a package that can read or run it is in the published image (often only a command-line tool or library); no = nothing yet
  note             constraint, licence or legal remark

Usage:  python tools/compat-catalogue.py            # write docs/compat/formats.tsv and docs/compat/SUMMARY.md
        python tools/compat-catalogue.py --check    # fail if the committed files differ from this script's output
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_TSV = ROOT / 'docs' / 'compat' / 'formats.tsv'
OUT_MD = ROOT / 'docs' / 'compat' / 'SUMMARY.md'
BUILD = 'maverick-public-dev-20261111.3'
# Packages of the published image (pkglist.tsv of the build above) that can act as handlers. Names used in GROUPS that differ from
# the package name are listed too: libreoffice = libreoffice-fresh, qtwebengine = qt6-webengine.
IN_IMAGE = {'libarchive', 'udisks2', 'ffmpeg', 'poppler', 'libraw', 'dolphin', 'kio-extras', 'kio-fuse', 'sqlite', 'openssl',
            'gnupg', 'fontconfig', 'python', 'tar', 'gzip', 'bzip2', 'xz', 'zstd', 'lz4', 'file', 'e2fsprogs', 'parted',
            'ark', '7zip', 'unrar', 'unzip', 'zip', 'cabextract', 'lhasa', 'unshield', 'squashfs-tools', 'erofs-utils',
            'dosfstools', 'exfatprogs', 'ntfs-3g', 'mtools', 'okular', 'gwenview', 'kimageformats', 'libheif', 'libjxl',
            'libavif', 'haruna', 'mpv', 'elisa', 'kate', 'ffmpegthumbs', 'kdegraphics-thumbnailers', 'libreoffice',
            'falkon', 'qtwebengine'}

CEILINGS = ('native', 'compat', 'vm', 'limited', 'notfeasible')
PHASES = ('1', '2', '3', '4', '5', 'never')

# (category, ceiling, phase, handlers, extensions, note)
GROUPS = [
    ('archive', 'native', '1', ['libarchive', '7zip', 'ark'],
     'zip zipx 7z tar gz tgz bz2 tbz2 xz txz zst tzst lz4 lzma z lz arj lzh lha cpio ar shar', ''),
    ('archive', 'native', '1', ['unrar', 'libarchive', 'ark'], 'rar r00', 'unrar has a non-free licence: check redistribution before bundling'),
    ('archive', 'native', '1', ['unshield', 'cabextract'], 'cab', 'InstallShield and Microsoft cabinets'),
    ('archive', 'native', '1', ['libarchive', 'squashfs-tools', 'erofs-utils'], 'squashfs sfs erofs', ''),
    ('disk-image', 'native', '1', ['udisks2', 'cdemu', 'libarchive'], 'iso udf bin cue nrg mdf mds ccd', 'mounting and reading; booting is the vm row'),
    ('disk-image', 'native', '1', ['udisks2', 'losetup', 'e2fsprogs', 'dosfstools'], 'img', ''),
    ('disk-image', 'native', '1', ['wimlib'], 'wim esd swm', 'Windows imaging format'),
    ('disk-image', 'native', '1', ['qemu-img', 'qemu-nbd', 'libguestfs'], 'vhd vhdx vmdk qcow2 qcow vdi', 'mount or convert; running the guest is the vm row'),
    ('disk-image', 'limited', '1', ['dmg2img', 'hfsprogs', 'apfs-fuse', '7zip'], 'dmg sparseimage sparsebundle',
     'compressed HFS+ images work; APFS and encrypted images are limited'),
    ('document', 'native', '1', ['libreoffice', 'onlyoffice'], 'docx doc docm dotx dot rtf odt ott fodt wps wpd', 'layout fidelity varies, fonts are substituted'),
    ('document', 'native', '1', ['libreoffice', 'onlyoffice'], 'xlsx xls xlsm xlsb xltx ods ots fods numbers', 'macros and some functions differ'),
    ('document', 'native', '1', ['libreoffice', 'onlyoffice'], 'pptx ppt pptm potx ppsx odp otp fodp key', 'animations and embedded fonts can differ; .key is Apple Keynote here (also used for private keys)'),
    ('document', 'native', '1', ['libreoffice', 'inkscape'], 'odg otg vsd vsdx pub pages', 'Visio, Publisher, Pages and CorelDRAW import is best-effort'),
    ('document', 'native', '1', ['okular', 'poppler', 'mupdf'], 'pdf ps eps xps oxps djvu djv', ''),
    ('document', 'native', '1', ['okular', 'calibre', 'foliate'], 'epub mobi azw azw3 fb2 cbz cbr cb7 lit', 'DRM-protected books are not supported'),
    ('document', 'native', '1', ['kate', 'nano', 'python'], 'txt md rst log csv tsv ini cfg conf tex bib org adoc', ''),
    ('image', 'native', '1', ['gwenview', 'kimageformats', 'imagemagick'], 'png jpg jpeg jpe gif bmp ico cur ppm pgm pbm pnm tga pcx xbm xpm webp apng', ''),
    ('image', 'native', '1', ['gwenview', 'libheif', 'libjxl', 'libavif'], 'heic heif avif jxl jp2 j2k', 'HEVC-based HEIC may need a patent-encumbered decoder'),
    ('image', 'native', '1', ['gwenview', 'libtiff', 'imagemagick'], 'tif tiff dds exr hdr', ''),
    ('image', 'native', '1', ['libraw', 'darktable', 'rawtherapee'], 'raw cr2 cr3 nef nrw arw sr2 dng orf rw2 raf pef srw', 'camera RAW; libraw is already in the image'),
    ('image', 'native', '1', ['gimp', 'krita'], 'psd xcf kra ora', 'Photoshop import is best-effort'),
    ('image', 'native', '1', ['inkscape', 'librsvg'], 'svg svgz ai cdr wmf emf', 'Illustrator and Windows metafile import is best-effort'),
    ('audio', 'native', '1', ['ffmpeg', 'vlc', 'mpv', 'elisa'], 'mp3 flac ogg oga opus wav aac m4a alac wma aiff aif ape wv mka mp2 ac3 dts amr au', 'ffmpeg is already in the image'),
    ('audio', 'native', '1', ['timidity', 'fluidsynth'], 'mid midi kar', ''),
    ('audio', 'native', '1', ['libopenmpt', 'mpv'], 'mod xm it s3m', 'tracker music'),
    ('video', 'native', '1', ['ffmpeg', 'vlc', 'mpv', 'haruna'], 'mp4 m4v mkv avi mov webm wmv asf flv f4v mpg mpeg ts m2ts mts 3gp 3g2 ogv vob rm rmvb divx', 'hardware decoding depends on the GPU driver'),
    ('video', 'native', '1', ['ffmpeg', 'mpv'], 'srt ass ssa vtt sub sup', 'subtitles'),
    ('font', 'native', '1', ['fontconfig', 'fontforge'], 'ttf otf ttc woff woff2 pfb pfm bdf pcf', 'fontconfig is already in the image'),
    ('3d-cad', 'native', '2', ['blender', 'meshlab', 'openscad'], 'stl obj fbx gltf glb 3ds dae ply 3mf blend usd usdz', 'USDZ and FBX import are best-effort'),
    ('3d-cad', 'native', '2', ['freecad', 'librecad', 'qcad'], 'step stp iges igs dxf dwg', 'DWG is proprietary: import is best-effort'),
    ('3d-cad', 'native', '2', ['cura', 'prusa-slicer'], 'gcode', ''),
    ('data', 'native', '1', ['sqlite', 'sqlitebrowser', 'duckdb'], 'sqlite sqlite3 db db3 parquet arrow feather', 'sqlite is already in the image'),
    ('data', 'native', '1', ['python', 'jq'], 'json jsonl yaml yml toml xml ipynb har geojson', 'python is already in the image'),
    ('mail', 'native', '2', ['thunderbird', 'kontact', 'libpst'], 'eml mbox msg pst ost emlx', 'Outlook formats are best-effort'),
    ('mail', 'native', '2', ['kontact', 'khard'], 'ics vcf ical', ''),
    ('security', 'native', '1', ['openssl', 'gnupg', 'keepassxc'], 'pem crt cer der p12 pfx gpg asc sig kdbx', 'openssl and gnupg are already in the image'),
    ('package', 'native', '2', ['dpkg', 'rpm-tools', 'libarchive'], 'deb rpm', 'extraction and inspection; installing foreign packages is not the aim'),
    ('package', 'native', '2', ['pacman', 'libarchive'], 'pkg.tar.zst pkg.tar.xz', 'native package format of the base system'),
    ('package', 'native', '2', ['appimage-runtime', 'flatpak', 'snapd'], 'appimage flatpak snap', 'must be an ARM64 build'),
    ('package', 'native', '2', ['python-pip', 'libarchive'], 'whl egg gem crate', ''),
    ('executable', 'native', '1', ['bash', 'python', 'nodejs', 'perl', 'ruby'], 'sh bash py js mjs pl rb lua php', ''),
    ('executable', 'native', '1', ['jre-openjdk'], 'jar class war', 'Java runs natively on ARM64'),
    ('executable', 'native', '2', ['dotnet-runtime', 'mono'], 'nupkg', '.NET assemblies: see exe/dll for Windows ones'),
    ('executable', 'native', '2', ['wasmtime', 'wasmer'], 'wasm wat', ''),
    ('executable', 'native', '1', ['binutils'], 'elf so ko', 'Linux ARM64 binaries run directly; Linux x86-64 programs need FEX-Emu, Box64 or qemu-user through binfmt_misc'),
    ('executable', 'compat', '2', ['wine', 'fex-emu', 'box64', 'dxvk', 'vkd3d-proton'], 'exe com scr', 'Windows x86-64 programs (Windows ARM64 programs run through Wine directly); no kernel drivers or anti-cheat; GPU translation on Adreno is experimental'),
    ('executable', 'compat', '2', ['wine', 'msitools'], 'msi msix appx appxbundle msp', 'Windows installers; MSIX needs extra work'),
    ('executable', 'compat', '2', ['wine'], 'dll ocx sys lnk cpl', 'libraries and shortcuts of Windows programs; .sys drivers cannot run'),
    ('executable', 'compat', '2', ['wine', 'powershell'], 'bat cmd ps1 vbs wsf reg', 'Windows scripts: PowerShell exists for ARM64 Linux; VBScript is limited'),
    ('mobile-app', 'native', '3', ['waydroid'], 'apk xapk apks apkm', 'Android apps run in a container; ARM64 apps need no CPU translation; no Google Play, unofficial on Snapdragon X'),
    ('mobile-app', 'limited', '3', ['waydroid', 'bundletool'], 'aab', 'Android App Bundles must be converted to APKs first'),
    ('mobile-app', 'notfeasible', 'never', ['touchhle'], 'ipa', 'iOS apps: FairPlay DRM, no UIKit; only a few old 32-bit games run in touchHLE'),
    ('macos', 'limited', '5', ['darling', 'xar', 'pbzx', '7zip'], 'app pkg mpkg', 'command-line tools only through Darling; GUI apps and Apple licence terms are blockers'),
    ('macos', 'notfeasible', 'never', [], 'dylib bundle framework', 'macOS libraries: not runnable outside macOS'),
    ('emulation', 'compat', '5', ['retroarch', 'mame', 'dolphin-emu'], 'nes sfc smc gb gbc gba nds n64 z64 gen smd sms gg pce a26 chd', 'emulators exist; the user supplies legally owned ROMs'),
    ('emulation', 'compat', '5', ['dosbox-staging', 'scummvm'], 'd64 adf', 'DOS and legacy games'),
    ('other-os', 'vm', '4', ['qemu-system-aarch64', 'libvirt', 'virt-manager'], 'ova ovf vbox', 'a whole guest operating system (other CPU architectures too, by slow emulation): needs KVM (EL2 boot path) to be fast'),
    ('web', 'native', '1', ['falkon', 'qtwebengine'], 'html htm xhtml mht', 'Falkon (QtWebEngine) is in the image since 0.1.0-dev.2; Firefox was removed for trademark reasons'),
    ('web', 'native', '2', ['qbittorrent', 'transmission'], 'torrent', ''),
    ('web', 'native', '1', ['xdg-utils'], 'url desktop webloc', ''),
]


def rows():
    seen = {}
    for cat, ceiling, phase, handlers, exts, note in GROUPS:
        assert ceiling in CEILINGS, ceiling
        assert phase in PHASES, phase
        for ext in exts.split():
            assert ext not in seen, 'duplicate extension %s' % ext
            seen[ext] = None
            today = 'partial' if any(h in IN_IMAGE for h in handlers) else 'no'
            yield (ext, cat, ceiling, phase, ' '.join(handlers) or '-', today, note or '-')


def render():
    data = list(rows())
    tsv = 'extension\tcategory\tceiling\tphase\tcandidate_handlers\tin_image_today\tnote\n' + '\n'.join('\t'.join(r) for r in data) + '\n'
    by_cat = collections.OrderedDict()
    for r in data:
        by_cat.setdefault(r[1], []).append(r)
    ceil = collections.Counter(r[2] for r in data)
    today = collections.Counter(r[5] for r in data)
    md = ['# Compatibility catalogue — summary', '',
          'Generated by `tools/compat-catalogue.py` for build `%s`; do not edit by hand. Full list: [formats.tsv](formats.tsv).' % BUILD, '',
          '**%d extensions** in %d categories. This is a plan: it states what could handle each extension, not what works.' % (len(data), len(by_cat)), '',
          '| Ceiling | Extensions |', '|---|---|']
    md += ['| %s | %d |' % (c, ceil[c]) for c in CEILINGS]
    md += ['', 'In the published image today: **%d** extensions have at least one package that can read or run them, often only a command-line tool or a library and not a usable application; **%d** have none.' % (today['partial'], today['no']), '',
           '| Category | Count | Extensions |', '|---|---|---|']
    for cat, rs in by_cat.items():
        md.append('| %s | %d | %s |' % (cat, len(rs), ' '.join('`.%s`' % r[0] for r in rs)))
    md += ['', 'Meaning of the ceilings: **native** = ordinary Linux code; **compat** = a compatibility layer or emulator inside the desktop; '
           '**vm** = a whole guest system; **limited** = partial or best-effort; **notfeasible** = blocked by technology or law.', '']
    return tsv, '\n'.join(md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    tsv, md = render()
    if args.check:
        ok = OUT_TSV.read_text(encoding='utf-8') == tsv and OUT_MD.read_text(encoding='utf-8') == md
        print('catalogue is up to date' if ok else 'catalogue differs: run tools/compat-catalogue.py')
        return 0 if ok else 1
    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_TSV.write_text(tsv, encoding='utf-8', newline='\n')
    OUT_MD.write_text(md, encoding='utf-8', newline='\n')
    print('wrote', OUT_TSV.relative_to(ROOT), OUT_MD.relative_to(ROOT), len(tsv.splitlines()) - 1, 'extensions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
