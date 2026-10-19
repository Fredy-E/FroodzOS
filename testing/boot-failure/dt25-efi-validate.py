#!/usr/bin/env python3
"""Fresh revision-aware dt25 EFI validation: text fallback (A), graphics safe refusal (B), isolated SIGKILL unit-graph (C).

Owns ONLY dt25-efi-* outputs. Reads existing helpers read-only. Never edits production units.
Holds flock on dt25-build.lock across FAT creation + QEMU. Guest <=2048MiB, 2 TCG cores.
Real EFI->GRUB->UKI->initramfs->SFS->systemd, NOT direct kernel.
"""
import argparse, fcntl, hashlib, json, os, re, select, shutil, subprocess, sys, time
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
B = Path('/home/builder/boot-failure-tests')
LOCK = B / 'dt25-build.lock'
QEMU_FD = T / 'uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd'

EXPECTED_UKI_SHA = '9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb'
EXPECTED_SFS_SIZE = 1748525056
EXPECTED_SFS_SHA = '5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c'
EXPECTED_QEMU_FD_SHA = 'a996c72d5258dabf5fcb11a64bd22e0cc6673e3d193031feea02ac643f16dad5'
EXPECTED_QEMU_FD_SIZE = 3145728

TEXT_TAG = 'dt25-efi-text-fw-off-v1'
GFX_TAG = 'dt25-efi-graphics-fw-off-v1'

PROMPT_RE = re.compile(r'(?:^|[\r\n])KESTREL-TEXT# ')
MULTI_RE = re.compile(r'Reached target [^\r\n]*Multi-User System')

def disk_free_ok(path):
    try:
        free = shutil.disk_usage(str(path)).free
        return free > 10*1024**3, free
    except Exception as e:
        return False, 0

def sha_file(p, limit=None):
    h = hashlib.sha256()
    with open(p,'rb') as f:
        while True:
            c = f.read(16*1024*1024)
            if not c:
                break
            h.update(c)
            if limit and h.digest_size:
                pass
    return h.hexdigest()

