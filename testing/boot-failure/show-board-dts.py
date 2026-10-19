#!/usr/bin/env python3
"""Show the Slim 3 board DTS: includes, override style, and any status lines."""
import re
p = '/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts'
lines = open(p, errors='replace').read().splitlines()
print('LINES', len(lines))
for i, l in enumerate(lines):
    if re.search(r'#include|/include/|status\s*=|&[a-z0-9_]+ \{', l):
        print(f'{i+1}: {l}')
