#!/usr/bin/env python3
"""Why did menutest15 fail despite reaching multi-user?"""
import json
r = json.load(open('/mnt/d/CachyOS-ARM64/testing/boot-failure/qemu-v2-menutest15-result.json'))
print('passed:', r.get('passed'))
for k in ('checks', 'markers', 'failed', 'errors', 'missing'):
    if k in r:
        print('##', k)
        print(json.dumps(r[k], indent=1)[:1500])
