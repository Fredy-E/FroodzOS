#!/usr/bin/env python3
"""Independent read-only provenance and disposable integration probes.

Never run the new test scripts' __main__ sections: those currently unlink their
prior result files. No source/media/service/firmware changes. Namespace mounts
and generated scripts are confined to a new builder fixture directory.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
NEW = Path('/home/builder/uki-v2-dt25')
OLD = Path('/home/builder/uki-v2-dt24')
ROOT = Path('/home/builder/imgroot')
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RESULT = T / f'dt25-parent-{STAMP}-integration-probe.json'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pe_section_hashes(path):
    with Path(path).open('rb') as stream:
        assert stream.read(2) == b'MZ'
        stream.seek(60)
        pe = struct.unpack('<I', stream.read(4))[0]
        stream.seek(pe)
        assert stream.read(4) == b'PE\0\0'
        coff = stream.read(20)
        machine, count = struct.unpack_from('<HH', coff)
        optional_size = struct.unpack_from('<H', coff, 16)[0]
        assert machine == 0xaa64
        table = pe + 24 + optional_size
        wanted = {'.text', '.linux', '.hwids', '.cmdline', '.uname', '.dtbauto', '.initrd'}
        answer = {}
        for index in range(count):
            stream.seek(table + index * 40)
            row = stream.read(40)
            name = row[:8].rstrip(b'\0').decode('ascii')
            if name not in wanted:
                continue
            virtual_size = struct.unpack_from('<I', row, 8)[0]
            raw_size, offset = struct.unpack_from('<II', row, 16)
            assert 0 < virtual_size <= raw_size
            assert offset + raw_size <= Path(path).stat().st_size
            assert name not in answer
            stream.seek(offset)
            data = stream.read(virtual_size)
            answer[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        assert set(answer) == wanted
        return answer


def run(argv, **kwargs):
    completed = subprocess.run(argv, capture_output=True, text=True, **kwargs)
    return {'exit_code': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr}


B.mkdir(parents=True, exist_ok=True)
with (B / 'dt25-build.lock').open('a+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    report = {'native_hardware_validated': False, 'candidate_accepted': False}
    audit = json.loads((T / 'dt25-artifact-audit.json').read_text())
    new_sha = digest(NEW / 'vmlinuz-live.efi')
    new_sections = pe_section_hashes(NEW / 'vmlinuz-live.efi')
    old_sections = pe_section_hashes(OLD / 'vmlinuz-live.efi')
    source_hashes_match = all(
        digest(P / rel) == data['sha256'] for rel, data in audit['sources'].items()
    )
    checks = {
        'new_uki_hash': new_sha == '9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb',
        'host_candidate_copy_hash': digest(T / 'dt25-candidate.efi') == new_sha,
        'old_uki_unchanged': digest(OLD / 'vmlinuz-live.efi') == '4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02',
        'old_sfs_unchanged': digest(P / 'live-staging-v2/arch/aarch64/airootfs.sfs') == '5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c',
        'source_hashes_match_audit': source_hashes_match,
        'pe_dtb_matches_accepted_dt25': new_sections['.dtbauto']['sha256'] == 'f5f67c13bdfe975998b083ac06465c36231c0bae205e8e60fff99832264f5232',
        'pe_initrd_matches_file': new_sections['.initrd']['sha256'] == digest(NEW / 'live-initramfs.img'),
        'pe_kernel_expected': new_sections['.linux']['sha256'] == '682273a91f2016b9d5484857639bd043e021b961d7f4cfd385a09566b2df3abc',
    }
    for name in ('.linux', '.text', '.hwids', '.cmdline', '.uname'):
        checks[f'unchanged_{name}'] = new_sections[name] == old_sections[name]
    report['provenance_checks'] = checks
    report['provenance_passed'] = all(checks.values())
    report['new_uki_sha256'] = new_sha
    report['pe_sections'] = new_sections
    temp = Path(tempfile.mkdtemp(dir=B, prefix='dt25-parent-probe-'))
    report['fixture'] = str(temp)
    ex = temp / 'extracted'
    ex.mkdir()
    extracted = run(['lsinitcpio', '-x', str(NEW / 'live-initramfs.img')], cwd=ex, timeout=120)
    assert extracted['exit_code'] == 0, extracted
    env = dict(os.environ)
    env.pop('LD_LIBRARY_PATH', None)
    report['chroot_binary_versions'] = run(
        ['chroot', str(ex), '/usr/bin/busybox', 'ash', '-c',
         '/usr/bin/findmnt --version && /usr/bin/mountpoint --version'], env=env, timeout=30
    )
    inheritance = temp / 'exported-getarg.sh'
    inheritance.write_text(
        '#!/bin/bash\ngetarg() { printf "1\\n"; }\nexport -f getarg\n'
        + f'"{ex}/usr/bin/busybox" ash -c '\
          "'command -v getarg || { echo GETARG_NOT_INHERITED; exit 23; }; getarg kestrel_graphics'\n"
    )
    report['bash_function_to_packed_ash'] = run(['bash', str(inheritance)], timeout=30)
    full_graph = temp / 'full-target-graph.sh'
    full_graph.write_text(f'''#!/bin/bash
set -euo pipefail
BASE="{temp}"
EX="{ex}"
mkdir -p "$BASE/ovl" "$BASE/sysroot"
mount -t tmpfs tmpfs "$BASE/ovl"
mkdir -p "$BASE/ovl/upper" "$BASE/ovl/work"
mount -t overlay overlay -o lowerdir={ROOT},upperdir="$BASE/ovl/upper",workdir="$BASE/ovl/work" "$BASE/sysroot"
mount -t proc proc "$BASE/sysroot/proc"
export PATH="$EX/usr/bin:$EX/bin:/usr/bin:/bin"
export LD_LIBRARY_PATH="$EX/usr/lib:$EX/lib"
export KESTREL_SYSROOT="$BASE/sysroot"
export KESTREL_ETC="$EX/etc"
"$EX/usr/bin/busybox" ash -c 'getarg() {{ case "$1" in kestrel_console) printf "ttyAMA0\\n";; *) printf "1\\n";; esac; }}; . "{ex}/hooks/kestrel_graphics"; kestrel_stage_graphics'
test -f "$BASE/sysroot/etc/systemd/system/kestrel-graphics.service"
findmnt -n -o FSTYPE "$BASE/sysroot"
systemd-analyze --root="$BASE/sysroot" verify multi-user.target default.target kestrel-graphics.service kestrel-graphics-sddm.service
''')
    report['full_target_graph'] = run(
        ['unshare', '--mount', '--propagation', 'private', 'bash', str(full_graph)], timeout=120
    )
    report['new_harness_existing_output_unlink'] = {
        name: 'out.unlink()' in (T / name).read_text()
        for name in ('test-platform-graphics-gate.py', 'test-dt25-packed-graphics.py')
    }
    report['packed_harness_failed_case_preservation_stub'] = 'return False' in (
        T / 'test-dt25-packed-graphics.py').read_text().split('def _test_failed', 1)[1].split('def test_', 1)[0]
    report['requires_changes'] = (
        any(report['new_harness_existing_output_unlink'].values())
        or report['packed_harness_failed_case_preservation_stub']
        or report['bash_function_to_packed_ash']['exit_code'] != 0
        or report['full_target_graph']['exit_code'] != 0
        or report['chroot_binary_versions']['exit_code'] != 0
        or not report['provenance_passed']
    )
    with RESULT.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'result_path': str(RESULT), **report}, indent=2))
    # Retain this new disposable fixture and original integration evidence.
    raise SystemExit(1 if report['requires_changes'] else 0)
