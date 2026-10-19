#!/usr/bin/env python3
"""Print the interconnect@16c0000 node and its siblings 1680000/16d0000."""
import re
text = open('/home/builder/boot-failure-tests/slim3.dts', errors='replace').read().splitlines()
want = ('interconnect@1680000', 'interconnect@16c0000', 'interconnect@16d0000')
i = 0
while i < len(text):
    if any(w in text[i] and '{' in text[i] for w in want):
        name = text[i].strip()
        depth = 0
        j = i
        buf = []
        while j < len(text):
            buf.append(text[j])
            depth += text[j].count('{') - text[j].count('}')
            j += 1
            if depth == 0:
                break
        print(f'===== {name} ({len(buf)} lines) =====')
        print('\n'.join(buf[:70]))
        if len(buf) > 70:
            print(f'... +{len(buf) - 70} more')
        i = j
    else:
        i += 1
