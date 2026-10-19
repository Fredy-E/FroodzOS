#!/usr/bin/env python3
"""Fail closed if initramfs PID 1 or WSL helper exclusion is wrong."""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
from platform_usb_gate import check_platform_usb
from platform_input_gate import check_platform_input
from platform_graphics_gate import check_platform_graphics

parser=argparse.ArgumentParser()
parser.add_argument('image',type=Path)
parser.add_argument('--require-local-firmware',action='store_true')
parser.add_argument('--require-log-capture',action='store_true')
parser.add_argument('--require-platform-usb',action='store_true')
parser.add_argument('--require-platform-input',action='store_true')
parser.add_argument('--require-graphics',action='store_true')
args=parser.parse_args()
base=Path('/home/builder/boot-failure-tests')
base.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='validate-',dir=base) as tmp:
    dest=Path(tmp)
    proc=subprocess.run(['lsinitcpio','-x',str(args.image.resolve())],cwd=dest,capture_output=True,text=True)
    if proc.returncode: raise SystemExit(proc.stdout+proc.stderr)
    data=(dest/'init').read_bytes()
    expected=Path('/usr/lib/initcpio/init').read_bytes()
    checks={
        'pid1_matches_mkinitcpio_script':data==expected,
        'pid1_has_ash_shebang':data.startswith(b'#!/usr/bin/ash\n'),
        'no_mount_drvfs':not (dest/'usr/bin/mount.drvfs').is_symlink() and not (dest/'usr/bin/mount.drvfs').exists(),
        'no_mount_wslfs':not (dest/'usr/bin/mount.wslfs').is_symlink() and not (dest/'usr/bin/mount.wslfs').exists(),
        'archiso_hook_present':(dest/'hooks/archiso').is_file(),
        'archiso_label_helper_present':(dest/'usr/bin/blkid').exists(),
        'fat_default_charset_module_present':bool(list(dest.rglob('nls_iso8859-1.ko*'))),
        'utf8_charset_module_present':bool(list(dest.rglob('nls_utf8.ko*'))),
    }
    if args.require_platform_usb:
        checks.update(check_platform_usb(dest))
    if args.require_platform_input:
        checks.update(check_platform_input(dest))
    if args.require_graphics:
        checks.update(check_platform_graphics(dest))
    if args.require_local_firmware:
        fw=dest/'usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3'
        names=['qcadsp8380.mbn','qccdsp8380.mbn','qcdxkmsucpurwa.mbn','adsp_dtbs.elf','cdsp_dtbs.elf']
        checks['board_firmware_present']=all((fw/name).is_file() for name in names)
    if args.require_log_capture:
        hook=dest/'hooks/kestrel_log'
        hook_text=hook.read_text() if hook.is_file() else ''
        checks['log_runtime_hook_present']=hook.is_file() and 'run_latehook' in hook_text and 'run_cleanuphook' in hook_text and 'run_earlyhook' not in hook_text
        checks['log_streamer_present']=bool(list(dest.rglob('usr/bin/kestrel-kmsg')))
        checks['log_init_script_present']=(dest/'usr/bin/kestrel-init-log').is_file()
        checks['log_root_script_present']=(dest/'usr/bin/kestrel-root-log').is_file()
        checks['log_service_present']=(dest/'etc/kestrel-usb-log.service').is_file()
        checks['early_checkpoint_binary']=(dest/'usr/bin/kestrel-checkpoint').is_file()
        checks['no_unbounded_firmware_loop']=not (dest/'usr/bin/kestrel-efilog-loop').exists()
        early=(dest/'hooks/kestrel_efilog').read_text()
        checks['early_capture_lifecycle']='run_earlyhook' in early and 'stop-early' in early
        binary=(dest/'usr/bin/kestrel-checkpoint').read_bytes()
        checks['checkpoint_owned_namespace']=b'674b8af1-da8e-4c2b-a84c-467e2d36c97c' in binary
    print(json.dumps({'image':str(args.image),'init_sha256':hashlib.sha256(data).hexdigest(),'checks':checks,'passed':all(checks.values())},indent=2))
    raise SystemExit(0 if all(checks.values()) else 1)
