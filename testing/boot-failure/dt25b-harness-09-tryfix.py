#!/usr/bin/env python3
"""Parent fix 2: guest inline Python used `;try:` (compound statement after
semicolon) which is a SyntaxError, so 09-unit-chaos.json was never written.

Replace the try/except aliveness probe with a single-expression
bash kill -0 returncode check (subprocess is already imported in the guest
snippet). No other `;try:` may remain in send strings.
"""
from pathlib import Path

HARNESS = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25b-efi-harness.py')
src = HARNESS.read_text()

old = 'oldgone=True;import errno;try: os.kill(cpb,0);oldgone=False;except Exception: oldgone=True;'
new = 'oldgone=(cpb<=0) or bool(subprocess.run(["bash","-c","kill -0 "+str(cpb)],capture_output=True).returncode);'
# The harness embeds this in a double-quoted string, so file bytes need backslash-quote:
new = new.replace('"', chr(92) + '"')

found = src.count(old)
assert found == 1, 'expected 1 occurrence, found %d' % found
src = src.replace(old, new)
assert ';try:' not in src, 'another ;try: remains'
assert 'except Exception' not in src, 'another except remains'

HARNESS.write_text(src)
print('HARNESS_09_TRYFIX_OK')
