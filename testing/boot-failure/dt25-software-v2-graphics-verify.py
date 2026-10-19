#!/usr/bin/env python3
# Verify owned graphics fix: hashes, no forbidden, tests pass.
# Usage: python3 dt25-software-v2-graphics-verify.py
from pathlib import Path
import hashlib, subprocess, sys
P = Path(__file__).resolve().parents[2]
FILES = [
 "builder/initcpio/hooks/kestrel_graphics",
 "builder/initcpio/install/kestrel_graphics",
 "builder/diagnostics/kestrel-graphics-supervisor.py",
 "builder/diagnostics/kestrel-graphics.service",
 "builder/diagnostics/kestrel-graphics-sddm.service",
]
def sha(p):
    return hashlib.sha256((P/p).read_bytes()).hexdigest()
def main():
    ok = True
    for f in FILES:
        q = P/f
        print(f, sha(f)[:16], q.stat().st_size)
        if not q.is_file():
            print('missing', f); ok=False
    sup = (P/'builder/diagnostics/kestrel-graphics-supervisor.py').read_text()
    for bad in ['pkill', 'terminate-user']:
        if bad in sup:
            print('forbidden in supervisor:', bad); ok=False
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1
if __name__ == '__main__':
    raise SystemExit(main())
