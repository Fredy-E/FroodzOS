#!/usr/bin/env python3
"""Compile/run isolated tests; export real test bytes for Windows reader tests."""
import hashlib,json,struct,subprocess,tempfile,zlib
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64'); T=P/'testing/boot-failure'
base=Path('/home/builder/boot-failure-tests'); base.mkdir(exist_ok=True)
checks={}
with tempfile.TemporaryDirectory(prefix='checkpoint-unit-',dir=base) as tmp:
 d=Path(tmp); (d/'vars').mkdir()
 for src,out,flags in [(P/'builder/diagnostics/kestrel-checkpoint.c',d/'production',[]),(T/'test-checkpoint.c',d/'test',['-Wno-unused-function'])]:
  subprocess.run(['gcc','-static','-O2','-Wall','-Wextra','-Werror',*flags,str(src),'-o',str(out)],check=True)
 checks['compile_werror']=True
 subprocess.run([str(d/'test'),str(d/'vars')],check=True)
 checks['unit_harness']=True
 export=T/'checkpoint-reader-fixtures'
 export.mkdir(exist_ok=True)
 files=sorted((d/'vars').iterdir()); assert len(files)==4
 for slot,f in enumerate(files):
  b=f.read_bytes(); assert struct.unpack('<I',b[:4])[0]==7
  record=bytearray(b[4:]); assert record[:8]==b'KSTRLOG1'
  ver,idx,n,crc=struct.unpack_from('<IIII',record,8)
  assert ver==1 and idx==slot and len(record)==80+n and len(record)<=1024
  record[20:24]=bytes(4); assert zlib.crc32(record)==crc
  (export/f'{slot}.bin').write_bytes(b[4:])
 checks['four_bounded_valid_crc_records']=True
 bad=bytearray((export/'0.bin').read_bytes()); bad[-1]^=1
 (export/'corrupt.bin').write_bytes(bad)
 (export/'truncated.bin').write_bytes(b'KSTRLOG1')
checks['synthetic_fixture_notice']=True
result={'passed':all(checks.values()),'checks':checks,'note':'Synthetic unit inputs, not native boot logs. No firmware touched.'}
(T/'checkpoint-unit-result.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
