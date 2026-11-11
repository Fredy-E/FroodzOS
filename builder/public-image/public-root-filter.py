#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Turn the private candidate root into a firmware-free, de-identified public-build root (tar stream filter).

    sudo tar --numeric-owner --xattrs --acls -C <mounted candidate root> -cf - . \
      | python3 public-root-filter.py <mounted candidate root> report.json \
      | sqfstar -comp xz -b 131072 -noappend -mkfs-time <epoch> out.sfs

Changes, and nothing else:
  1. removes vendor firmware staged from the owner's Windows installation (usr/lib/firmware/updates/);
  2. removes linux-firmware split packages this laptop does not need (files and pacman database entries);
  3. renames the project-built kernel package 'linux-cachyos-arm64' to 'linux-froodzos-arm64' (files, dtbs directory,
     database entry) and drops the project-local overlay repository ('cachyos-arm64' database, signature, /srv directory,
     pacman.conf section) so that no CachyOS name or key remains;
  4. removes the pacman keyring's PRIVATE key and revocation certificate (the public keyring stays);
  5. rewrites /etc/os-release and the package-owned /usr/lib/os-release identity (no Arch name/logo), removes the Arch logo
     files and the Firefox package (Mozilla trademark policy: not clearly redistributable as an ALARM-built binary);
  6. fixes the 'linux-firmware' meta package dependency list.
