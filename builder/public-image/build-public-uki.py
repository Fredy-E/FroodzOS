#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build firmware-free public UKIs from the two pinned private UKIs (run in the CachyOSBuilder distro, no media writes).

Only the .initrd section changes: the unified kernel image keeps its kernel, command line, os-release, hwids and device
tree. In the initramfs this removes (a) the vendor firmware under usr/lib/firmware/updates (staged from a Windows
installation) and (b) firmware files that belong to the Arch Linux ARM firmware packages the public root no longer ships.
Outputs: froodzos-maverick-tp.efi (touchpad device tree) and froodzos-maverick-base.efi (original device tree).
"""
import hashlib, importlib.util, json, lzma, os, re, shutil, subprocess, sys, fcntl
from pathlib import Path

D = Path('/mnt/d/CachyOS-ARM64'); C = D / 'maverick-dev-candidate-20261110'
spec = importlib.util.spec_from_file_location('dt27uki', D / 'development/dt27-wifi/testing/boot-failure/build-dt27-wifi-uki.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BASE = C / 'input/kestrel-live-dt27-wifi.efi'; BASE_SHA = '4fb18edfb4ae2f2727658b5c94f43a3ccee78dd33d8e952a1b11a656ddd90867'
TP1 = C / 'touchpad-test/kestrel-maverick-tp1.efi'; TP1_SHA = 'fb8ab6893d844a388f58238b8fc7088d2dfd042e7102a1ec635031ede64f0e42'
DB = Path('/home/builder/pkgaudit/root/var/lib/pacman/local')   # extracted from the pinned candidate root by pkg-audit
OUT = Path('/mnt/d/FroodzOS-build/uki'); WORK = Path('/mnt/d/FroodzOS-build/uki-work')
REMOVE = ['amd', 'amdgpu', 'broadcom', 'cirrus', 'intel', 'mediatek', 'nvidia', 'other', 'radeon', 'ti']
STUB, LOCK = m.STUB, m.LOCK
assert m.sha(BASE) == BASE_SHA and m.sha(TP1) == TP1_SHA and m.sha(STUB / 'stubble.efi') == m.STUB_SHA


def read_files(entry):
    parts = (DB / entry / 'files').read_text(encoding='utf-8').split('%FILES%')
    return parts[1] if len(parts) > 1 else ''


def pkg_files(pkgname):
    for e in os.listdir(DB):
        mm = re.match(r'^(.*)-[^-]+-[^-]+$', e)
        if mm and mm.group(1) == pkgname:
            txt = read_files(e)
            return {x.strip().rstrip('/') for x in txt.splitlines() if x.strip()}
    raise SystemExit('no db entry ' + pkgname)


removed = set().union(*[pkg_files('linux-firmware-' + p) for p in REMOVE])
kept = set()
for e in os.listdir(DB):
    mm = re.match(r'^(.*)-[^-]+-[^-]+$', e)
    if mm and not (mm.group(1).startswith('linux-firmware-') and mm.group(1)[len('linux-firmware-'):] in REMOVE):
        txt = read_files(e)
        kept |= {x.strip().rstrip('/') for x in txt.splitlines() if x.strip()}
drop = removed - kept


def split_cpio(blob):
    """Yield (name, start, end, nlink, mode) for each entry of a newc archive starting at 0; return end offset incl. trailer."""
    pos, out = 0, []
    while blob[pos:pos + 6] == b'070701':
        f = [int(blob[pos + 6 + 8 * k:pos + 14 + 8 * k], 16) for k in range(13)]
        mode, nlink, fs, ns = f[1], f[4], f[6], f[11]
        name = blob[pos + 110:pos + 110 + ns - 1].decode('utf-8', 'replace')
        p2 = (pos + 110 + ns + 3) & ~3
        end = (p2 + fs + 3) & ~3
        out.append((name, pos, end, nlink, mode, fs))
        pos = end
        if name == 'TRAILER!!!':
            break
    return out, pos


def filter_main(raw):
    ents, end = split_cpio(raw)
    keep, dropped, kb = [], [], 0
    for name, s, e, nlink, mode, fs in ents:
        n = name.rstrip('/')
        if n == 'TRAILER!!!':
            keep.append(raw[s:e]); continue
        bad = n == 'usr/lib/firmware/updates' or n.startswith('usr/lib/firmware/updates/') or n in drop
        if bad:
            assert not (nlink > 1 and fs > 0), 'dropped entry carries hard-link data: ' + n
            dropped.append(n); continue
        keep.append(raw[s:e])
    return b''.join(keep), dropped


def build():
    for p in (OUT, WORK):
        shutil.rmtree(p, ignore_errors=True); p.mkdir(parents=True)
    old, oldmeta, oldhdr = m.sections(BASE.read_bytes())
    oldtp, _, _ = m.sections(TP1.read_bytes())
    blob = old['.initrd']
    first_ents, first_end = split_cpio(blob)
    pad = first_end
    while blob[pad:pad + 1] == b'\0':
        pad += 1
    head, main_xz = blob[:pad], blob[pad:]
    assert main_xz[:6] == b'\xfd7zXZ\x00', 'main initramfs is not xz'
    main = lzma.decompress(main_xz)
    new_main, dropped = filter_main(main)
    new_xz = lzma.compress(new_main, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32, preset=9 | lzma.PRESET_EXTREME)
    new_initrd = head + new_xz
    # sanity: re-read the new archive
    chk, _ = split_cpio(lzma.decompress(new_xz))
    names = [c[0].rstrip('/') for c in chk]
    assert not any(n.startswith('usr/lib/firmware/updates') for n in names)
    assert not any(n in drop for n in names if n != 'TRAILER!!!')
    (WORK / 'initrd.new').write_bytes(new_initrd)
    for name in ('.linux', '.osrel', '.cmdline', '.hwids', '.sbat'):
        m.exclusive(WORK / (name[1:] + '.input'), old[name])
    m.exclusive(WORK / 'build.conf', b'[UKI]\n')
    results = {}
    with LOCK.open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for label, dtbsrc in (('tp', oldtp['.dtbauto']), ('base', old['.dtbauto'])):
            dtb = WORK / (label + '.dtb'); dtb.write_bytes(dtbsrc)
            target = OUT / ('froodzos-maverick-%s.efi' % label)
            cmd = ['python3', str(STUB / 'stubblify'), 'build', '--config=' + str(WORK / 'build.conf'), '--efi-arch=aa64',
                   '--stub=' + str(STUB / 'stubble.efi'), '--linux=' + str(WORK / 'linux.input'), '--initrd=' + str(WORK / 'initrd.new'),
                   '--devicetree-auto=' + str(dtb), '--os-release=@' + str(WORK / 'osrel.input'), '--cmdline=@' + str(WORK / 'cmdline.input'),
                   '--hwids=', '--section=.hwids:@' + str(WORK / 'hwids.input'),
                   '--uname=' + old['.uname'].rstrip(b'\0\n').decode('ascii'), '--no-sign-kernel', '--no-measure', '--no-policy-digest',
                   '--output=' + str(target)]
            env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/builder', 'LC_ALL': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(WORK)}
            r = subprocess.run(cmd, cwd=WORK, env=env, capture_output=True, text=True, timeout=600)
            assert r.returncode == 0, 'stubblify failed: ' + r.stderr[-400:]
            new, newmeta, newhdr = m.sections(target.read_bytes())
            same = {n: (new.get(n) == old[n]) for n in old if n not in ('.initrd', '.dtbauto')}
            results[label] = {'file': target.name, 'bytes': target.stat().st_size, 'sha256': m.sha(target),
                              'sections_equal_except_initrd_and_dtb': all(same.values()),
                              'dtb_matches_source': new['.dtbauto'] == dtbsrc, 'initrd_is_new': new['.initrd'].rstrip(b'\0') == new_initrd.rstrip(b'\0'),
                              'header_retained': oldhdr == newhdr}
    report = {'initrd_old_bytes': len(blob), 'initrd_new_bytes': len(new_initrd), 'entries_dropped': len(dropped),
              'dropped_updates': sum(1 for n in dropped if n.startswith('usr/lib/firmware/updates')),
              'dropped_sample': dropped[:6], 'ukis': results, 'base_uki_sha256': BASE_SHA, 'tp_source_sha256': TP1_SHA}
    (OUT / 'build-public-uki.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


build()
