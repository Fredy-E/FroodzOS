#!/usr/bin/env python3
"""Validate guest send-string syntax without booting: join the packed tuple
pieces exactly as the harness does, then bash -n the shell and py_compile
the embedded python3 -c payloads."""
import ast
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25b-efi-harness.py')
tree = ast.parse(HARNESS.read_text())
joined = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) \
            and node.targets[0].id in ('B_COLLECT_SEND', 'B_08_JSON_SEND', 'C_CHAOS_SEND'):
        parts = []
        tup = node.value
        items = tup.elts if isinstance(tup, ast.Tuple) else [tup]
        for e in items:
            assert isinstance(e, ast.Constant) and isinstance(e.value, str), node.targets[0].id
            parts.append(e.value)
        joined[node.targets[0].id] = ''.join(parts)

assert set(joined) == {'B_COLLECT_SEND', 'B_08_JSON_SEND', 'C_CHAOS_SEND'}, joined.keys()
print('SENDS_JOINED', {k: len(v) for k, v in joined.items()})

for name, script in joined.items():
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as f:
        f.write(script)
        path = f.name
    r = subprocess.run(['bash', '-n', path], capture_output=True, text=True)
    print(name, 'bash -n rc=', r.returncode, r.stderr[:300])
    assert r.returncode == 0, (name, r.stderr[:500])
    # validate every python3 -c payload
    idx = 0
    n = 0
    while True:
        i = script.find("python3 -c '", idx)
        if i < 0:
            break
        j = script.find("' 2>&1", i)
        assert j > i, name
        payload = script[i + len("python3 -c '"):j]
        # guest escapes \' inside single quotes are consumed by bash printf? keep raw for compile check
        try:
            compile(payload, '<guest-%s-%d>' % (name, n), 'exec')
            print(name, 'payload', n, 'compiles, len', len(payload))
        except SyntaxError as e:
            print(name, 'payload', n, 'SYNTAX FAIL:', e)
            print(repr(payload[max(0, e.offset - 200):e.offset + 100]))
            raise SystemExit(1)
        n += 1
        idx = j + 1
print('ALL_GUEST_SYNTAX_OK')
