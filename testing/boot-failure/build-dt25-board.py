#!/usr/bin/env python3
"""Apply 0020, build one DTB, constrain scope to two status properties.

Evidence-integrity fix (dt25-fix-v2):
- Project root derived from __file__, not a Windows-only literal.
- Explicit --tag or --result/--log overrides; tag syntax validated.
- ALL intended outputs are preflighted BEFORE any source/DT/copy/build
  mutation. Collision refuses with exit 2 and changes zero bytes.
- Exclusive creation (open 'x'); no unlink-existing to obtain freshness.
- Resume is safe: pristine baseline proceeds; byte-exact accepted 0020
  state refuses without reapplying; any other source state refuses.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
T = Path(__file__).resolve().parent
K = Path('/home/builder/src/ksrc')
REL = 'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
BASELINE_DTS = Path('/home/builder/boot-failure-tests/dt25-baseline/board.dts')
BASELINE_DTB = Path('/home/builder/boot-failure-tests/dt25-baseline/board.dtb')

TAG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def fail(msg):
    print(f'ERROR: {msg}', file=sys.stderr)
    raise SystemExit(2)


def validate_tag(tag):
    if not TAG_RE.fullmatch(tag):
        fail(f'invalid --tag {tag!r}: must match {TAG_RE.pattern} (no traversal, no slashes)')
    return tag


def resolve_output(explicit, tagged_default, legacy):
    if explicit is not None:
        p = Path(explicit)
        try:
            rp = p.resolve()
            td = T.resolve()
            if rp != td and td not in rp.parents:
                fail(f'explicit output {p} escapes evidence dir {T}')
        except SystemExit:
            raise
        except Exception as e:
            fail(f'bad explicit output {p}: {e}')
        return p
    if tagged_default is not None:
        return tagged_default
    return legacy


def preflight(paths):
    existing = [str(p) for p in paths if Path(p).exists()]
    if existing:
        fail('refusing: intended output(s) already exist (no bytes changed): '
             + ', '.join(existing))


parser = argparse.ArgumentParser()
parser.add_argument('--tag', default=None, help='fresh evidence tag, e.g. fixv2-20261018-01')
parser.add_argument('--log', default=None)
parser.add_argument('--board-result', default=None)
parser.add_argument('--dt24-result', default=None)
parser.add_argument('--dt21-result', default=None)
parser.add_argument('--build-result', default=None)
args = parser.parse_args()

if args.tag is not None:
    validate_tag(args.tag)
    tag = args.tag
    log_d = T / f'dt25-thermal-fix-v2-build-{tag}.log'
    board_d = T / f'dt25-thermal-fix-v2-board-{tag}.json'
    dt24_d = T / f'dt25-thermal-fix-v2-dt24-retained-{tag}.json'
    dt21_d = T / f'dt25-thermal-fix-v2-dt21-retained-{tag}.json'
    build_d = T / f'dt25-thermal-fix-v2-dtb-build-result-{tag}.json'
else:
    tag = None
    log_d = T / 'dt25-thermal-build-dtb.log'
    board_d = T / 'dt25-thermal-board-green.json'
    dt24_d = T / 'dt25-thermal-dt24-retained-green.json'
    dt21_d = T / 'dt25-thermal-dt21-retained-green.json'
    build_d = T / 'dt25-thermal-dtb-build-result.json'

log = resolve_output(Path(args.log) if args.log else None,
                     log_d if args.tag else None, log_d)
board_result = resolve_output(Path(args.board_result) if args.board_result else None,
                              board_d if args.tag else None, board_d)
dt24_result = resolve_output(Path(args.dt24_result) if args.dt24_result else None,
                             dt24_d if args.tag else None, dt24_d)
dt21_result = resolve_output(Path(args.dt21_result) if args.dt21_result else None,
                             dt21_d if args.tag else None, dt21_d)
build_result = resolve_output(Path(args.build_result) if args.build_result else None,
                              build_d if args.tag else None, build_d)

# PREFLIGHT FIRST: before any source read that gates mutation, and well
# before patch/copy/fdtput/build. Zero bytes change on collision.
preflight([log, board_result, dt24_result, dt21_result, build_result])

FIXBASE = Path('/home/builder/boot-failure-tests/dt25-fix-v2-fixtures')
source = K / REL
dtb = source.with_suffix('.dtb')
baseline_dts = BASELINE_DTS
baseline_dtb = BASELINE_DTB
patch = ROOT / 'pkgs/linux-cachyos-arm64/patches/0020-diagnostic-restore-cpu-tsens.patch'
if not patch.is_file():
    fail(f'Missing 0020 patch: {patch}')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


baseline_bytes = baseline_dts.read_bytes()
try:
    source_bytes = source.read_bytes()
except FileNotFoundError:
    fail(f'source missing: {source}')

if source_bytes == baseline_bytes:
    pristine = True
else:
    # Byte-exact accepted-state check WITHOUT mutating the work tree:
    # reverse the patch to stdout and compare to the frozen baseline.
    import os as _os
    _env = dict(_os.environ, TMPDIR=str(FIXBASE))
    try:
        FIXBASE.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass
    try:
        reverted = subprocess.check_output(
            ['patch', '--batch', '--silent', '-R', '-p1',
             '--output=-', str(source), str(patch)], cwd=str(FIXBASE), env=_env)
    except subprocess.CalledProcessError:
        reverted = None
    if reverted == baseline_bytes:
        fail('source already contains accepted 0020 (byte-exact patched state); '
             'refusing to reapply. Restore frozen baseline for a rebuild, or '
             'rerun predicates on the current immutable DT with a fresh --tag '
             '(no make/DT rebuild needed). No bytes changed.')
    fail('incompatible source state (neither frozen baseline nor byte-exact '
         'accepted 0020); refusing to patch blindly. No bytes changed.')

image = K / 'arch/arm64/boot/Image'
config = K / '.config'
image_hash = sha(image)
config_hash = sha(config)
old_dtb = baseline_dtb

# forward dry-run then real apply (only reachable on pristine source)
import os as _os2
_env2 = dict(_os2.environ, TMPDIR=str(FIXBASE))
for dry in (True, False):
    cmd = ['patch', '--batch', '--forward', '-p1', '-d', str(K), '-i', str(patch)]
    if dry:
        cmd.append('--dry-run')
    subprocess.run(cmd, check=True, env=_env2)

text = source.read_text()
assert '&tsens0' in text and '&tsens1' in text, 'Patch markers missing'
assert text.count('status = "okay"') >= 2

# single-board build under lock, propagate real exit, no Image/config rebuild
with log.open('x') as lf:
    run = subprocess.run(
        ['flock', '/home/builder/boot-failure-tests/dt25-build.lock',
         'make', 'ARCH=arm64', 'CROSS_COMPILE=', '-j2',
         'qcom/x126100-lenovo-ideapad-slim3.dtb'],
        cwd=K, stdout=lf, stderr=subprocess.STDOUT)
run.check_returncode()
assert sha(image) == image_hash, 'Kernel Image changed'
assert sha(config) == config_hash, 'Kernel config changed'

# predicate runs with preflighted exclusive results (checkers use open 'x')
subprocess.run(['python3', str(T / 'check-dt25-board.py'), str(dtb),
                '--result', str(board_result)], check=True)
subprocess.run(['python3', str(T / 'check-dt24-board.py'), str(dtb),
                '--result', str(dt24_result)], check=True)
subprocess.run(['python3', str(T / 'check-dt21-board.py'), str(dtb),
                '--result', str(dt21_result)], check=True)


def sym(name):
    return subprocess.check_output(['fdtget', '-t', 's', str(dtb), '/__symbols__', name], text=True).strip()


allowed = {(sym('tsens0'), 'status'), (sym('tsens1'), 'status')}


def normalized(path):
    txt = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(path)],
                                  text=True, stderr=subprocess.DEVNULL)
    stack, out = [], []
    for line in txt.splitlines():
        s = line.strip()
        if s.endswith('{'):
            nm = s[:-1].strip().split()[-1]
            parent = stack[-1] if stack else ''
            stack.append('/' if nm == '/' else parent.rstrip('/') + '/' + nm)
        if '=' in s and stack and (stack[-1], s.split('=', 1)[0].strip()) in allowed:
            continue
        out.append(line)
        if s == '};':
            stack.pop()
    assert not stack
    return '\n'.join(out)


assert normalized(old_dtb) == normalized(dtb), 'Compiled changes outside two tsens status properties'

# reverse reproduces frozen baseline bytes exactly (without touching work tree)
reverted = subprocess.check_output(
    ['patch', '--batch', '--silent', '-R', '-p1', '--output=-', str(source), str(patch)], cwd=str(FIXBASE), env=_env2)
assert reverted == baseline_dts.read_bytes(), 'Patch reverse mismatch'

report = {'passed': True, 'kernel_unchanged': True, 'config_unchanged': True,
          'allowed_changed_properties': sorted([list(x) for x in allowed]),
          'only_allowed_compiled_properties_changed': True,
          'patch_forward_and_reverse_verified': True,
          'dtb_sha256': sha(dtb), 'dtb_bytes': dtb.stat().st_size,
          'kernel_sha256': image_hash, 'config_sha256': config_hash,
          'old_dtb': str(old_dtb), 'native_hardware_validated': False,
          'tag': tag}
with build_result.open('x') as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
