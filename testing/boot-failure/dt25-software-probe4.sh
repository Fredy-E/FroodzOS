#!/bin/bash
set -u
KSRC=/home/builder/src/ksrc
out=/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25-software-inventory4.txt
{
echo "==FULL DRM CONFIG=="
grep -E "SIMPLEDRM|SIMPLEFB|SYSFB|FBDEV|MSM|MDSS|DPU|GEM" "$KSRC/.config" 2>&1 | head -n 60
echo "==CMDLINE BLACKLISTS in DT?=="
grep -r -n "dispcc|blacklist|modprobe" /mnt/d/CachyOS-ARM64/builder/*.sh /mnt/d/CachyOS-ARM64/builder/*.py 2>&1 | head -n 60
echo "==DT status gpu mdss dispcc=="
python3 -c "
import subprocess
K='/home/builder/src/ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb'
def fdt(node,prop=None,kind='s',listing=None):
    c=['fdtget']
    if listing: c+=[listing,K,node]
    else: c+=['-t',kind,K,node,prop]
    r=subprocess.run(c,capture_output=True,text=True)
    return r.stdout.strip() if r.returncode==0 else 'ERR:'+r.stderr.strip()[:200]
for n in ['/soc@0/display-subsystem@aa00000','/soc@0/gpu@3d60000','/soc@0/clock-controller@af00000','/__symbols__']:
    print('NODE',n, fdt(n,listing='-p')[:1000])
" 2>&1 | head -n 80
echo "==TASKSET SYSTEMD-RUN TIMEOUT=="
for b in taskset systemd-run timeout nice ionice chrt; do ls -l "/home/builder/imgroot/usr/bin/$b" 2>&1; done
echo "==SDDM perms=="
ls -l /home/builder/imgroot/etc/sddm.conf.d/ 2>&1
cat /home/builder/imgroot/etc/sddm.conf.d/autologin.conf 2>&1
echo "==CHECK simpledrm in Image strings=="
strings /home/builder/src/ksrc/arch/arm64/boot/Image 2>/dev/null | grep -i -E "simpledrm|simple-framebuffer" | head -n 10 || true
echo DONE4
} > "$out" 2>&1
cat "$out" 2>&1 | head -n 20
