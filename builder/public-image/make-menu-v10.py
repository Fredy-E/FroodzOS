#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Simple menus. Builds (1) grub.cfg.public4 for the release image and (2) grub.cfg.v10 for the private stick.

The release menu has two boot entries and a firmware entry; no submenu, no chain-loading. The stick menu adds the previous version
(known-good graphics), a text recovery console and the original system. All linux lines are taken unchanged from menu v7 / the public menu.
"""
import hashlib, pathlib, sys

C = pathlib.Path(r'D:\CachyOS-ARM64\maverick-dev-candidate-20261110')
v7 = (C / 'output' / 'grub.cfg.v7').read_text(encoding='utf-8').split('\n')
pub = (C / 'output' / 'grub.cfg.public').read_text(encoding='utf-8').split('\n')


def block(lines, start):
    i = next(k for k, l in enumerate(lines) if l.startswith(start))
    j = next(k for k in range(i, len(lines)) if lines[k] == '}')
    return lines[i:j + 1]


def head(lines):
    return lines[:next(k for k, l in enumerate(lines) if l.startswith('menuentry '))]


def retitle(b, title):
    return ["menuentry '%s' {" % title] + b[1:]


def clean_echo(b):          # drop test-only echo lines
    return [l for l in b if not l.strip().startswith('echo ')]


FW = ['menuentry \'Firmware boot menu\' {', '    exit', '}']

# ---- release menu
p1 = clean_echo(retitle(block(pub, "menuentry 'FroodzOS 0.1.0-dev Maverick (firmware-free build)"), 'FroodzOS 0.1.0-dev.2 Maverick'))
p2 = clean_echo(retitle(block(pub, "menuentry 'FroodzOS fallback - no touchpad driver'"), 'FroodzOS 0.1.0-dev.2 Maverick - without the touchpad driver'))
UNB = lambda ls: [l.replace(' kestrel_efilog=0', ' kestrel_efilog=0 kestrel_graphics_unbounded=1 sysctl.kernel.apparmor_restrict_unprivileged_userns=0') if l.startswith('    linux /EFI/Linux/froodzos-') else l for l in ls]
rel = head(pub) + UNB(p1) + [''] + UNB(p2) + [''] + FW + ['']
rel = [l.replace('public-build menu (2026-11-11)', 'release menu (2026-11-13)') for l in rel]
(C / 'output' / 'grub.cfg.public4').write_bytes('\n'.join(rel).encode('utf-8'))
print('public4', hashlib.sha256('\n'.join(rel).encode('utf-8')).hexdigest())

# ---- stick menu
d1 = clean_echo(retitle(block(v7, "menuentry 'FroodzOS 0.1.0-dev.2 (Phase 1 handlers) - touchpad"), 'FroodzOS 0.1.0-dev.2 Maverick'))
d2 = clean_echo(retitle(block(v7, "menuentry 'FroodzOS 0.1.0-dev.2 (Phase 1 handlers) - no touchpad"), 'FroodzOS 0.1.0-dev.2 Maverick - without the touchpad driver'))
prev = clean_echo(retitle(block(v7, "menuentry 'FroodzOS 0.1.0-dev Maverick - Wi-Fi + graphics + touchpad (default)'"), 'FroodzOS 0.1.0-dev Maverick - previous version (older desktop, known-good graphics)'))
rec = retitle(block(v7, "menuentry 'Text recovery (dt24)'"), 'Text recovery console')
orig = retitle(block(v7, "menuentry 'Original system - text + CPU temperature log'"), 'Original system (text only)')
# temporary test entry: same as the first entry but with graphics environment variant C (see tools/gfx-env-C.txt)
d3 = retitle(d1, 'FroodzOS 0.1.0-dev.2 Maverick - graphics test variant C (try only if the first entry shows no desktop)')
d3 = [l.replace('/EFI/Linux/froodzos-maverick-tp.efi', '/EFI/Linux/froodzos-maverick-tp-gfxC.efi') for l in d3]
stick = head(v7) + UNB(d1) + [''] + UNB(d2) + [''] + prev + [''] + rec + [''] + orig + [''] + FW + ['']
stick = [l.replace('menu v7 (2026-11-12)', 'menu v10 (2026-11-13)') for l in stick]
(C / 'output' / 'grub.cfg.v10').write_bytes('\n'.join(stick).encode('utf-8'))
print('v10', hashlib.sha256('\n'.join(stick).encode('utf-8')).hexdigest())
