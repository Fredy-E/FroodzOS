#!/usr/bin/env python3
"""Authorize only the exact two files backed by matching dt19 test results."""
import hashlib,json,re
from pathlib import Path
P=Path('D:/CachyOS-ARM64'); T=P/'testing/boot-failure'
a=json.loads((T/'dt19-artifact-audit.json').read_text()); assert a['passed']
gates=['dt19-artifact-audit.json','dt19-logger-v2-v1-result.json','qemu-dt19-menu8-fw-off-v1-result.json']
for name in gates:
    r=json.loads((T/name).read_text()); assert r['passed'] and r['uki_sha256']==a['uki_sha256'],name
files=[]
for rel,source,old in [
 ('EFI/Linux/kestrel-live.efi','testing/boot-failure/dt19-candidate.efi','15e9c8bb9d40fdfb7ed31776eff364156a3c3c1f6463f91fd4109a5bb3b9186d'),
 ('boot/grub/grub.cfg','testing/boot-failure/log-option-grub.cfg','b3fb4e16dc3b0eef908d62c4ec80c52af64e87e6c5ed4de7813847d609cc321e')]:
    f=P/source; size=f.stat().st_size; assert size<4294967296
    files.append({'path':rel,'source':source,'bytes':size,'sha256':hashlib.file_digest(f.open('rb'),'sha256').hexdigest(),'old_sha256':old})
assert files[0]['sha256']==a['uki_sha256']
menu=(P/files[1]['source']).read_text(); entries=re.findall(r'^menuentry .*?(?=^menuentry |\Z)',menu,re.S|re.M)
assert len(entries)==11 and 'set default=7' in menu
for i in [7,8]:
    assert 'kestrel_efilog=1' in entries[i] and 'rd.log=console rd.log=file' in entries[i]
assert 'efi-pstore.pstore_disable=1' in menu
m={'revision':'v2-dt19','uki_sha256':a['uki_sha256'],'gates':gates,'files':files,'menu_entries':len(entries),'default_entry':8}
(T/'dt19-update-manifest.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
