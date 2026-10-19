#!/usr/bin/env python3
"""Read-only frozen kernel/SFS USB networking prerequisites; no extraction."""
import datetime, fcntl, hashlib, json, shutil, subprocess
from pathlib import Path
P = Path('/mnt/d/CachyOS-ARM64')
T = P/'testing/boot-failure'
K = Path('/home/builder/src/ksrc')
SFS = Path('/home/builder/live-rootfs-v2.squashfs')
tag = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out = T/('native-network-prereqs-'+tag+'.json')
with out.open('x') as receipt:
    with Path('/home/builder/boot-failure-tests/dt25-build.lock').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = (K/'.config').read_text()
        release = (K/'include/config/kernel.release').read_text().strip()
        wanted = ['CONFIG_USB_RTL8152', 'CONFIG_USB_USBNET', 'CONFIG_USB_NET_AX8817X', 'CONFIG_USB_NET_AX88179_178A', 'CONFIG_USB_NET_CDCETHER', 'CONFIG_USB_NET_CDC_NCM', 'CONFIG_USB_NET_RNDIS_HOST', 'CONFIG_USB_NET_CDC_MBIM', 'CONFIG_USB_IPHETH']
        states = {k: next((ln.split('=',1)[1] for ln in config.splitlines() if ln.startswith(k+'=')), 'not set') for k in wanted}
        listing = subprocess.run(['unsquashfs','-ll',str(SFS)],capture_output=True,text=True,check=True,timeout=120).stdout
        # Symlink listings end with '-> target'; inspect the path, not target.
        paths = [ln.split('squashfs-root/',1)[1].split(' -> ',1)[0] for ln in listing.splitlines() if 'squashfs-root/' in ln]
        module_names = ['r8152','usbnet','asix','ax88179_178a','cdc_ether','cdc_ncm','rndis_host','cdc_mbim','ipheth','mii']
        modules = {m:[p for p in paths if 'usr/lib/modules/'+release+'/' in p and p.split('/')[-1].startswith(m+'.ko')] for m in module_names}
        tools = {name:('usr/bin/'+name in paths) for name in ['python3','nmcli','curl','ip','getent','sudo','git','timeout']}
        result = {'scope':'read-only kernel config and frozen-SFS file listing; no native network test', 'kernel_release':release,'kernel_config_sha256':hashlib.sha256(config.encode()).hexdigest(),'kernel_config':states,'sfs_modules':modules,'sfs_tools':tools,'d_free_bytes':shutil.disk_usage('/mnt/d').free,'native_network_proven':False,'ethernet_adapter_model_unknown':True,'notes':['Module presence is not successful link/DHCP/DNS/TLS.','No kernel/DTB/image edits; no internal storage or USB writes.']}
        json.dump(result,receipt,indent=2)
print(out)
print(json.dumps(result,indent=2))