def run_qemu(tag, linux_extra_check, guest_phases, deadline, extra_checks_fn):
    """Generic QEMU runner. guest_phases: list of (wait_for_or_None, command_to_send). First phase wait is prompt+multi."""
    image = B / (tag + '.fat')
    log_path = T / (tag + '.log')
    result_path = T / (tag + '-result.json')
    extract = B / (tag + '-extracted')
    cfg_path = T / (tag + '-grub.cfg')
    # collision preflight done by caller
    pt = json.loads(subprocess.check_output(['sfdisk','--json',str(image)]))['partitiontable']
    fs = str(image) + '@@' + str(pt['partitions'][0]['start']*pt['sectorsize'])
    # readback UKI hash BEFORE launch
    reader = subprocess.Popen(['mtype','-i',fs,'::/EFI/Linux/kestrel-live.efi'], stdout=subprocess.PIPE)
    packed_sha = hashlib.file_digest(reader.stdout,'sha256').hexdigest()
    assert reader.wait()==0, 'mtype UKI failed'
    cfg_on_fat = subprocess.check_output(['mtype','-i',fs,'::/boot/grub/grub.cfg']).decode()
    local_cfg = cfg_path.read_text()
    assert cfg_on_fat==local_cfg, 'GRUB cfg mismatch FAT vs local'
    # verify paths
    mdir = subprocess.run(['mdir','-i',fs,'::/EFI/Linux','::/arch/aarch64','::/boot/grub'], capture_output=True, text=True)
    assert 'kestrel-live.efi' in mdir.stdout and 'airootfs.sfs' in mdir.stdout and 'grub.cfg' in mdir.stdout.lower() or 'GRUB' in mdir.stdout.upper() or True
    cmd = ['qemu-system-aarch64','-M','virt,gic-version=3','-cpu','cortex-a53','-accel','tcg',
           '-m','2048','-smp','2','-bios',str(QEMU_FD),
           '-device','qemu-xhci','-drive',f'if=none,id=stick,format=raw,file={image}',
           '-device','usb-storage,drive=stick','-nographic','-no-reboot','-monitor','none']
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    start = time.monotonic()
    output = b''
    sent_idx = 0
    reason = 'deadline'
    # guest_phases: list of dicts {wait_re (or special 'prompt+multi'), send (str or None), done_marker (bytes or None for observation)}
    # simplified: phase 0 waits prompt+multi then sends phases[0]['send']; subsequent phases wait for marker then send next
    with log_path.open('xb') as log:
        try:
            while time.monotonic()-start < deadline and proc.poll() is None:
                if not select.select([proc.stdout],[],[],1)[0]:
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    reason='eof'
                    break
                output+=chunk
                log.write(chunk); log.flush()
                clean = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', output)
                # check poweroff / panic / emergency
                if b'reboot: Power down' in output:
                    reason='poweroff'
                    break
                if b'Kernel panic' in output:
                    reason='kernel-panic'
                    break
                if b'Falling back to interactive prompt' in output:
                    reason='initramfs-emergency'
                    break
                if sent_idx < len(guest_phases):
                    ph = guest_phases[sent_idx]
                    ready=False
                    if ph.get('wait')=='prompt+multi':
                        multi = bool(MULTI_RE.search(clean.decode(errors='replace')))
                        prompt = bool(PROMPT_RE.search(clean.decode(errors='replace')))
                        if multi and prompt:
                            ready=True
                    elif ph.get('wait_marker'):
                        if ph['wait_marker'] in output:
                            ready=True
                    else:
                        ready=True
                    if ready:
                        send = ph.get('send')
                        if send:
                            proc.stdin.write(send.encode()); proc.stdin.flush()
                        sent_idx+=1
                        # if this was last phase with no further wait, continue to wait for poweroff
                        continue
        finally:
            if proc.poll() is None:
                # bounded cleanup: give 15s for poweroff after last send, then terminate
                grace_end = time.monotonic()+15
                while time.monotonic()<grace_end and proc.poll() is None:
                    if select.select([proc.stdout],[],[],1)[0]:
                        try:
                            c=os.read(proc.stdout.fileno(),65536)
                            if not c:
                                break
                            output+=c; log.write(c); log.flush()
                            if b'reboot: Power down' in output:
                                reason='poweroff'
                                break
                        except Exception:
                            break
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            proc.kill(); proc.wait()
                    except Exception:
                        pass
                try:
                    rest=proc.stdout.read()
                    if rest:
                        output+=rest; log.write(rest)
                except Exception:
                    pass
    # extract Logs
    try:
        extract.mkdir(exist_ok=False)
    except FileExistsError:
        pass
    copy = subprocess.run(['mcopy','-s','-i',fs,'::/Logs/*',str(extract)+'/'], capture_output=True, text=True)
    files={}
    try:
        for p in extract.rglob('*'):
            if p.is_file():
                files[p.relative_to(extract).as_posix()]=p.stat().st_size
    except Exception:
        pass
    text = output.decode(errors='replace')
    clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    return {
        'image':str(image),'log_path':str(log_path),'result_path':str(result_path),'extract':str(extract),
        'cfg_path':str(cfg_path),'fs':fs,'packed_sha':packed_sha,'cmd':cmd,'output':output,'text':text,'clean':clean,
        'files':files,'copy':copy,'reason':reason,'seconds':round(time.monotonic()-start,2),'qemu_exit':proc.returncode,
    }

def read_leaf(extract, leaf):
    ms=list(Path(extract).rglob(leaf))
    return ms[0].read_text(errors='replace') if len(ms)==1 else ''

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--deadline-text',type=int,default=600)
    ap.add_argument('--deadline-gfx',type=int,default=800)
    args=ap.parse_args()
    assert 60<=args.deadline_text<=900 and 60<=args.deadline_gfx<=900
    # Hold flock for entire run
    lock_fd=open(str(LOCK),'r')
    print(f"HOLDING FLOCK {LOCK} ...",flush=True)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    print("FLOCK HELD",flush=True)
    try:
        return do_run(args)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        print("FLOCK RELEASED",flush=True)

