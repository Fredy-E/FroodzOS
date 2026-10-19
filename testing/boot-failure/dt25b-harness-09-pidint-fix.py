#!/usr/bin/env python3
"""Parent fix 3: guest 09 JSON carries MainPID as STRING "0" (from
systemctl-show string split) but validate_09_record demands INTEGER 0.
Coerce MainPID to int inside the single-expression comprehension.
Backslash-quote sequences are built via placeholder to keep this
script itself free of escaping hazards.
"""
from pathlib import Path

HARNESS = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25b-efi-harness.py')
src = HARNESS.read_text()


def q(s):
    return s.replace('@', chr(92) + '"')


old_pad = q('    "pad={l.split(@=@,1)[0]:l.split(@=@,1)[1] for l in pa.splitlines() if @=@ in l};"')
new_pad = q('    "pad={a:(int(b) if a==@MainPID@ else b) for a,b in (l.split(@=@,1) for l in pa.splitlines() if @=@ in l)};"')
old_cad = q('    "cad={l.split(@=@,1)[0]:l.split(@=@,1)[1] for l in ca.splitlines() if @=@ in l};"')
new_cad = q('    "cad={a:(int(b) if a==@MainPID@ else b) for a,b in (l.split(@=@,1) for l in ca.splitlines() if @=@ in l)};"')

for old, new, tag in ((old_pad, new_pad, 'pad'), (old_cad, new_cad, 'cad')):
    found = src.count(old)
    assert found == 1, '%s: expected 1, found %d' % (tag, found)
    src = src.replace(old, new)

HARNESS.write_text(src)
print('HARNESS_09_PIDINT_OK')