The report lists every removal, rename and rewrite so a reviewer can compare it with the expectation.
"""
import io, json, os, re, sys, tarfile

MOUNT, REPORT = sys.argv[1], sys.argv[2]
REMOVE_PKGS = ['linux-firmware-amd', 'linux-firmware-amdgpu', 'linux-firmware-broadcom', 'linux-firmware-cirrus',
               'linux-firmware-intel', 'linux-firmware-mediatek', 'linux-firmware-nvidia', 'linux-firmware-other',
               'linux-firmware-radeon', 'linux-firmware-ti',
               'firefox']              # Mozilla trademark policy: an ALARM-built, Firefox-branded binary is not clearly redistributable
OLD_K, NEW_K = 'linux-cachyos-arm64', 'linux-froodzos-arm64'
BUILD_ID = os.environ.get('FZ_BUILD_ID', 'maverick-public-dev-20261111.2')
LOCAL = os.path.join(MOUNT, 'var/lib/pacman/local')


def read_desc(path):
    d, key = {}, None
    for line in open(path, encoding='utf-8', errors='replace').read().splitlines():
        m = re.match(r'^%([A-Z0-9]+)%$', line)
        if m:
            key = m.group(1)
            d[key] = []
        elif line and key:
            d[key].append(line)
    return d


def db_dir_for(name):
    for e in os.listdir(LOCAL):
        m = re.match(r'^(.*)-[^-]+-[^-]+$', e)
        if m and m.group(1) == name:
            return e
    raise SystemExit('package not in database: ' + name)


def files_of(entry):
    return [x for x in read_desc(os.path.join(LOCAL, entry, 'files')).get('FILES', [])]


removed_entries = {db_dir_for(p): p for p in REMOVE_PKGS}
kept_paths = set()
removed_paths = set()
for e in os.listdir(LOCAL):
    if not os.path.isfile(os.path.join(LOCAL, e, 'files')):
        continue
    target = removed_paths if e in removed_entries else kept_paths
    for f in files_of(e):
        target.add(f.rstrip('/'))
drop_paths = removed_paths - kept_paths          # paths owned only by removed packages
kernel_entry = db_dir_for(OLD_K)
rep = {'removed_files': 0, 'removed_dirs': 0, 'removed_firmware_updates': 0, 'removed_db_entries': 0, 'renamed': [],
       'rewritten': [], 'dropped_other': [], 'kept_members': 0}


def renamed(name):
    n = name
    if n == 'boot/vmlinuz-linux-cachyos-arm64':
        return 'boot/vmlinuz-linux-froodzos-arm64'
    if n == 'boot/vmlinuz-cachyos-arm64.efi':
        return 'boot/vmlinuz-froodzos-arm64.efi'
    if n == 'boot/dtbs/linux-cachyos-arm64' or n.startswith('boot/dtbs/linux-cachyos-arm64/'):
        return n.replace('linux-cachyos-arm64', NEW_K, 1)
    if n == 'var/lib/pacman/local/' + kernel_entry or n.startswith('var/lib/pacman/local/' + kernel_entry + '/'):
        return n.replace(kernel_entry, kernel_entry.replace(OLD_K, NEW_K, 1), 1)
    return n


_etc = open(os.path.join(MOUNT, 'etc/os-release'), encoding='utf-8').read()
NEW_OS_RELEASE = re.sub(r'^LOGO=.*\n', '', re.sub(r'^PRETTY_NAME=.*$', 'PRETTY_NAME="FroodzOS 0.1.0-dev Maverick (ARM64, firmware-free public build)"',
                 re.sub(r'^BUILD_ID=.*$', 'BUILD_ID=' + BUILD_ID, _etc, flags=re.M), flags=re.M), flags=re.M)
ARCH_LOGOS = {'usr/share/pixmaps/archlinux-logo.png', 'usr/share/pixmaps/archlinux-logo.svg',
              'usr/share/pixmaps/archlinux-logo-text.svg', 'usr/share/pixmaps/archlinux-logo-text-dark.svg'}


def rewrite_text(name, data):
    t = data.decode('utf-8')
    if name == 'etc/os-release':
        t = re.sub(r'^BUILD_ID=.*$', 'BUILD_ID=' + BUILD_ID, t, flags=re.M)
        t = re.sub(r'^PRETTY_NAME=.*$', 'PRETTY_NAME="FroodzOS 0.1.0-dev Maverick (ARM64, firmware-free public build)"', t, flags=re.M)
        t = re.sub(r'^LOGO=.*\n', '', t, flags=re.M)             # no Arch logo reference
    elif name == 'usr/lib/os-release':
        t = NEW_OS_RELEASE                                          # the package-owned copy must not say Arch Linux ARM
    elif name == 'etc/pacman.conf':
        t = re.sub(r'\n\[cachyos-arm64\]\n(?:[^\n\[][^\n]*\n)*', '\n', t)
    elif name.startswith('var/lib/pacman/local/' + kernel_entry + '/'):
        t = t.replace(OLD_K, NEW_K).replace('vmlinuz-cachyos-arm64', 'vmlinuz-froodzos-arm64')
    elif re.match(r'var/lib/pacman/local/linux-firmware-[0-9][^/]*/desc$', name):
        lines, out, in_dep = t.split('\n'), [], False
        for ln in lines:
            if ln.startswith('%'):
                in_dep = ln == '%DEPENDS%'
            elif in_dep and ln in REMOVE_PKGS:
                continue
            out.append(ln)
        t = '\n'.join(out)
    return t.encode('utf-8')


tin = tarfile.open(fileobj=sys.stdin.buffer, mode='r|')
tout = tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.PAX_FORMAT, encoding='utf-8')
for ti in tin:
    name = ti.name[2:] if ti.name.startswith('./') else ti.name
    name = name.rstrip('/') if name != '.' else '.'
    if name == '.':
        tout.addfile(ti)
        continue
    # --- removals ---
    if name == 'usr/lib/firmware/updates' or name.startswith('usr/lib/firmware/updates/'):
        rep['removed_firmware_updates'] += 1
        continue
    parts = name.split('/')
    if len(parts) >= 5 and parts[:4] == ['var', 'lib', 'pacman', 'local'] and parts[4] in removed_entries:
        rep['removed_db_entries'] += 1
        continue
    if name in drop_paths:
        rep['removed_dirs' if ti.isdir() else 'removed_files'] += 1
        continue
    if name in ARCH_LOGOS:
        rep['dropped_other'].append(name)
        continue
    if name in ('var/lib/pacman/sync/cachyos-arm64.db', 'var/lib/pacman/sync/cachyos-arm64.db.sig'):
        rep['dropped_other'].append(name)
        continue
    if name == 'srv/cachyos-arm64':
        rep['dropped_other'].append(name)
        continue
    if name.startswith('etc/pacman.d/gnupg/private-keys-v1.d/') or name.startswith('etc/pacman.d/gnupg/openpgp-revocs.d/'):
        rep['dropped_other'].append(name)
        continue
    # --- rewrites and renames ---
    new = renamed(name)
    if new != name:
        rep['renamed'].append([name, new])
    if ti.isreg() and (name in ('etc/os-release', 'usr/lib/os-release', 'etc/pacman.conf') or
                       name in ('var/lib/pacman/local/%s/desc' % kernel_entry, 'var/lib/pacman/local/%s/files' % kernel_entry) or
                       re.match(r'var/lib/pacman/local/linux-firmware-[0-9][^/]*/desc$', name)):
        data = tin.extractfile(ti).read()
        out = rewrite_text(name, data)
        ti.size = len(out)
        ti.name = new
        ti.pax_headers = dict(ti.pax_headers)
        rep['rewritten'].append(name)
        tout.addfile(ti, io.BytesIO(out))
        rep['kept_members'] += 1
        continue
    if new != name:
        ti.name = new
        if ti.islnk():
            ti.linkname = renamed(ti.linkname)
    tout.addfile(ti, tin.extractfile(ti) if ti.isreg() else None)
    rep['kept_members'] += 1
rep['dropped_other'] = sorted(set(rep['dropped_other']))[:50]
json.dump(rep, open(REPORT, 'w', encoding='utf-8'), indent=1)
print('filter done', {k: (v if isinstance(v, int) else len(v)) for k, v in rep.items()}, file=sys.stderr)
try:                      # sqfstar stops reading at the end-of-archive marker, so the final padding may hit a closed pipe
    tout.close()
except BrokenPipeError:
    pass