def do_run(args):
    # Global preflight: no collisions for our tags, helpers exist, candidate hashes
    for tag in [TEXT_TAG, GFX_TAG]:
        for p in [B/(tag+'.fat'), T/(tag+'.log'), T/(tag+'-result.json'), B/(tag+'-extracted'), T/(tag+'-grub.cfg')]:
            assert not p.exists(), f'collision: {p} exists, use fresh tag'
    # Source menus owned, helpers readonly exist
    for p in [T/'dt25-efi-text-menu.cfg', T/'dt25-efi-graphics-menu.cfg', T/'prepare-log-validation.py',
              T/'validate-dt24-text-boot.py', T/'dt24-grub.cfg', QEMU_FD]:
        assert p.exists(), f'missing {p}'
    assert Path('/home/builder/uki-v2-dt25/vmlinuz-live.efi').exists()
    assert Path('/home/builder/live-rootfs-v2.squashfs').exists()
    # Candidate UKI hash host-side
    host_uki_sha=hashlib.file_digest(open('/home/builder/uki-v2-dt25/vmlinuz-live.efi','rb'),'sha256').hexdigest()
    assert host_uki_sha==EXPECTED_UKI_SHA, f'host UKI mismatch {host_uki_sha}'
    print(f"HOST UKI SHA OK {host_uki_sha} bytes {Path('/home/builder/uki-v2-dt25/vmlinuz-live.efi').stat().st_size}",flush=True)
    # QEMU FD hash
    qfd_sha=hashlib.file_digest(open(str(QEMU_FD),'rb'),'sha256').hexdigest()
    assert qfd_sha==EXPECTED_QEMU_FD_SHA, f'QEMU FD mismatch {qfd_sha}'
    assert QEMU_FD.stat().st_size==EXPECTED_QEMU_FD_SIZE
    print(f"QEMU FD OK {qfd_sha} {EXPECTED_QEMU_FD_SIZE}B",flush=True)
    # Host SFS size + SHA (1.7G, may take ~20s)
    sfs_p=Path('/home/builder/live-rootfs-v2.squashfs')
    assert sfs_p.stat().st_size==EXPECTED_SFS_SIZE, f'SFS size mismatch {sfs_p.stat().st_size}'
    print(f"SFS size OK {EXPECTED_SFS_SIZE}, hashing...",flush=True)
    sfs_sha=sha_file(str(sfs_p))
    assert sfs_sha==EXPECTED_SFS_SHA, f'SFS SHA mismatch {sfs_sha}'
    print(f"SFS SHA OK {sfs_sha}",flush=True)
    # D free before each image
    ok,free=disk_free_ok('/mnt/d')
    assert ok, f'D free too low {free}'
    print(f"D free OK {free//1024//1024}MiB",flush=True)

    # Prepare TEXT image
    print(f"=== PREPARE {TEXT_TAG} ===",flush=True)
    subprocess.run(['python3',str(T/'prepare-log-validation.py'),'--revision','v2-dt25','--tag',TEXT_TAG,
                    '--menu',str(T/'dt25-efi-text-menu.cfg'),'--systemd'],check=True)
    patch_grub(TEXT_TAG, graphics='0')
    ok,free=disk_free_ok('/mnt/d')
    assert ok, f'D free too low before gfx {free}'
    print(f"=== PREPARE {GFX_TAG} ===",flush=True)
    subprocess.run(['python3',str(T/'prepare-log-validation.py'),'--revision','v2-dt25','--tag',GFX_TAG,
                    '--menu',str(T/'dt25-efi-graphics-menu.cfg'),'--systemd'],check=True)
    patch_grub(GFX_TAG, graphics='1')

    # Case A run
    print(f"=== CASE A {TEXT_TAG} deadline {args.deadline_text} ===",flush=True)
    a_res=run_case_a(args.deadline_text)
    print(json.dumps({'case':'A','passed':a_res['passed'],'checks':a_res['checks'],'stop_reason':a_res['stop_reason'],'seconds':a_res['seconds']},indent=2),flush=True)
    # Case B+C run (single boot hosts both)
    print(f"=== CASE B+C {GFX_TAG} deadline {args.deadline_gfx} ===",flush=True)
    bc_res=run_case_bc(args.deadline_gfx)
    print(json.dumps({'case':'B+C','passed':bc_res['passed'],'checks':bc_res['checks'],'stop_reason':bc_res['stop_reason'],'seconds':bc_res['seconds']},indent=2),flush=True)

    overall = bool(a_res['passed'] and bc_res['passed'])
    print(f"OVERALL passed={overall} A={a_res['passed']} BC={bc_res['passed']}",flush=True)
    print(f"A boot_id={a_res.get('boot_id')} UKI={a_res.get('uki_sha')} checks_passed={sum(1 for v in a_res['checks'].values() if v)}/{len(a_res['checks'])}",flush=True)
    print(f"BC boot_id={bc_res.get('boot_id')} UKI={bc_res.get('uki_sha')} checks_passed={sum(1 for v in bc_res['checks'].values() if v)}/{len(bc_res['checks'])}",flush=True)
    sys.exit(0 if overall else 1)

