#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable QEMU boot of the firmware-free public image (run in the CachyOSBuilder distro; no real media).

A copy of the image is made and ONLY /boot/grub/grub.cfg inside the copy is replaced by a test variant (timeout 1, serial
console added to the kernel lines). Everything else (GRUB binary, UKIs, root squashfs) is the exact image under test.
QEMU virt is not the laptop: this proves the image boots, the identity and the pruning, not any hardware behaviour.

FZ_RECORDER=1 (or full) adds the smartlog-v3 recorder contract test: KESTREL-LOG-TARGET and Logs/ are injected into the
disposable stick, the guest prints one ===REC=== block, and the host asserts the markers. FZ_RECORDER=power sends an HMP
'quit' after the guest prints FZREC_POWER_READY and then reads the logs back from the stick image. The recorder itself is
implemented by another worker; the assertions follow the W4 section 15.3 layout and the FZ_LOG_* environment contract, and
the table below is the one place to adjust a marker.
"""
import hashlib, json, os, re, select, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path

C = Path('/mnt/d/CachyOS-ARM64/maverick-dev-candidate-20261110'); B = Path('/mnt/d/FroodzOS-build')
IMG = B / os.environ.get('FZ_IMG', 'FroodzOS-0.1.0-dev-maverick-arm64-83n3-nofw.img'); TEST = B / 'qemu-public-test.img'
EXPECT_BUILD = os.environ.get('FZ_EXPECT_BUILD', 'maverick-public-dev')
FW = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd')
REC = os.environ.get('FZ_RECORDER', '').strip().lower()
REC = 'full' if REC in ('1', 'full') else (REC if REC in ('power', 'unplug') else '')

ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
REC_BLOCK = re.compile(r'===REC===(.*?)===RECEND===', re.S)
REC_KV = re.compile(r'^([a-z0-9_]+)=(.*)$')


def clean_serial(text):
    return ANSI.sub('', text).replace('\r', '')


def parse_rec_block(text):
    match = REC_BLOCK.search(clean_serial(text))
    if not match:
        return {}
    values = {}
    for line in match.group(1).splitlines():
        hit = REC_KV.match(line.strip())
        if hit:
            values[hit.group(1)] = hit.group(2).strip()
    return values


def rec_int(values, key, default=0):
    try:
        return int(values.get(key, default))
    except (TypeError, ValueError):
        return default


def rec_bool(values, key):
    return str(values.get(key, '')).strip().lower() in ('1', 'true', 'yes', 'ok', 'active')


RECORDER_MARKERS = (
    {'name': 'block_found', 'required': True,
     'check': lambda kv: bool(kv)},
    {'name': 'recorder_service_active', 'required': True,
     'check': lambda kv: str(kv.get('service_active', '')).strip() == 'active'},
    {'name': 'recorder_started_early', 'required': True,
     'check': lambda kv: bool(rec_int(kv, 'userspace_monotonic_us') and rec_int(kv, 'recorder_started_monotonic_us')
                              and 0 <= rec_int(kv, 'recorder_started_monotonic_us') - rec_int(kv, 'userspace_monotonic_us') <= int(os.environ.get('FZ_REC_EARLY_US', '3000000')))},
    {'name': 'first_record_before_userspace', 'required': False,
     'check': lambda kv: bool(rec_int(kv, 'userspace_monotonic_us')
                              and rec_int(kv, 'first_record_uptime_ms') * 1000 <= rec_int(kv, 'userspace_monotonic_us'))},
    {'name': 'handover_gap_ok', 'required': False,
     'check': lambda kv: 0 <= rec_int(kv, 'handover_gap_ms') <= 2000},
    {'name': 'kmsg_stream_has_early_boot', 'required': True,
     'check': lambda kv: rec_bool(kv, 'kmsg_has_boot') and rec_int(kv, 'kmsg_bytes') > 0},
    {'name': 'journal_file_present', 'required': True,
     'check': lambda kv: rec_int(kv, 'journal_bytes') > 0},
    {'name': 'terminal_session_recorded', 'required': True,
     'check': lambda kv: rec_bool(kv, 'term_has_marker')},
    {'name': 'terminal_exit_code_recorded', 'required': True,
     'check': lambda kv: rec_bool(kv, 'term_has_exit')},
    {'name': 'terminal_redaction_applied', 'required': True,
     'check': lambda kv: rec_bool(kv, 'term_has_redacted') and not rec_bool(kv, 'term_has_secret')},
    {'name': 'redaction_marker_seen', 'required': True,
     'check': lambda kv: rec_bool(kv, 'redaction_seen')},
    {'name': 'size_cap_respected', 'required': True,
     'check': lambda kv: (rec_bool(kv, 'cap_ok')
                          and rec_int(kv, 'max_file_bytes') <= rec_int(kv, 'per_file_cap', 8 << 20)
                          and rec_int(kv, 'total_bytes') <= rec_int(kv, 'global_cap', 64 << 20))},
    {'name': 'free_space_guard_respected', 'required': True,
     'check': lambda kv: rec_bool(kv, 'guard_ok')
                         and rec_int(kv, 'free_after_kb') >= rec_int(kv, 'reserve_kb')},
    {'name': 'ram_fallback_used', 'required': False,
     'check': lambda kv: rec_bool(kv, 'ram_fallback')},
    {'name': 'flood_cap_reached', 'required': False,
     'check': lambda kv: rec_bool(kv, 'flood_cap_reached')},
)


def evaluate_recorder_markers(text, table=RECORDER_MARKERS):
    values = parse_rec_block(text)
    markers = {}
    for row in table:
        try:
            markers[row['name']] = bool(row['check'](values))
        except Exception:
            markers[row['name']] = False
    markers['panic'] = 'Kernel panic' in text
    markers['raw'] = values
    return markers


def recorder_markers_pass(markers, table=RECORDER_MARKERS):
    required = [row['name'] for row in table if row.get('required')]
    return all(markers.get(name) for name in required) and not markers.get('panic')


POWERCUT_MARKERS = (
    {'name': 'powercut_ready_marker', 'required': True,
     'check': lambda text, files: 'FZREC_POWER_READY' in text},
    {'name': 'powercut_stream_files_present', 'required': True,
     'check': lambda text, files: files.get('stream_files', 0) > 0},
    {'name': 'powercut_logs_readable', 'required': True,
     'check': lambda text, files: files.get('complete_records', 0) > 0},
    {'name': 'powercut_alive_marker_present', 'required': False,
     'check': lambda text, files: files.get('alive_marker', False)},
)


def evaluate_powercut(text, files, table=POWERCUT_MARKERS):
    markers = {}
    for row in table:
        try:
            markers[row['name']] = bool(row['check'](text, files))
        except Exception:
            markers[row['name']] = False
    return markers


def powercut_markers_pass(markers, table=POWERCUT_MARKERS):
    return all(markers.get(row['name']) for row in table if row.get('required'))


def recorder_selftest_script():
    return r'''#!/bin/sh
# fz-recorder-selftest.sh <nonce> [target] [mode]
N=$1
T=${2:-/run/archiso/bootmnt}
MODE=${3:-full}
sleep 3
capture() { "$@" 2>/dev/null || true; }
R=$(ls -d "$T"/Logs/boot-* 2>/dev/null | sort | tail -1)
if [ -z "$R" ]; then R="$T"; fi
ACTIVE=$(capture systemctl is-active fz-smartlog)
[ -n "$ACTIVE" ] || ACTIVE=unknown
US=$(capture systemctl show -p UserspaceTimestampMonotonic --value)
ST=$(capture systemctl show -p ActiveEnterTimestampMonotonic --value fz-smartlog)
KBOOT=0
grep -R -q "Booting Linux" "$R/streams/kernel" 2>/dev/null && KBOOT=1
KB=$(find "$R/streams/kernel" -type f -exec du -cb {} + 2>/dev/null | awk 'END{print $1+0}')
JB=$(find "$R/streams/journal" -type f -exec du -cb {} + 2>/dev/null | awk 'END{print $1+0}')
TM=$(grep -R -q "FZREC_MARKER_$N" "$R/streams/terminal" 2>/dev/null && echo 1 || echo 0)
TE=0
grep -R -q -E '"exit"[[:space:]]*:[[:space:]]*[1-9]' "$R/streams/terminal" 2>/dev/null && TE=1
TS=$(grep -R -q "FZREC_SECRET_$N" "$R" 2>/dev/null && echo 1 || echo 0)
TR=$(grep -R -q -E "REDACTED|<redacted" "$R/streams/terminal" 2>/dev/null && echo 1 || echo 0)
FR=0
FIRST=$(head -1 "$R"/streams/kernel/000001.jsonl 2>/dev/null)
MONO=$(printf '%s' "$FIRST" | grep -o '"mono": *[0-9.]*' | grep -o '[0-9.]*$' | head -1)
[ -n "$MONO" ] && FR=$(printf '%s' "$MONO" | awk '{printf "%d", $1*1000}')
GAP=$(grep -o '"handover_gap_ms"[[:space:]]*:[[:space:]]*[0-9]*' "$R"/boot.json 2>/dev/null | grep -o '[0-9]*$' | head -1)
PER=${FZ_LOG_MAX_STREAM_BYTES:-8388608}
GLOBAL=${FZ_LOG_MAX_BOOT_BYTES:-67108864}
RES=${FZ_LOG_MIN_FREE_KB:-16384}
measure() {
  MAXF=$(find "$R" -type f -exec stat -c %s {} + 2>/dev/null | sort -n | tail -1)
  TOTAL=$(du -sb "$R" 2>/dev/null | awk '{print $1+0}')
  MAXF=${MAXF:-0}; TOTAL=${TOTAL:-0}
  if [ "$MAXF" -le "$PER" ] && [ "$TOTAL" -le "$GLOBAL" ]; then CAP_OK=1; else CAP_OK=0; fi
}
measure
FLOOD=0
if command -v fz-recorder >/dev/null 2>&1; then
  fz-recorder selftest flood --mb 200 --stream journal >/tmp/fz-rec-flood 2>&1 && FLOOD=1
elif command -v fz-smartlog >/dev/null 2>&1; then
  fz-smartlog selftest flood --mb 200 --stream journal >/tmp/fz-rec-flood 2>&1 && FLOOD=1
fi
FLOOD_CAP=0
grep -q 'cap_reached=1' /tmp/fz-rec-flood 2>/dev/null && FLOOD_CAP=1
measure
FREE=$(df -Pk "$T" 2>/dev/null | awk 'NR==2{print $4+0}')
FREE=${FREE:-0}
if [ "$FREE" -ge "$RES" ]; then GUARD=1; else GUARD=0; fi
RAMF=0
grep -R -q -E '"dest"[[:space:]]*:[[:space:]]*"ram"|where=ram' "$R" 2>/dev/null && RAMF=1
echo '===REC==='
echo "service_active=${ACTIVE:-unknown}"
echo "userspace_monotonic_us=${US:-0}"
echo "recorder_started_monotonic_us=${ST:-0}"
echo "first_record_uptime_ms=${FR:-0}"
echo "handover_gap_ms=${GAP:-0}"
echo "kmsg_has_boot=${KBOOT}"
echo "kmsg_bytes=${KB:-0}"
echo "journal_bytes=${JB:-0}"
echo "term_has_marker=${TM}"
echo "term_has_exit=${TE}"
echo "term_has_secret=${TS}"
echo "term_has_redacted=${TR}"
echo "max_file_bytes=${MAXF:-0}"
echo "total_bytes=${TOTAL:-0}"
echo "per_file_cap=${PER}"
echo "global_cap=${GLOBAL}"
echo "cap_ok=${CAP_OK:-0}"
echo "flood_supported=${FLOOD}"
echo "flood_cap_reached=${FLOOD_CAP}"
echo "free_after_kb=${FREE}"
echo "reserve_kb=${RES}"
echo "guard_ok=${GUARD:-0}"
echo "redaction_seen=${TR}"
echo "ram_fallback=${RAMF}"
echo '===RECEND==='
echo '===RECDIAG==='
echo "R=$R"; ls /run/fz-smartlog 2>&1 | head; cat /run/fz-smartlog/env 2>&1 | head -12
find "$R" -maxdepth 3 2>/dev/null | head -40
capture fz-smartlog status | head -30
echo '===RECDIAGEND==='
if [ "$MODE" = power ] || [ "$MODE" = unplug ]; then
  MODE_UP=$(printf '%s' "$MODE" | tr 'a-z' 'A-Z')
  echo "FZREC_${MODE_UP}_READY"
  sleep 300
fi
'''


class HMP:
    def __init__(self, path, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline and not os.path.exists(path):
            time.sleep(0.1)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(path)

    def cmd(self, text):
        self.sock.sendall((text + '\n').encode())
        time.sleep(0.2)
        try:
            return self.sock.recv(65536).decode('utf-8', 'replace')
        except socket.timeout:
            return ''

    def quit(self):
        return self.cmd('quit')

    def device_del(self, device_id):
        return self.cmd('device_del ' + device_id)


def read_recorder_tree(image, offset=True):
    """Read ::/Logs from a FAT image with mtools (no root, no mount)."""
    result = {'stream_files': 0, 'complete_records': 0, 'alive_marker': False, 'files': 0, 'error': ''}
    if not shutil.which('mcopy'):
        result['error'] = 'mtools mcopy not installed'
        return result
    temp = tempfile.mkdtemp(prefix='fzrec-read.')
    try:
        fs = str(image) + ('@@1M' if offset else '')
        proc = subprocess.run(['mcopy', '-s', '-n', '-i', fs, '::/Logs', temp],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            result['error'] = (proc.stdout + proc.stderr).strip()[:300]
            return result
        for path in sorted(Path(temp).rglob('*')):
            if not path.is_file():
                continue
            result['files'] += 1
            if path.name == 'alive.txt' or path.name == 'alive.json':
                result['alive_marker'] = True
            if path.parts and 'streams' in path.parts:
                result['stream_files'] += 1
                data = path.read_bytes()[:1 << 20]
                for line in data.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if path.suffix == '.jsonl':
                        try:
                            json.loads(line.decode('utf-8', 'replace'))
                            result['complete_records'] += 1
                        except ValueError:
                            continue
                    elif path.suffix == '.log':
                        if re.match(rb'^\d+,\d+,\d+,[^;]*;', line) or line.startswith(b'['):
                            result['complete_records'] += 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return result


def build_recorder_stick(fs):
    subprocess.run(['mmd', '-i', fs, '::/Logs'], check=False, capture_output=True)
    marker = B / 'KESTREL-LOG-TARGET.qemu-recorder'
    marker.write_text('KESTREL_A64_USB_CAPTURE_V1\n', encoding='ascii', newline='\n')
    subprocess.run(['mcopy', '-i', fs, '-o', str(marker), '::/KESTREL-LOG-TARGET'], check=True)
    script = B / 'fz-recorder-selftest.sh'
    script.write_text(recorder_selftest_script(), encoding='utf-8', newline='\n')
    subprocess.run(['mcopy', '-i', fs, '-o', str(script), '::/fz-recorder-selftest.sh'], check=True)


def build_qemu_command(test_img, nvme, waydroid, recorder, monitor):
    drive = ['-drive', 'if=none,id=stick,format=raw' + ('' if recorder else ',snapshot=on') + ',file=' + str(test_img),
             '-device', 'usb-storage,drive=stick']
    cmd = ['qemu-system-aarch64', '-M', 'virt,gic-version=3', '-cpu', 'cortex-a53', '-accel', 'tcg', '-m', '3072', '-smp', os.environ.get('FZ_SMP', '2'),
           '-bios', str(FW), '-device', 'qemu-xhci'] + drive + ['-nographic', '-no-reboot']
    if recorder:
        cmd += ['-drive', 'if=none,id=rectest,format=raw,cache=writeback,file=' + str(B / 'qemu-recorder-test-disk.img'),
                '-device', 'usb-storage,drive=rectest,id=rectest',
                '-monitor', 'unix:%s,server=on,wait=off' % monitor]
    else:
        cmd += ['-monitor', 'none']
    if nvme:
        cmd += ['-drive', 'if=none,id=nv,format=raw,snapshot=on,file=' + str(B / 'qemu-nvme-test.img'),
                '-device', 'nvme,drive=nv,serial=fztest']
    return cmd


def main():
    tag = os.environ.get('FZ_TAG', 'public-image-qemu-1')
    log_path = C / 'output' / (tag + '.log')
    res_path = C / 'output' / (tag + '-result.json')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    img_sha = hashlib.file_digest(IMG.open('rb'), 'sha256').hexdigest()
    cfg = (C / 'output' / os.environ.get('FZ_CFG', 'grub.cfg.public')).read_text(encoding='utf-8')
    serial_opts = ' console=ttyAMA0,115200'
    if REC:
        serial_opts += ' fz_record=full kestrel_graphics=0'
    if os.environ.get('FZ_EXTRA_CMDLINE'):
        serial_opts += ' ' + os.environ['FZ_EXTRA_CMDLINE']
    cfg = cfg.replace('set timeout=10', 'set timeout=1').replace(' kestrel_efilog=0', ' kestrel_efilog=0' + serial_opts)
    tcfg = B / 'grub.cfg.qemu'
    tcfg.write_text(cfg, encoding='utf-8', newline='\n')
    shutil.copyfile(IMG, TEST)
    fs = str(TEST) + '@@1M'
    subprocess.run(['mcopy', '-i', fs, '-o', str(tcfg), '::/boot/grub/grub.cfg'], check=True)
    NVME = os.environ.get('FZ_NVME') == '1'
    WD = os.environ.get('FZ_WAYDROID') == '1'
    if NVME:
        NVME_IMG = B / 'qemu-nvme-test.img'
        NVME_IMG.unlink(missing_ok=True)
        with NVME_IMG.open('wb') as f:
            f.truncate(64 * 1024 * 1024)
        subprocess.run(['sfdisk', str(NVME_IMG)], input=b'label: gpt\nstart=2048, size=60000\nstart=64000, size=60000\n',
                       check=True, capture_output=True)
    monitor = Path(os.environ.get('FZ_MONITOR_SOCKET', '/tmp/qemu-recorder-test.mon'))  # unix sockets cannot live on /mnt/d
    if REC:
        monitor.unlink(missing_ok=True)
        build_recorder_stick(fs)
        rec_disk = B / 'qemu-recorder-test-disk.img'
        rec_disk.unlink(missing_ok=True)
        with rec_disk.open('wb') as f:
            f.truncate(64 * 1024 * 1024)
        subprocess.run(['mkfs.vfat', '-F', '32', '-n', 'FZREC_TEST', str(rec_disk)], check=True, capture_output=True)
    cmd = build_qemu_command(TEST, NVME, WD, REC, monitor)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    start = time.monotonic(); out = b''; reason = 'deadline'; mu_at = None; typed = False; end_at = None; login_at = None
    nonce = 'qemu%06d' % (int(start) % 1000000)
    hmp = None
    CMDS = [b'live\n', b'live\n',
            b'echo ===JOBS===; systemctl list-jobs --no-pager 2>&1 | head -20; systemctl is-system-running; echo ===JOBSEND===\n',
            b'echo ===ID===; grep -E "^(PRETTY_NAME|BUILD_ID|ID)=" /etc/os-release; uname -r; pacman -Q linux-froodzos-arm64; pacman -Q | wc -l\n',
            b'echo ===PRUNED===; ls /usr/lib/firmware/updates 2>&1 | head -2; sudo -n ls -A /etc/pacman.d/gnupg/private-keys-v1.d | wc -l; ls /usr/lib/firmware | wc -l; ls /usr/lib/firmware/ath12k 2>&1 | head -3\n',
            b'echo ===PHASE1===; pacman -Q firefox 2>&1 | head -1; ls /usr/share/pixmaps | grep -c archlinux; grep -E "^(NAME|VERSION_ID|BUILD_ID)=" /usr/lib/os-release; pacman -Q ark okular gwenview libreoffice-fresh falkon haruna mpv 2>&1 | wc -l; command -v 7zz unrar bsdtar; echo ===PHASE1END===\n',
            b'echo ===R3===; ls /opt/helium/helium /opt/zen/zen /usr/local/bin/helium; pacman -Q chromium 2>&1 | head -1; pacman -Q falkon 2>&1 | head -1; ls /etc/mpv/mpv.conf /usr/local/bin/fz-mount-image /etc/sysctl.d/90-froodzos-userns.conf; command -v udisksctl; grep -c chromium /etc/xdg/mimeapps.list; systemctl is-enabled fz-smartlog; ls /run/fz-smartlog | head -4; echo ===R3END===\n',
            b'echo ===DBCHECK===; pacman -Dk 2>&1 | tail -n 6; echo dbrc=$?\n',
            b'echo ===UNITS===; systemctl is-enabled fz-touchpad; systemctl --failed --no-legend | head -8\n',
            b'echo ===SELFTEST===; sudo -n python3 /usr/local/sbin/fz-touchpad.py --selftest; echo rc=$?\n',
            *([b'echo ===NVME===; ls /dev/nvme0n1*; for d in /dev/nvme0n1*; do echo "$d RO=$(sudo -n blockdev --getro $d)"; done; sudo -n dd if=/dev/zero of=/dev/nvme0n1p1 bs=512 count=1 conv=notrunc >/dev/null 2>&1; echo DDRC=$?; udevadm info -q property -n /dev/nvme0n1p1 | grep UDISKS_; echo ===NVMEEND===\n'] if NVME else []),
            *([b'echo ===WD===; sudo -n fz-waydroid check 2>&1 | tail -n 22; sudo -n lsmod | grep -c binder_linux; sudo -n fz-waydroid init 2>&1 | tail -n 3; echo ===WDEND===\n'] if WD else []),
            b'echo ===MOUNTS===; findmnt -no SOURCE,FSTYPE / ; ls /run/archiso/bootmnt | head -8; echo ===END===\n']
    rec_cmds = [b'live\n', b'live\n',
                b'echo FZREC_MARKER_' + nonce.encode() + b'\n',
                b'false\n',
                b'echo "password=FZREC_SECRET_' + nonce.encode() + b'"\n',
                b'exit\n', b'SLEEP:20', b'live\n', b'live\n',
                b'sh /run/archiso/bootmnt/fz-recorder-selftest.sh ' + nonce.encode() + b' /run/archiso/bootmnt ' + REC.encode() + b'\n']
    with log_path.open('xb') as log:
        while time.monotonic() - start < 1500 and proc.poll() is None:
            cleanw = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
            if login_at is None and b'login:' in cleanw: login_at = time.monotonic()
            stalled = mu_at is None and login_at is not None and time.monotonic() - login_at > 120
            if (stalled or (mu_at and time.monotonic() - mu_at > 25)) and not typed and b'login:' in cleanw:
                typed = True; reason = 'logged-in'
                if REC:
                    if hmp is None:
                        try:
                            hmp = HMP(str(monitor))
                        except OSError as exc:
                            hmp = None
                            reason = 'monitor-connect-failed: %s' % exc
                    for line in rec_cmds:
                        if line.startswith(b'SLEEP:'):
                            time.sleep(int(line[6:])); continue
                        proc.stdin.write(line); proc.stdin.flush()
                        time.sleep(15 if line == b'live\n' else 6)  # TCG guests need time between the login name and the password
                    end_at = time.monotonic() + 300
                else:
                    for line in CMDS:
                        proc.stdin.write(line); proc.stdin.flush(); time.sleep(12)
                    end_at = time.monotonic() + 30
            if REC and hmp and (b'FZREC_POWER_READY' in out or b'FZREC_UNPLUG_READY' in out) and reason == 'logged-in':
                time.sleep(6)
                if REC == 'power':
                    hmp.quit(); reason = 'power-cut'; end_at = time.monotonic() + 20
                else:
                    hmp.device_del('rectest'); reason = 'unplugged'; time.sleep(5)
                    proc.stdin.write(b'echo FZREC_UNPLUG_DONE\n'); proc.stdin.flush()
                    end_at = time.monotonic() + 30
            if not select.select([proc.stdout], [], [], 1)[0]:
                if end_at and time.monotonic() > end_at: break
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk: reason = 'eof'; break
            out += chunk; log.write(chunk); log.flush()
            clean = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', out)
            if b'Falling back to interactive prompt' in out: reason = 'initramfs-mount-failure'; break
            if b'---[ end Kernel panic' in out: reason = 'kernel-panic'; break
            if b'===RECDIAGEND===' in out and REC and REC == 'full': reason = 'recorder-selftest'; break
            if mu_at is None and re.search(rb'Reached target [^\r\n]*Multi-User System', clean): mu_at = time.monotonic()
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        out += proc.stdout.read()
    text = out.decode(errors='replace'); clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text).replace('\r', '')
    seg = lambda a, b: clean[clean.rfind(a):clean.rfind(b)] if a in clean else ''
    markers = {
        'grub_started': 'GNU GRUB' in text or 'Booting' in text or 'EFI stub' in text,
        'multi_user': mu_at is not None,
        'logged_in_and_ran': '===END===' in clean,
        'identity_public_build': EXPECT_BUILD in clean and 'firmware-free public build' in clean,
        'no_firefox': "package 'firefox' was not found" in seg('===PHASE1===', '===PHASE1END==='),
        'no_arch_logo': '\n0\n' in seg('===PHASE1===', '===PHASE1END==='),
        'handlers_installed': '\n7\n' in seg('===PHASE1===', '===PHASE1END==='),
        'r3_chromium_no_falkon': ('/opt/helium/helium' in seg('===R3===', '===R3END===')) and ('/opt/zen/zen' in seg('===R3===', '===R3END===')) and ("package 'chromium' was not found" in seg('===R3===', '===R3END===')) and ("package 'falkon' was not found" in seg('===R3===', '===R3END===')),
        'r3_files': all(x in seg('===R3===', '===R3END===') for x in ('/etc/mpv/mpv.conf', '/usr/local/bin/fz-mount-image', '90-froodzos-userns.conf', 'udisksctl')),
        'smartlog_running': 'enabled' in seg('===R3===', '===R3END===') and ('ready' in seg('===R3===', '===R3END===') or 'events.log' in seg('===R3===', '===R3END===')),
        'kernel_package_renamed': 'linux-froodzos-arm64 7.3.0rc3-1' in clean,
        'no_vendor_firmware_dir': bool(re.search(r'===PRUNED===\s*\n[^\n]*No such file', clean)),
        'no_private_keyring_key': bool(re.search(r'===PRUNED===[^\n]*\n[^\n]*No such file[^\n]*\n[^\n]*\n?\s*0\b', clean)) or '\n0\n' in seg('===PRUNED===', '===DBCHECK==='),
        'selftest_pass': 'fz-touchpad: SELFTEST PASS' in clean,
        'panic': 'Kernel panic' in text,
    }
    if NVME:
        nv = seg('===NVME===', '===NVMEEND===')
        ros = re.findall(r'(/dev/nvme0n1\S*) RO=(\d)', nv)
        markers['nvme_all_read_only'] = len(ros) >= 3 and all(v == '1' for _, v in ros)
        markers['nvme_write_refused'] = bool(re.search(r'DDRC=[1-9]', nv))
        markers['nvme_hidden_from_udisks'] = 'UDISKS_AUTO=0' in nv and 'UDISKS_IGNORE' not in nv and 'ro,nosuid,nodev,noexec' in nv
    if WD:
        wd = seg('===WD===', '===WDEND===')
        markers['waydroid_binder_loads'] = 'binder filesystem: available' in wd
        markers['waydroid_tools_present'] = 'MISSING' not in wd and 'tool waydroid:' in wd
        markers['waydroid_init_needs_persist'] = 'no persistent partition' in wd.split('fz-waydroid init')[-1] or wd.count('no persistent partition') >= 2
    rec_markers = {}
    powercut = {}
    if REC:
        rec_markers = evaluate_recorder_markers(text)
        markers.update({k: v for k, v in rec_markers.items() if k != 'raw'})
        markers['recorder_raw'] = rec_markers.get('raw', {})
        if REC == 'power':
            powercut = evaluate_powercut(text, read_recorder_tree(TEST, offset=True))
            markers.update(powercut)
    if REC:
        passed = markers['multi_user'] and recorder_markers_pass(rec_markers) and not markers['panic']
        if REC == 'power':
            passed = passed and powercut_markers_pass(powercut)
    else:
        passed = all(markers[k] for k in ('multi_user', 'logged_in_and_ran', 'identity_public_build', 'kernel_package_renamed', 'selftest_pass', 'no_firefox', 'no_arch_logo', 'handlers_installed', 'r3_chromium_no_falkon', 'r3_files', 'smartlog_running')) and not markers['panic'] and (not NVME or all(markers[k] for k in ('nvme_all_read_only', 'nvme_write_refused', 'nvme_hidden_from_udisks'))) and (not WD or all(markers[k] for k in ('waydroid_binder_loads', 'waydroid_tools_present', 'waydroid_init_needs_persist')))
    tail = clean[clean.rfind('===ID==='):] if '===ID===' in clean else clean[-3500:]
    summary = {'tag': tag, 'seconds': round(time.monotonic() - start, 1), 'stop_reason': reason, 'markers': markers, 'passed': passed,
               'image_sha256': img_sha, 'hardware_validated': False, 'recorder_mode': REC or None,
               'scope': 'QEMU TCG virt; the image under test is the real public image except grub.cfg (test variant: timeout 1, serial console). No laptop hardware behaviour is tested.'}
    if REC:
        summary['test_image'] = str(TEST)
        summary['recorder_contract'] = 'W4 section 15.3 streams + FZ_LOG_* environment; marker table in builder/public-image/qemu-public.py'
    res_path.write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=2)); print('--- GUEST OUTPUT:'); print(tail[:5000])
    if not REC:
        TEST.unlink(missing_ok=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
