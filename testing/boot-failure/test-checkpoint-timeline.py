#!/usr/bin/env python3
"""Pure file-backed regression. NEVER accesses real firmware."""
import json, subprocess, tempfile, zlib, struct
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64'); T=P/'testing/boot-failure'
base=Path('/home/builder/boot-failure-tests')
with tempfile.TemporaryDirectory(prefix='timeline-v2-',dir=base) as tmp:
    d=Path(tmp); v=d/'vars'; v.mkdir(); exe=d/'timeline'
    subprocess.run(['gcc','-static','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function',str(T/'test-checkpoint-timeline.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(v)],check=True)
    files=sorted(v.iterdir()); assert len(files)==4
    for slot,p in enumerate(files):
        b=bytearray(p.read_bytes()[4:]); assert b[:8]==b'KSTRLOG1' and len(b)<=1024
        version,index,length,crc=struct.unpack_from('<IIII',b,8)
        assert version==1 and index==slot and length==len(b)-80
        b[20:24]=bytes(4); assert zlib.crc32(b)==crc
    r={'passed':True,'firmware_calls':0,'checks':['delayed follow-up warnings','noise filtering','silent late checkpoint','maximum four writes','CRC cross-check']}
    (T/'checkpoint-timeline-v2-result.json').write_text(json.dumps(r,indent=2)); print(json.dumps(r,indent=2))