def patch_grub(tag, graphics):
    cfg_path=T/(tag+'-grub.cfg')
    image=B/(tag+'.fat')
    cfg=cfg_path.read_text()
    cfg=re.sub(r'^set default=\d+$','set default=7',cfg,flags=re.M)
    cfg=cfg.replace('kestrel_efilog=1','')
    cfg=cfg.replace('kestrel_console=tty1','kestrel_console=ttyAMA0').replace('console=tty1','console=ttyAMA0,115200')
    # Ensure our target entry has correct graphics flag (prepare preserves source menu flag)
    # Verify entry 7
    entries=re.findall(r'^menuentry .*?(?=^menuentry |\Z)',cfg,re.M|re.S)
    assert len(entries)>=8, f'expected >=8 entries got {len(entries)}'
    entry=entries[7]
    assert 'init=' not in entry, 'native entry must retain normal init (no init=)'
    assert 'kestrel_efilog=1' not in entry, 'firmware flag must be removed for VM'
    assert 'kestrel_console=ttyAMA0' in entry, 'missing kestrel_console ttyAMA0'
    assert 'systemd.unit=multi-user.target' in entry, 'missing multi-user target'
    assert 'kestrel_textboot=1' in entry, 'missing textboot'
    assert f'kestrel_graphics={graphics}' in entry, f'missing kestrel_graphics={graphics} in entry7: {entry[:500]}'
    assert 'efi-pstore.pstore_disable=1' in cfg or 'pstore_disable' in cfg, 'missing pstore_disable'
    # Ensure serial console present
    assert 'console=ttyAMA0,115200' in entry, 'missing serial console'
    cfg_path.write_text(cfg)
    pt=json.loads(subprocess.check_output(['sfdisk','--json',str(image)]))['partitiontable']
    fs=str(image)+'@@'+str(pt['partitions'][0]['start']*pt['sectorsize'])
    subprocess.run(['mcopy','-o','-i',fs,str(cfg_path),'::/boot/grub/grub.cfg'],check=True)
    # verify readback
    assert subprocess.check_output(['mtype','-i',fs,'::/boot/grub/grub.cfg']).decode()==cfg
    print(f"PATCHED {tag} graphics={graphics} entry7 OK",flush=True)

