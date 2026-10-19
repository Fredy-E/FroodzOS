import os,signal,json
from pathlib import Path
needle='if=none,id=stick,format=raw,file=/home/builder/boot-failure-tests/qemu-dt24-menu8-text-fw-off-v1.fat'
found=[]
for entry in Path('/proc').iterdir():
 if not entry.name.isdecimal():continue
 try:
  if not (entry/'comm').read_text().startswith('qemu-system'):continue
  argv=(entry/'cmdline').read_bytes().split(b'\0')
  if needle.encode() in argv:found.append(int(entry.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert len(found)<=1,found
for pid in found:os.kill(pid,signal.SIGTERM)
print('STOPPED_ONLY_V1_TEST_VM',found)
p=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/dt24-text-v1-harness-correction.json')
with p.open('x') as f:json.dump({'reason':'The harness matched the menu instruction containing the prompt and sent before getty opened the TTY. Candidate reached normal systemd/getty and actual interactive Bash; rerun with anchored real-prompt predicate. Quiet kernel banner must be checked in captured kmsg, not serial.','v1_not_accepted':True,'stopped_vm_pids':found},f,indent=2)
