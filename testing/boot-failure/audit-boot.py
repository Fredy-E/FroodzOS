#!/usr/bin/env python3
"""Read-only boot-chain inspection; no writes to images or targets."""
import hashlib, json, re, subprocess
from pathlib import Path

ROOT = Path('/home/builder')
STUB = ROOT / 'src/stubble-9f11278e080a5c4a77db6acf4c8f75c14412087a'
K = ROOT / 'src/ksrc'

def run(args, limit=14000):
    print('\nCOMMAND', ' '.join(map(str, args)))
    result = subprocess.run(list(map(str,args)), capture_output=True, text=True, errors='replace')
    print('EXIT',result.returncode)
    text = result.stdout + result.stderr
    print(text[:limit])

def show(path):
    path=Path(path)
    print('\nFILE', path)
    print(path.read_text(errors='replace') if path.exists() else 'MISSING')

run(['uname','-a'])
run(['df','-h','/home/builder','/mnt/d'])
for name in ['Image','Image.gz']:
    path=K/'arch/arm64/boot'/name
    if path.exists():
        print('KERNEL',path,'bytes',path.stat().st_size)
        run(['file',path])
show(K/'include/config/kernel.release')
config=(K/'.config').read_text()
for line in config.splitlines():
    if re.match(r'(?:# )?CONFIG_(?:EFI|EFI_STUB|EFI_GENERIC_STUB_INITRD_CMDLINE_LOADER|ARM64|ARCH_QCOM|ACPI|SERIAL_AMBA_PL011|SERIAL_AMBA_PL011_CONSOLE|FB_EFI|DRM_SIMPLEDRM|DRM_MSM|QCOM_SCM|QCOM_WDT|WATCHDOG|USB_XHCI_HCD|USB_XHCI_PLATFORM|USB_DWC3|USB_DWC3_QCOM|BLK_DEV_LOOP|SQUASHFS|OVERLAY_FS|PANIC_TIMEOUT|CMDLINE.*|ARM64_VA_BITS.*|ARM64_PAGE_SHIFT|ARM64_.*PAGES|IKCONFIG.*)(?:=| )',line):
        print(line)
show(ROOT/'uki/live-mkinitcpio.conf')
show(ROOT/'uki/live-cmdline')
show(STUB/'hwids/json/x126100-lenovo-ideapad-slim3.json')
run(['python3',STUB/'stubblify','inspect',ROOT/'uki/vmlinuz-live.efi'],22000)
run(['file',STUB/'stubble.efi',ROOT/'uki/vmlinuz-live.efi'])
run(['lsinitcpio','-a',ROOT/'uki/live-initramfs.img'],16000)
result=subprocess.run(['lsinitcpio','-l',str(ROOT/'uki/live-initramfs.img')],capture_output=True,text=True)
lines=result.stdout.splitlines()
print('\nINITRAMFS LIST exit',result.returncode,'entries',len(lines))
for line in lines:
    if re.search(r'(^init$|archiso|qcom/|qcadsp|qccdsp|qcdx|adsp_dtbs|cdsp_dtbs|dwc3|xhci|usb-storage|uas\.ko|overlay\.ko|squashfs\.ko|hwids)',line):
        print(line)
for path in ['/usr/lib/initcpio/hooks/archiso','/usr/lib/initcpio/install/archiso','/usr/lib/initcpio/init']:
    show(path)
run(['pacman','-Q','mkinitcpio','mkinitcpio-archiso','qemu-system-aarch64','edk2-armvirt'],4000)
print('\nSTUB SOURCE FILES')
print('\n'.join(str(p.relative_to(STUB)) for p in STUB.rglob('*') if p.is_file() and p.suffix in ['.c','.h'] and not any(x in p.parts for x in ['.git','build'])))
