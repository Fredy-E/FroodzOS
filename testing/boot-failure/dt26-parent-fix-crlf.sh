#!/bin/bash
# Parent fix: supervisor MUST be LF-only (kernel shebang exec fails on CR).
# Also removes host-generated __pycache__ junk (never a manifest source).
set -u
F=/mnt/d/CachyOS-ARM64/builder/diagnostics/kestrel-graphics-supervisor.py
echo "before: $(stat -c%s "$F") bytes"
sed -i 's/\r$//' "$F"
echo "after: $(stat -c%s "$F") bytes"
file "$F"
head -1 "$F" | od -c | head -2
python3 -c "import ast; ast.parse(open('$F', encoding='utf-8').read()); print('py-parse OK')"
find /mnt/d/CachyOS-ARM64/builder /mnt/d/CachyOS-ARM64/testing -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
echo "pycache sweep done"
sha256sum "$F"
