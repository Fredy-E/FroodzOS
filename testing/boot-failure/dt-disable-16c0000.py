#!/usr/bin/env python3
"""DIAGNOSTIC: disable pcie_south_anoc (16c0000) in the Slim 3 board DTS.
Local-only experiment, not for publication. Verifies pristine base first,
rebuilds the exact DTB target, and records the change as a patch file."""
import difflib
import hashlib
import os
import subprocess
import sys
import tarfile

KSRC = '/home/builder/src/ksrc'
BOARD = 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
TARBALL = '/home/builder/src/linux-ms-dev-kit-3f0d8691afa098ba378d7d5a3968f03219887719.tar.gz'
PATCH = ('/mnt/d/CachyOS-ARM64/pkgs/linux-cachyos-arm64/patches/'
         '0006-diagnostic-disable-pcie-south-anoc.patch')
WORK = '/home/builder/dts-pristine-check'
DTB = KSRC + '/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'

OVERRIDE = '''
/* DIAGNOSTIC 2026-10-11: disable pcie_south_anoc to test whether its qnoc
 * probe is the silent-reset site observed right after the 1680000 probe.
 * Local-only experiment, not for publication. */
&pcie_south_anoc {
	status = "disabled";
};
'''

shutil_rm = __import__('shutil').rmtree
shutil_rm(WORK, ignore_errors=True)
os.makedirs(WORK)
with tarfile.open(TARBALL) as tf:
    tf.extractall(WORK, filter='fully_trusted')
names = os.listdir(WORK)
proot = os.path.join(WORK, names[0]) if len(names) == 1 else WORK
# tarball root may nest differently; find the board file
cand = None
for base, _d, files in os.walk(proot):
    if 'x126100-lenovo-ideapad-slim3.dts' in files:
        cand = os.path.join(base, 'x126100-lenovo-ideapad-slim3.dts')
        break
assert cand, 'board DTS not found in tarball'
cur = os.path.join(KSRC, BOARD)
pristine = open(cand, 'rb').read().decode()
current = open(cur).read()
# allow only our own 0001-0005 kernel patches' footprint: board DTS must be pristine or already carry this override
if current != pristine and 'pcie_south_anoc' not in current:
    print('BOARD_DTS_DIRTY_UNEXPECTED')
    sys.exit(1)
print('BOARD_DTS_BASE_OK')
if '&pcie_south_anoc' not in current:
    open(cur, 'a').write(OVERRIDE)
    print('OVERRIDE_APPENDED')
else:
    print('OVERRIDE_ALREADY_PRESENT')
current = open(cur).read()

r = subprocess.run(['make', 'ARCH=arm64', 'qcom/x126100-lenovo-ideapad-slim3.dtb'],
                   cwd=KSRC, capture_output=True, text=True)
print('DTB_MAKE_EXIT', r.returncode)
print((r.stdout + r.stderr)[-800:])
if r.returncode != 0:
    sys.exit('dtb build failed')
data = open(DTB, 'rb').read()
print('DTB', len(data), hashlib.sha256(data).hexdigest())
r = subprocess.run(['fdtget', DTB, '/soc@0/interconnect@16c0000', 'status'],
                   capture_output=True, text=True)
print('NODE_STATUS', r.stdout.strip() or r.stderr.strip())

diff = ''.join(difflib.unified_diff(pristine.splitlines(), current.splitlines(),
                                    fromfile='a/' + BOARD, tofile='b/' + BOARD,
                                    lineterm='\n')) + '\n'
header = ('From: Kestrel OS port <local>\n'
          'Subject: [PATCH, DIAGNOSTIC, LOCAL-ONLY] disable pcie_south_anoc on Slim 3\n\n'
          'Rationale: native boot resets silently right after the 1680000\n'
          'interconnect probe; 16c0000 (pcie_south_anoc) is next in probe\n'
          'order. Single-variable test whether its qnoc probe is the reset\n'
          'site. NOT for publication or general ARM64 support.\n\n'
          '---\n')
open(PATCH, 'w').write(header + diff)
print('PATCH_WRITTEN', PATCH)
shutil_rm(WORK, ignore_errors=True)
