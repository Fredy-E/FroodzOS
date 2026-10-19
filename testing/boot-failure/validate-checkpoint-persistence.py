#!/usr/bin/env python3
"""Exact-UKI EFI checkpoint persistence test with disposable AAVMF pflash.
No physical media or host firmware is accessed. Never overwrites old results.
"""
import base64,hashlib,json,os,re,select,shutil,struct,subprocess,time,zlib
from pathlib import Path
P=Path('/mnt/d/CachyOS-ARM64'); T=P/'testing/boot-failure'
BASE=Path('/home/builder/boot-failure-tests'); TAG='dt14-checkpoint-v1'
OUT=BASE/TAG
if OUT.exists(): raise SystemExit('Use a fresh test tag; existing evidence preserved')
OUT.mkdir()
REV='v2-dt14'; UKI=Path('/home/builder/uki-'+REV+'/vmlinuz-live.efi')
subprocess.run(['python3',str(T/'prepare-partitioned-validation.py'),'--revision',REV],check=True)
IMAGE=BASE/('qemu-'+REV+'-shell.fat')
pt=json.loads(subprocess.check_output(['sfdisk','--json',str(IMAGE)]))['partitiontable']
FS=str(IMAGE)+'@@'+str(pt['partitions'][0]['start']*pt['sectorsize'])
subprocess.run(['mmd','-i',FS,'::/Logs'],check=True)
marker=OUT/'KESTREL-LOG-TARGET';marker.write_text('KESTREL_A64_USB_CAPTURE_V1\n')
subprocess.run(['mcopy','-i',FS,str(marker),'::/KESTREL-LOG-TARGET'],check=True)
FW=T/'uefi-package/usr/share/AAVMF'
CODE=FW/'AAVMF_CODE.no-secboot.fd'; VARS=OUT/'vars.fd'
shutil.copyfile(FW/'AAVMF_VARS.fd',VARS)
GUID='674b8af1-da8e-4c2b-a84c-467e2d36c97c'
def decode(b):
 assert b[:4]==b'\x07\0\0\0'
 d=bytearray(b[4:]);assert d[:8]==b'KSTRLOG1' and 80<=len(d)<=1024
 ver,slot,n,crc=struct.unpack_from('<IIII',d,8);assert ver==1 and slot<4 and len(d)==80+n
 d[20:24]=bytes(4);assert zlib.crc32(d)==crc
 return {'slot':slot,'boot_id':bytes(d[32:68]).decode(),'reason':bytes(d[68:80]).rstrip(b'\0').decode(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def boot(label,flags,crash=False):
 cfg=OUT/(label+'.cfg')
 cfg.write_text('set timeout=1\nset default=0\nterminal_output console\nmenuentry "Checkpoint validation '+label+'" {\n linux /EFI/Linux/kestrel-live.efi archisobasedir=arch archisolabel=KESTREL_A64 copytoram=n cow_spacesize=512M console=ttyAMA0,115200 loglevel=7 panic=0 init=/usr/bin/bash '+flags+'\n boot\n}\n')
 subprocess.run(['mcopy','-o','-i',FS,str(cfg),'::/boot/grub/grub.cfg'],check=True)
 cmd=['qemu-system-aarch64','-M','virt,gic-version=3','-cpu','cortex-a53','-accel','tcg','-m','2048','-smp','2',
 '-drive','if=pflash,format=raw,unit=0,readonly=on,file='+str(CODE),'-drive','if=pflash,format=raw,unit=1,file='+str(VARS),
 '-device','qemu-xhci','-drive','if=none,id=stick,format=raw,file='+str(IMAGE),'-device','usb-storage,drive=stick','-nographic','-no-reboot','-monitor','none']
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
 output=b''; sent=False; done=False; start=time.monotonic()
 with (OUT/(label+'.log')).open('wb') as log:
  try:
   while time.monotonic()-start<240 and proc.poll() is None:
    if not select.select([proc.stdout],[],[],1)[0]:continue
    chunk=os.read(proc.stdout.fileno(),65536)
    if not chunk:break
    output+=chunk;log.write(chunk);log.flush()
    if not sent and (b'no job control' in output or b'bash-' in output[-1024:]):
     shell="printf '\\nKST_ROOT_OK\\n'; mount -t efivarfs efivarfs /sys/firmware/efi/efivars 2>/dev/null; cat /run/kestrel-capture/checkpoint-status.log 2>/dev/null; for f in /sys/firmware/efi/efivars/KestrelBoot*-"+GUID+"; do [ -f \"$f\" ] || continue; printf 'KSTVAR|%s|' \"${f##*/}\"; base64 -w0 \"$f\"; printf '\\n'; done; printf '\\nKST_DONE\\n'\n"
     proc.stdin.write(shell.encode());proc.stdin.flush();sent=True
    if re.search(rb'^KST_DONE\r?$',output,re.M):done=True;break
   if done and not crash:
    proc.stdin.write(b'/usr/bin/systemctl poweroff --force --force\n');proc.stdin.flush()
    try:extra=proc.communicate(timeout=30)[0];output+=extra;log.write(extra)
    except subprocess.TimeoutExpired:pass
  finally:
   if proc.poll() is None:proc.kill();proc.wait(timeout=20)
 assert done, f'{label}: did not reach verified root-shell probe; inspect {OUT/(label+".log")}'
 assert b'Kernel panic' not in output
 records={}
 for name,data in re.findall(rb'^KSTVAR\|([^|\r\n]+)\|([A-Za-z0-9+/=]+)\r?$',output,re.M):
  b=base64.b64decode(data,validate=True);decode(b);records[name.decode()]=b
  (OUT/(label+'-'+name.decode()+'.bin')).write_bytes(b)
 return {'label':label,'seconds':round(time.monotonic()-start,2),'forced_process_kill':crash,'records':{k:decode(v) for k,v in records.items()}},records
results=[]
r,off=boot('off','');results.append(r);assert not off,'Flag OFF created checkpoint records'
r,on=boot('on','kestrel_log=1 kestrel_efilog=1',True);results.append(r);assert len(on)>=2,'No startup/final firmware checkpoints'
r,after=boot('recovery-off','');results.append(r);assert on==after,'Records changed/lost after abrupt VM termination'
r,refused=boot('existing-evidence','kestrel_log=1 kestrel_efilog=1');results.append(r);assert on==refused,'Existing evidence overwritten'
summary={'passed':True,'revision':REV,'uki_sha256':hashlib.sha256(UKI.read_bytes()).hexdigest(),'results':results,'hardware_validated':False,'persistence_verified':True}
(T/(TAG+'-result.json')).write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
