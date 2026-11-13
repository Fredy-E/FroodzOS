#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Rebuild a UKI with a different /etc/kestrel-graphics-env in its initramfs (run in the CachyOSBuilder distro, no media writes).

    build-gfx-variant-uki.py <source.efi> <env-file | -> <out.efi> [<cpio-entry>=<file> ...]

`-` keeps the environment file unchanged (and prints it). Only the .initrd section changes; everything else is copied as is.
The cpio entry is rebuilt (header size field, padding) so no other entry moves.
"""
import importlib.util, fcntl, lzma, subprocess, sys
from pathlib import Path

D = Path('/mnt/d/CachyOS-ARM64')
spec = importlib.util.spec_from_file_location('dt27uki', D / 'development/dt27-wifi/testing/boot-failure/build-dt27-wifi-uki.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
src, envfile, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
STUB, LOCK = m.STUB, m.LOCK
NAME = 'etc/kestrel-graphics-env'


def entries(blob):
    pos, res = 0, []
    while blob[pos:pos + 6] == b'070701':
        f = [int(blob[pos + 6 + 8 * k:pos + 14 + 8 * k], 16) for k in range(13)]
        fs, ns = f[6], f[11]
        name = blob[pos + 110:pos + 110 + ns - 1].decode('utf-8', 'replace').rstrip('/')
        data0 = (pos + 110 + ns + 3) & ~3
        end = (data0 + fs + 3) & ~3
        res.append((name, pos, data0, fs, end, f))
        pos = end
        if name == 'TRAILER!!!':
            break
    return res, pos


def rebuild(blob, ent, newdata):
    name, pos, data0, fs, end, f = ent
    f = list(f); f[6] = len(newdata); f[12] = 0
    nb = (name + '\0').encode()
    f[11] = len(nb)
    hdr = b'070701' + b''.join(('%08X' % v).encode() for v in f)
    body = hdr + nb
    body += b'\0' * ((4 - len(body) % 4) % 4)
    body += newdata
    body += b'\0' * ((4 - len(body) % 4) % 4)
    return blob[:pos] + body + blob[end:]


secs, meta, hdr = m.sections(src.read_bytes())
blob = secs['.initrd']
ents, first_end = entries(blob)
pad = first_end
while blob[pad:pad + 1] == b'\0':
    pad += 1
head, main_xz = blob[:pad], blob[pad:]
assert main_xz[:6] == b'\xfd7zXZ\x00'
main = lzma.decompress(main_xz)
ents, _ = entries(main)
hit = [e for e in ents if e[0] == NAME]
assert len(hit) == 1, 'env entry not found'
old = main[hit[0][2]:hit[0][2] + hit[0][3]]
print('--- current %s (%d bytes):\n%s' % (NAME, len(old), old.decode('utf-8', 'replace')))
import hashlib
repl = [] if envfile == '-' else [(NAME, Path(envfile))]
DTB_OVERRIDE = None
for extra in sys.argv[4:]:        # optional <cpio-entry>=<file>, any entry of the initramfs (e.g. etc/kestrel-graphics-supervisor); '@dtb=<file>' replaces the .dtbauto section
    en, _, fn = extra.partition('=')
    if en == '@dtb':
        DTB_OVERRIDE = Path(fn)
        continue
    repl.append((en, Path(fn)))
for en, fp in repl:
    cur, _ = entries(main)
    h = [e for e in cur if e[0] == en]
    assert len(h) == 1, 'entry not found: ' + en
    old_e = main[h[0][2]:h[0][2] + h[0][3]]
    new = fp.read_bytes()
    main = rebuild(main, h[0], new)
    ents2, _ = entries(main)
    chk = [e for e in ents2 if e[0] == en][0]
    assert main[chk[2]:chk[2] + chk[3]] == new and len(ents2) == len(cur)
    print('--- %s: sha256 %s (%d B) -> %s (%d B)' % (en, hashlib.sha256(old_e).hexdigest()[:16], len(old_e), hashlib.sha256(new).hexdigest()[:16], len(new)))
new_xz = lzma.compress(main, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32, preset=9 | lzma.PRESET_EXTREME)
work = Path('/mnt/c/FroodzOS-build/uki-gfx-work'); work.mkdir(parents=True, exist_ok=True)
(work / 'initrd.new').write_bytes(head + new_xz)
for name in ('.linux', '.osrel', '.cmdline', '.hwids', '.sbat'):
    (work / (name[1:] + '.input')).write_bytes(secs[name])
(work / 'tp.dtb').write_bytes(DTB_OVERRIDE.read_bytes() if DTB_OVERRIDE else secs['.dtbauto'])
(work / 'build.conf').write_bytes(b'[UKI]\n')
LOCK.parent.mkdir(parents=True, exist_ok=True); LOCK.touch(exist_ok=True)
with LOCK.open('rb') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cmd = ['python3', str(STUB / 'stubblify'), 'build', '--config=' + str(work / 'build.conf'), '--efi-arch=aa64',
           '--stub=' + str(STUB / 'stubble.efi'), '--linux=' + str(work / 'linux.input'), '--initrd=' + str(work / 'initrd.new'),
           '--devicetree-auto=' + str(work / 'tp.dtb'), '--os-release=@' + str(work / 'osrel.input'), '--cmdline=@' + str(work / 'cmdline.input'),
           '--hwids=', '--section=.hwids:@' + str(work / 'hwids.input'),
           '--uname=' + secs['.uname'].rstrip(b'\0\n').decode('ascii'), '--no-sign-kernel', '--no-measure', '--no-policy-digest', '--output=' + str(out)]
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/builder', 'LC_ALL': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(work)}
    r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, 'stubblify failed: ' + r.stderr[-300:]
ns, nm, nh = m.sections(out.read_bytes())
assert all(ns[k] == secs[k] for k in secs if k not in ('.initrd', '.dtbauto')), 'an unexpected section changed'
assert DTB_OVERRIDE is not None or ns['.dtbauto'] == secs['.dtbauto'], 'the device tree changed without @dtb'
assert DTB_OVERRIDE is None or ns['.dtbauto'].rstrip(b'\0') == DTB_OVERRIDE.read_bytes().rstrip(b'\0'), 'device tree section is not the supplied one'
print('built', out, out.stat().st_size, 'bytes; only .initrd' + (' and .dtbauto' if DTB_OVERRIDE else '') + ' differ')
