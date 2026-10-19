from pathlib import Path
import subprocess
P=Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
for name in ['/usr/lib/initcpio/install/base','/usr/lib/initcpio/init_functions']:
    p=Path(name)
    lines=p.read_text().splitlines()
    if name.endswith('/base'):
        print('\nFILE',name,'\n'+'\n'.join(lines))
    else:
        starts=[i for i,line in enumerate(lines) if any(line.startswith(x+'()') for x in ['run_hookfunctions','mount_setup','rdlogger_start','rdlogger_stop'])]
        for i in starts:
            end=next((j+1 for j in range(i+1,len(lines)) if lines[j]=='}'),len(lines))
            print('\nFUNCTION '+lines[i]+'\n'+'\n'.join(lines[i:end]))
for cmd in [['/usr/lib/initcpio/busybox','--list'],['/usr/bin/dmesg','--help'],['/usr/bin/blkid','--help']]:
    r=subprocess.run(cmd,capture_output=True,text=True)
    print('\nCOMMAND',cmd,'EXIT',r.returncode,'\n'+r.stdout+r.stderr)
