#!/usr/bin/env python3
"""Check log8 shell validation result + captured files."""
import json
r = json.load(open('/mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-log8-shell-result.json'))
print('passed:', r.get('passed'), '| stop:', r.get('stop_reason'))
caps = r.get('captured_files', {})
print('captured:', len(caps))
for k in sorted(caps)[:10]:
    print('   ', k)
