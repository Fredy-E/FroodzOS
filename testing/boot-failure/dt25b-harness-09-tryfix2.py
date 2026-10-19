#!/usr/bin/env python3
"""Parent fix 2 (v2): replace 6-piece guest try/except with a single-expression
bash kill -0 aliveness probe. No backslash literals in this script except
via chr(92); the harness file edit is assembled programmatically.
"""
from pathlib import Path

HARNESS = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25b-efi-harness.py')
src = HARNESS.read_text()
BS = chr(92)
Q = BS + '"'

old = (
    '    "oldgone=True;"\n'
    '    "import errno;"\n'
    '    "try:"\n'
    '    " os.kill(cpb,0);oldgone=False;"\n'
    '    "except Exception:"\n'
    '    " oldgone=True;"\n'
)
new = (
    '    "oldgone=(cpb<=0) or bool(subprocess.run(['
    + Q + 'bash' + Q + ',' + Q + '-c' + Q + ',' + Q + 'kill -0 ' + Q
    + '+str(cpb)],capture_output=True).returncode);"\n'
)

found = src.count(old)
assert found == 1, 'expected 1 occurrence, found %d' % found
src = src.replace(old, new)
assert chr(59)+chr(116)+chr(114)+chr(121)+chr(58) not in src, 'another ;try: remains'

HARNESS.write_text(src)
print('HARNESS_09_TRYFIX2_OK')