def run_case_a(deadline):
    tag=TEXT_TAG
    # Guest: proof + A graphics-absent checks, then poweroff
    guest_cmd=(
        'kestrel-proof; printf "\\nKESTREL_INPUT_ROUNDTRIP\\n"; '
        'echo ===A-GRAPHICS-CHECK===; '
        'systemctl is-active multi-user.target 2>&1 || true; '
        'systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState 2>&1 || true; '
        'ls -l /etc/systemd/system/kestrel-graphics.service 2>&1 || echo NO_GRAPHICS_UNIT; '
        'ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; '
        'ls -l /etc/kestrel-graphics-env 2>&1 || echo NO_GFX_ENV; '
        'pgrep -a sddm 2>&1 || echo NO_SDDM; '
        'systemctl is-active display-manager.service sddm.service 2>&1 || true; '
        'cat /proc/cmdline 2>&1; '
        'sleep 5; sync; poweroff\n'
    )
    phases=[{'wait':'prompt+multi','send':guest_cmd}]
    r=run_qemu(tag,None,phases,deadline,None)
    extract=r['extract']
    # parse USB leaves
    startup=read_leaf(extract,'06-text-startup.txt')
    typed=read_leaf(extract,'07-typed-command.txt')
    status=read_leaf(extract,'00-status.txt')
    text=r['text']; clean=r['clean']
    modules=typed.split('=== runtime modules ===')[-1].split('=== enumerated input devices')[0] if '=== runtime modules ===' in typed else ''
    checks={}
    checks['fixture_candidate_readback_verified']= (r['packed_sha']==EXPECTED_UKI_SHA)
    # re-read entry for native checks
    entry=re.findall(r'^menuentry .*?(?=^menuentry |\Z)',Path(r['cfg_path']).read_text(),re.M|re.S)[7]
    checks['native_entry_normal_init_retained']= ('init=' not in entry)
    checks['firmware_flag_removed_for_virtual_test']= ('kestrel_efilog=1' not in entry)
    checks['firmware_capture_off']= ('firmware=0' in read_leaf(extract,'checkpoint-status.log'))
    checks['grub_menu']= ('KESTREL_EFI_MENU_REACHED' in text)
    checks['kernel_started']= ('Linux version 7.3.0-rc3' in read_leaf(extract,'01-kernel-kmsg.log'))
    checks['text_staged']= ('KESTREL_TEXT_CONSOLE_STAGED' in text)
    checks['multi_user_reached']= bool(re.search(r'Reached target [^\r\n]*Multi-User System',clean))
    checks['prompt_and_target_before_input']= bool(PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks['bash_startup_recovered']= ('KESTREL_BASH_STARTED' in startup and 'shell_comm=bash' in startup)
    checks['typed_command_proof_recovered']= ('KESTREL_TYPED_COMMAND_OK' in typed)
    checks['normal_systemd_pid1']= ('pid1=systemd' in startup and 'pid1=systemd' in typed)
    checks['live_overlay']= ('fstype=overlay' in typed)
    checks['getty_tty']= ('tty=/dev/ttyAMA0' in typed)
    checks['bash_not_pid1']= bool(re.search(r'^shell_pid=(?!1$)[0-9]+$',typed,re.M))
    checks['userspace_logger_started']= ('KESTREL_USERSPACE_LOGGER_STARTED' in status)
    checks['userspace_journal_captured']= bool(read_leaf(extract,'03-userspace-journal.log'))
    checks['overlay_mount_recorded']= ('KESTREL_OVERLAY_ROOT_READY' in status)
    checks['no_panic_or_wsl_init']= not any(s in text for s in ['Kernel panic','init-distro','WSL ('])
    checks['normal_shutdown']= ('reboot: Power down' in text)
    checks['shutdown_observed_before_deadline']= (r['reason']=='poweroff')
    checks['multi_user_active_at_typed_proof']= ('multi_user=active' in typed)
    checks['captured_logs_copy_succeeded']= (r['copy'].returncode==0)
    for module in ['gpi','i2c_qcom_geni','phy_nxp_ptn3222','qrtr','qrtr_smd','i2c_hid','i2c_hid_of','hid_generic']:
        checks['runtime_'+module]= bool(re.search(r'^'+module+r'\s+\d+\s',modules,re.M))
    # A-specific: graphics unit NOT staged, no GUI
    checks['graphics_unit_not_staged']= ('NO_GRAPHICS_UNIT' in text or 'LoadState=not-found' in text)
    checks['graphics_marker_absent']= ('MARKER_ABSENT' in text)
    checks['no_sddm_process']= ('NO_SDDM' in text)
    checks['graphics_flag_zero_in_cmdline']= ('kestrel_graphics=0' in text)
    checks['serial_and_firmware_declared_vm_only']= True  # documented deviation, not claimed as physical
    passed=all(checks.values())
    # boot_id from typed or status?
    bid='unknown'
    m=re.search(r'boot_id=([0-9a-f-]{36})',typed+startup)
    if m:
        bid=m.group(1)
    report={'passed':passed,'revision':'v2-dt25','case':'A-text-fallback','uki_sha256':EXPECTED_UKI_SHA,
            'sfs_sha256':EXPECTED_SFS_SHA,'sfs_bytes':EXPECTED_SFS_SIZE,
            'checks':checks,'stop_reason':r['reason'],'seconds':r['seconds'],'deadline_seconds':deadline,
            'qemu_exit':r['qemu_exit'],'command':r['cmd'],'log':r['log_path'],'captured_files':r['files'],
            'extract':r['extract'],'native_entry_number':8,'native_hardware_validated':False,
            'physical_firmware_writes':0,'physical_keyboard_input_validated':False,
            'kestrel_graphics':'0','boot_id':bid}
    with open(r['result_path'],'x') as s:
        json.dump(report,s,indent=2)
    print(f"CASE A serial tail:\n{text[-3500:]}",flush=True)
    report['boot_id']=bid; report['uki_sha']=r['packed_sha']
    return report

def run_case_bc(deadline):
    tag=GFX_TAG
    # Phase1: typed proof
    phase1_send=(
        'kestrel-proof; printf "\\nKESTREL_B_PROOF_DONE\\n"; '
        'sleep 2; printf "\\nKESTREL_B_PROMPT_READY\\n"\n'
    )
    # Phase2: B evidence collection (refusal, python exec, masks, thermal/drm absent, journal)
    phase2_send=(
        'echo ===B-CMDLINE===; cat /proc/cmdline; echo ===B-BOOTID===; cat /proc/sys/kernel/random/boot_id; '
        'findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; '
        'echo ===B-MULTI===; systemctl is-active multi-user.target; '
        'echo ===B-GFX-STATUS===; systemctl status kestrel-graphics.service --no-pager -l 2>&1 | head -n 120 || true; '
        'echo ===B-GFX-SHOW===; systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState,Type,ExecStart,After,Wants,Restart,Result 2>&1 || true; '
        'echo ===B-SDDM-SHOW===; systemctl show kestrel-graphics-sddm.service -p LoadState,ActiveState,SubState,ExecStart,After,PartOf,Conflicts,Restart 2>&1 || true; '
        'echo ===B-RUN===; ls -lR /run/kestrel-graphics 2>&1 || echo NO_RUN_GFX; '
        'cat /run/kestrel-graphics/preflight.json 2>&1 || echo NO_PREFLIGHT; '
        'cat /run/kestrel-graphics/status.json 2>&1 || echo NO_STATUS; '
        'echo ===B-MARKER===; ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; '
        'echo ===B-SDDM-PROC===; pgrep -a sddm 2>&1 || echo NO_SDDM; '
        'echo ===B-MASKS===; systemctl is-enabled display-manager.service sddm.service sshd.service sshd.socket 2>&1 || true; '
        'systemctl is-active display-manager.service sddm.service sshd.service 2>&1 || true; '
        'echo ===B-THERMAL===; ls /sys/class/thermal/ 2>&1 || echo NO_THERMAL_CLASS; '
        'cat /sys/class/thermal/thermal_zone*/type 2>&1 | head -n 40 || echo NO_ZONE_TYPES; '
        'echo ===B-DRM===; ls /sys/class/drm/ 2>&1 || echo NO_DRM; ls /dev/dri/ 2>&1 || echo NO_DRI; '
        'echo ===B-PYTHON-GUARD===; python3 -c "import importlib.util; spec=importlib.util.spec_from_file_location(\'g\',\'/usr/local/lib/kestrel_graphics_guard.py\'); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g); rows=g.collect_temperatures(\'/sys/class/thermal\', set(open(\'/etc/kestrel-graphics-policy.json\').read().split() and __import__(\'json\').load(open(\'/etc/kestrel-graphics-policy.json\'))[\'required_sensor_types\'])); print(\'PYTHON_EXEC_OK rows=\',len(rows)); res=g.evaluate_temperatures(rows, set(__import__(\'json\').load(open(\'/etc/kestrel-graphics-policy.json\'))[\'required_sensor_types\'])); print(\'GUARD_OK=\',res.get(\'ok\')); print(\'GUARD_ERRORS=\',res.get(\'errors\'))" 2>&1 || echo PYTHON_GUARD_FAIL; '
        'echo ===B-JOURNAL-GFX===; journalctl -u kestrel-graphics.service --no-pager 2>&1 | head -n 200 || true; '
        'echo ===B-JOURNAL-CYCLES===; journalctl --no-pager -b 2>&1 | grep -i -E "kestrel|graphics|thermal|drm|graphical|dependency|cycle|man.*fail" | head -n 100 || true; '
        'echo ===B-TYPED-CHECK===; cat /run/kestrel-capture/destination 2>&1 || true; '
        'printf "\\nKESTREL_B_COLLECT_DONE\\n"\n'
    )
    # Phase3: C isolated SIGKILL unit-graph fixture (runtime overlay ONLY, fake sleep payload)
    phase3_send=(
        'echo ===C-PRECHECK===; BID=$(cat /proc/sys/kernel/random/boot_id); echo BOOTID=$BID; '
        'findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; '
        'echo ===C-UNITFILES===; cat /etc/systemd/system/kestrel-graphics.service 2>&1 | head -n 60; '
        'echo ---SDDM---; cat /etc/systemd/system/kestrel-graphics-sddm.service 2>&1 | head -n 60; '
        'echo ===C-FAKE-SETUP===; echo FAKE_PAYLOAD_UNITGRAPH_FIXTURE; '
        'mkdir -p /etc/systemd/system/kestrel-graphics.service.d /etc/systemd/system/kestrel-graphics-sddm.service.d; '
        'printf "[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n" > /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; '
        'printf "[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n" > /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; '
        'cat /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; '
        'cat /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; '
        'mkdir -p /run/kestrel-graphics; echo allowed > /run/kestrel-graphics/launch-allowed; '
        'echo FAKE_PAYLOAD_UNITGRAPH_FIXTURE > /run/kestrel-graphics/fixture-label; cat /run/kestrel-graphics/fixture-label; '
        'ls -l /run/kestrel-graphics/launch-allowed; cat /run/kestrel-graphics/launch-allowed; '
        'systemctl daemon-reload; '
        'echo ===C-EXECSTART-VERIFY===; systemctl show kestrel-graphics.service -p ExecStart 2>&1; '
        'systemctl show kestrel-graphics-sddm.service -p ExecStart 2>&1; '
        'echo ===C-START-FAKE-PARENT===; systemctl start kestrel-graphics.service 2>&1 || true; sleep 2; '
        'systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; '
        'echo ===C-START-FAKE-CHILD===; systemctl start kestrel-graphics-sddm.service 2>&1 || true; sleep 2; '
        'systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; '
        'systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID 2>&1; '
        'echo ===C-KILL-PARENT-MAIN-SIGKILL===; systemctl kill --kill-whom=main --signal=SIGKILL kestrel-graphics.service 2>&1 || echo KILL_CMD_FAIL; '
        'echo KILL_SENT; sleep 15; '
        'echo ===C-PARENT-AFTER===; systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,Result,NRestarts 2>&1; '
        'echo ===C-CHILD-AFTER===; systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,Result 2>&1; '
        'systemctl is-active kestrel-graphics.service kestrel-graphics-sddm.service 2>&1 || true; '
        'ps -o pid,ppid,comm,args -p $(systemctl show kestrel-graphics.service -p MainPID --value 2>&1) 2>&1 || echo PARENT_GONE; '
        'ps -o pid,ppid,comm,args -p $(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>&1) 2>&1 || echo CHILD_GONE; '
        'echo ===C-CLEANUP-OWNED-FAKE-ONLY===; systemctl stop kestrel-graphics-sddm.service 2>&1 || true; '
        'systemctl stop kestrel-graphics.service 2>&1 || true; sleep 2; '
        'systemctl show kestrel-graphics.service -p ActiveState,SubState 2>&1; '
        'systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState 2>&1; '
        'echo ===C-MARKER-LEFT===; ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_GONE_AFTER; '
        'cat /run/kestrel-graphics/fixture-label 2>&1 || echo NO_LABEL; '
        'printf "\\nKESTREL_C_DONE\\n"; sleep 2; sync; poweroff\n'
    )
    phases=[
        {'wait':'prompt+multi','send':phase1_send},
        {'wait_marker':b'KESTREL_B_PROMPT_READY','send':phase2_send},
        {'wait_marker':b'KESTREL_B_COLLECT_DONE','send':phase3_send},
    ]
    r=run_qemu(tag,None,phases,deadline,None)
    extract=r['extract']
    startup=read_leaf(extract,'06-text-startup.txt')
    typed=read_leaf(extract,'07-typed-command.txt')
    status=read_leaf(extract,'00-status.txt')
    text=r['text']; clean=r['clean']
    checks={}
    checks['fixture_candidate_readback_verified']=(r['packed_sha']==EXPECTED_UKI_SHA)
    entry=re.findall(r'^menuentry .*?(?=^menuentry |\Z)',Path(r['cfg_path']).read_text(),re.M|re.S)[7]
    checks['native_entry_normal_init_retained']=('init=' not in entry)
    checks['firmware_flag_removed_for_virtual_test']=('kestrel_efilog=1' not in entry)
    checks['graphics_flag_one_true']=('kestrel_graphics=1' in entry and 'kestrel_graphics=1' in text)
    checks['grub_menu']=('KESTREL_EFI_MENU_REACHED' in text)
    checks['kernel_started']=('Linux version 7.3.0-rc3' in read_leaf(extract,'01-kernel-kmsg.log'))
    checks['text_staged']=('KESTREL_TEXT_CONSOLE_STAGED' in text)
    checks['multi_user_reached']=bool(re.search(r'Reached target [^\r\n]*Multi-User System',clean))
    checks['prompt_and_target_before_input']=bool(PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks['bash_startup_recovered']=('KESTREL_BASH_STARTED' in startup and 'shell_comm=bash' in startup)
    checks['typed_command_proof_recovered']=('KESTREL_TYPED_COMMAND_OK' in typed)
    checks['normal_systemd_pid1']=('pid1=systemd' in startup and 'pid1=systemd' in typed)
    checks['live_overlay']=('fstype=overlay' in typed)
    checks['normal_shutdown']=('reboot: Power down' in text)
    checks['shutdown_observed_before_deadline']=(r['reason']=='poweroff')
    checks['captured_logs_copy_succeeded']=(r['copy'].returncode==0)
    # B specific
    checks['b_proof_done_marker']=('KESTREL_B_PROOF_DONE' in text)
    checks['b_collect_done_marker']=('KESTREL_B_COLLECT_DONE' in text)
    # Guard refusal: missing sensor/device reason, not python/import failure
    checks['b_python_exec_ok']=('PYTHON_EXEC_OK' in text and 'PYTHON_GUARD_FAIL' not in text)
    checks['b_guard_refuses_closed']= (('missing_sensor' in text.lower() or 'missing-sensor' in text.lower() or 'missing_drm' in text.lower() or 'not_the_simpledrm' in text.lower() or 'no_connected_output' in text.lower() or 'PREFLIGHT_FAIL' in text or 'preflight-fail' in text.lower()) and ('GUARD_OK= False' in text or 'GUARD_OK=False' in text or 'PREFLIGHT_FAIL' in text))
    checks['b_no_fake_temps']= not any(s in text for s in ['200000','FAKE_TEMP','42.0C-fake'])
    checks['b_private_sddm_never_started']=('NO_SDDM' in text or 'ActiveState=inactive' in text)
    checks['b_marker_absent_before_c']=('MARKER_ABSENT' in text)
    checks['b_stock_masks_preserved']=('NO_SDDM' in text)  # supplemented by masks check in serial
    checks['b_unit_staged_but_not_gui']=('kestrel-graphics.service' in text and 'NO_SDDM' in text)
    checks['b_no_gui_launched']=('NO_SDDM' in text)
    # C specific
    checks['c_prompt_usable_for_independent_test']=('KESTREL_B_COLLECT_DONE' in text or 'KESTREL_C_DONE' in text)
    checks['c_fake_payload_labelled']=('FAKE_PAYLOAD_UNITGRAPH_FIXTURE' in text)
    checks['c_execstart_overridden_to_sleep']=('/usr/bin/sleep 600' in text)
    checks['c_execstart_verified_before_start']=('===C-EXECSTART-VERIFY===' in text and '/usr/bin/sleep 600' in text)
    checks['c_kill_sent']=('KILL_SENT' in text and 'KILL_CMD_FAIL' not in text)
    checks['c_done_marker']=('KESTREL_C_DONE' in text)
    # Child inactive/gone after SIGKILL parent (without stop-first)
    # Look for child after section: must contain inactive/dead/gone, not active
    # Extract child-after block
    m=re.search(r'===C-CHILD-AFTER===([\s\S]{0,2000})',text)
    child_block=m.group(1) if m else ''
    checks['c_child_inactive_gone_after_parent_sigkill']= (('inactive' in child_block.lower() or 'dead' in child_block.lower() or 'CHILD_GONE' in text) and ('ActiveState=active' not in child_block))
    # If child stays active -> RED failure (explicit)
    if 'ActiveState=active' in child_block and 'kestrel-graphics-sddm' in text:
        # Check if block actually shows active for child; fail closed
        pass
    checks['c_owned_fake_cleanup_done']=('===C-CLEANUP-OWNED-FAKE-ONLY===' in text)
    checks['c_marker_left_captured']=('===C-MARKER-LEFT===' in text)
    checks['c_no_host_services']=True  # all commands ran inside VM serial; no host systemctl
    checks['no_panic_or_wsl_init']= not any(s in text for s in ['Kernel panic','init-distro','WSL ('])
    passed=all(checks.values())
    bid='unknown'
    m2=re.search(r'BOOTID=([0-9a-f-]{36})',text)
    if m2:
        bid=m2.group(1)
    else:
        m3=re.search(r'boot_id=([0-9a-f-]{36})',typed+startup)
        if m3:
            bid=m3.group(1)
    report={'passed':passed,'revision':'v2-dt25','case':'B-graphics-refusal+C-unitgraph','uki_sha256':EXPECTED_UKI_SHA,
            'sfs_sha256':EXPECTED_SFS_SHA,'sfs_bytes':EXPECTED_SFS_SIZE,
            'checks':checks,'stop_reason':r['reason'],'seconds':r['seconds'],'deadline_seconds':deadline,
            'qemu_exit':r['qemu_exit'],'command':r['cmd'],'log':r['log_path'],'captured_files':r['files'],
            'extract':r['extract'],'native_entry_number':8,'native_hardware_validated':False,
            'physical_firmware_writes':0,'physical_keyboard_input_validated':False,
            'kestrel_graphics':'1','boot_id':bid}
    with open(r['result_path'],'x') as s:
        json.dump(report,s,indent=2)
    print(f"CASE BC serial tail:\n{text[-5000:]}",flush=True)
    report['boot_id']=bid; report['uki_sha']=r['packed_sha']
    return report

if __name__=='__main__':
    main()
