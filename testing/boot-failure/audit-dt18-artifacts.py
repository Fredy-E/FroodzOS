#!/usr/bin/env python3
"""Provenance gate: embedded kernel/DTB vs exact build inputs, no secrets."""
import hashlib,json,shutil,struct
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64');T=P/'testing/boot-failure'; K=Path('/home/builder/src/ksrc')
uki=Path('/home/builder/uki-v2-dt18/vmlinuz-live.efi'); b=uki.read_bytes()
o=struct.unpack_from('<I',b,0x3c)[0];assert b[o:o+4]==b'PE\0\0'
machine,nsec=struct.unpack_from('<HH',b,o+4);assert machine==0xaa64
opt=struct.unpack_from('<H',b,o+20)[0]; sections={}
for i in range(nsec):
 h=o+24+opt+40*i; name=b[h:h+8].rstrip(b'\0').decode(); vsize=struct.unpack_from('<I',b,h+8)[0]; rawsize,ptr=struct.unpack_from('<II',b,h+16)
 assert vsize<=rawsize or rawsize==0
 sections[name]=b[ptr:ptr+vsize]
checks={'.linux':K/'arch/arm64/boot/Image','.dtbauto':K/'arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb','.initrd':Path('/home/builder/uki-v2-dt18/live-initramfs.img')}
for name,src in checks.items(): assert sections[name]==src.read_bytes(),name
assert b'efi-pstore.pstore_disable=1' in sections['.cmdline']
source=P/'builder/diagnostics/kestrel-checkpoint.c'
report={'passed':True,'revision':'v2-dt18','uki_bytes':len(b),'uki_sha256':hashlib.sha256(b).hexdigest(),'embedded_inputs':{n:{'bytes':len(sections[n]),'sha256':hashlib.sha256(sections[n]).hexdigest()} for n in checks},'logger_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pstore_nvram_disabled_in_default_cmdline':True,'native_boot_verified':False}
(T/'dt18-artifact-audit.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
dest=T/'dt18-candidate.efi'
with dest.open('xb') as f:f.write(b)
assert hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()==report['uki_sha256']
