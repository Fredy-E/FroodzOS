#!/usr/bin/env python3
"""Fix stubble 64K kernel alignment: verify pristine, patch, diff, rebuild."""
import difflib
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile

PIN = 'stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a'
SRC = f'/home/builder/src/{PIN}'
TARBALL = SRC + '.tar.gz'
PKG = '/mnt/d/CachyOS-ARM64/pkgs/stubble-arm64'
PATCHDIR = PKG + '/patches'
PATCH = PATCHDIR + '/0001-linux-exec-64k-kernel-alignment.patch'
WORK = '/home/builder/stubble-pristine-check'

OLD = """        /* Do we need to ensure under 4gb address on x86? */
        _cleanup_pages_ Pages loaded_kernel_pages = xmalloc_pages(
                        AllocateAnyPages, EfiLoaderCode, EFI_SIZE_TO_PAGES(kernel_size_in_memory), 0);

        uint8_t* loaded_kernel = PHYSICAL_ADDRESS_TO_POINTER(loaded_kernel_pages.addr);
"""
NEW = """        /* Do we need to ensure under 4gb address on x86? */
        /* The ARM64 kernel requires 64K (TEXT_OFFSET) load alignment, but AllocateAnyPages only
         * guarantees 4K. Without this, boot nondeterministically fails in the kernel EFI stub with
         * "FIRMWARE BUG: kernel image not aligned on 64k boundary" (photographed on Lenovo 83N3,
         * 2026-10-11). Over-allocate 15 pages and align the base up inside the allocation; the
         * section bounds check below still holds because the shift is at most 60K. */
        _cleanup_pages_ Pages loaded_kernel_pages = xmalloc_pages(
                        AllocateAnyPages, EfiLoaderCode, EFI_SIZE_TO_PAGES(kernel_size_in_memory) + 15, 0);

        uint8_t* loaded_kernel = (uint8_t*) ALIGN_TO(
                        (uintptr_t) PHYSICAL_ADDRESS_TO_POINTER(loaded_kernel_pages.addr), 65536);
"""


def run(*args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r


# 1. pristine extraction
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
with tarfile.open(TARBALL) as tf:
    tf.extractall(WORK)
names = os.listdir(WORK)
proot = os.path.join(WORK, names[0]) if len(names) == 1 and os.path.isdir(os.path.join(WORK, names[0])) else WORK

mismatches = []
for base, _dirs, files in os.walk(proot):
    for fn in files:
        if fn.endswith(('.o', '.efi')) or fn == 'stubble' or fn.startswith('.'):
            continue
        rel = os.path.relpath(os.path.join(base, fn), proot)
        cur = os.path.join(SRC, rel)
        if not os.path.isfile(cur):
            mismatches.append(f'ONLY_PRISTINE {rel}')
            continue
        if open(os.path.join(base, fn), 'rb').read() != open(cur, 'rb').read():
            mismatches.append(f'MODIFIED {rel}')
print('PRISTINE_CHECK', mismatches if mismatches else 'TREE_PRISTINE')
if mismatches:
    sys.exit('tree not pristine, refusing')

# 2. apply edit
lc = os.path.join(SRC, 'linux.c')
text = open(lc).read()
assert OLD in text, 'anchor not found'
assert text.count(OLD) == 1
open(lc, 'w').write(text.replace(OLD, NEW))
print('EDIT_APPLIED')

# 3. ALIGN_TO availability check
util = open(os.path.join(SRC, 'include/util.h')).read()
print('ALIGN_TO_VIA_UTIL', ('memory-util.h' in util or 'ALIGN_TO' in util))

# 4. generate patch from pristine
old_lines = open(os.path.join(proot, 'linux.c')).read().splitlines()
new_lines = open(lc).read().splitlines()
diff = ''.join(difflib.unified_diff(old_lines, new_lines, fromfile='a/linux.c',
                                    tofile='b/linux.c', lineterm='\n')) + '\n'
header = ('From: Kestrel OS port <local>\n'
          'Subject: [PATCH] linux_exec: 64K-align the loaded ARM64 kernel image\n\n'
          'Rationale: AllocateAnyPages guarantees only 4K alignment, but the\n'
          'ARM64 kernel EFI stub requires 64K (TEXT_OFFSET) load alignment.\n'
          'Boots fail nondeterministically with "FIRMWARE BUG: kernel image\n'
          'not aligned on 64k boundary" (photographed on Lenovo 83N3).\n'
          'Over-allocate 15 pages and align the base up; the existing section\n'
          'bounds check still holds (max shift 60K < 64K extra).\n\n'
          '---\n')
os.makedirs(PATCHDIR, exist_ok=True)
open(PATCH, 'w').write(header + diff)
print('PATCH_WRITTEN', PATCH)

# 5. rebuild
r = run('make', cwd=SRC)
print('MAKE_EXIT', r.returncode)
print(r.stdout[-1500:])
print(r.stderr[-1500:])
if r.returncode != 0:
    sys.exit('stubble rebuild failed')
efi = os.path.join(SRC, 'stubble.efi')
data = open(efi, 'rb').read()
print('STUBBLE_EFI', len(data), hashlib.sha256(data).hexdigest(), data[:2])
shutil.rmtree(WORK, ignore_errors=True)
