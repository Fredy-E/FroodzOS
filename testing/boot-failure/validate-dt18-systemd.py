#!/usr/bin/env python3
"""Full EFI/root/systemd + USB logging regression for exact dt18, flag OFF.
The fixture selects native #8 with only serial-console/deadline alterations
and the firmware flag removed (persistent writes are tested separately).
"""
import hashlib,json,re,subprocess
from pathlib import Path
T=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure'); B=Path('/home/builder/boot-failure-tests')
rev='v2-dt18'; tag='qemu-dt18-menu8-fw-off-v1'; image=B/('qemu-'+rev+'-systemd.fat')
subprocess.run(['python3',str(T/'prepare-log-validation.py'),'--revision',rev,'--systemd'],check=True)
cfg=(T/('qemu-'+rev+'-systemd-grub.cfg')).read_text()
cfg=re.sub(r'^set default=\d+$','set default=7',cfg,flags=re.M).replace('kestrel_efilog=1','')
cfgfile=T/(tag+'-grub.cfg'); cfgfile.write_text(cfg)
pt=json.loads(subprocess.check_output(['sfdisk','--json',str(image)]))['partitiontable']
fs=str(image)+'@@'+str(pt['partitions'][0]['start']*pt['sectorsize'])
subprocess.run(['mcopy','-o','-i',fs,str(cfgfile),'::/boot/grub/grub.cfg'],check=True)
subprocess.run(['python3',str(T/'run-efi-log-validation.py'),'--image',str(image),'--tag',tag,'--systemd','--deadline','480'],check=True)
p=T/(tag+'-result.json'); r=json.loads(p.read_text())
r['uki_sha256']=hashlib.file_digest(Path('/home/builder/uki-'+rev+'/vmlinuz-live.efi').open('rb'),'sha256').hexdigest()
r['native_entry_number']=8; r['firmware_flag_removed_for_this_test']=True
p.write_text(json.dumps(r,indent=2))
