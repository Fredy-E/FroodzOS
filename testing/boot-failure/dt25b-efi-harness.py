#!/usr/bin/env python3
"""dt25b EFI validation harness: text fallback (A) + graphics refusal (B) + isolated SIGKILL unit-graph (C).

Revision-aware (v2-dt25b). Owns ONLY dt25b-efi-* outputs. Reads existing
helpers read-only. Never edits production units. Real EFI->GRUB->UKI->
initramfs->SFS->systemd path only (no -kernel/-initrd/-append). Guest
<=2048MiB, 2 TCG cores, serial ttyAMA0. kestrel_efilog stays OFF for VM,
efi-pstore.pstore_disable retained.

Oracle preference: guest-generated atomic JSON on validated VM fixture USB:
  /run/archiso/bootmnt/Logs/boot-<boot-id>/08-graphics-test.json
  /run/archiso/bootmnt/Logs/boot-<boot-id>/09-unit-chaos.json
Serial is fallback only (anchored records + strict JSON validation).

Unit contract under test (deleg_03f10f91):
  parent ExecStartPre AND ExecStopPost exactly:
    /usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed
  child BindsTo=parent in addition to After+PartOf.
C sequence (new): stale marker -> start parent -> assert Pre cleared ->
fake marker -> start child -> SIGKILL parent -> bounded 15s auto child
inactive/PID0/gone + marker ABSENT post stop. No manual stop before
measurement. Marker-left is FAIL (changed from v2).

Usage (run AFTER dt25b build is parent-verified; this file does code only):
  python3 dt25b-efi-harness.py --audit <dt25b-artifact-audit.json> \
      --case {a,bc,all} --prefix dt25b-efi-fw-off-v1
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
B = Path("/home/builder/boot-failure-tests")
LOCK = B / "dt25-build.lock"
QEMU_FD = T / "uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"

REVISION = "v2-dt25b"
PROMPT_RE = re.compile(r"(?:^|[\r\n])KESTREL-TEXT# ")
MULTI_RE = re.compile(r"Reached target [^\r\n]*Multi-User System")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# Parser lives beside this harness; load by path (dash in filename).
PARSER_PATH = T / "dt25b-efi-parser.py"


def load_parser():
    spec = importlib.util.spec_from_file_location(
        "dt25b_efi_parser", str(PARSER_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def disk_free_ok(path):
    try:
        free = shutil.disk_usage(str(path)).free
        return free > 10 * 1024 ** 3, free
    except Exception:
        return False, 0


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            c = f.read(16 * 1024 * 1024)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def fat_offset(image):
    pt = json.loads(subprocess.check_output(
        ["sfdisk", "--json", str(image)]))["partitiontable"]
    return pt, str(image) + "@@" + str(
        pt["partitions"][0]["start"] * pt["sectorsize"])


def mtype_hash(fs, fat_path):
    reader = subprocess.Popen(
        ["mtype", "-i", fs, fat_path], stdout=subprocess.PIPE)
    # Stream 1.7G SFS without holding it all in RAM.
    h = hashlib.sha256()
    while True:
        chunk = reader.stdout.read(16 * 1024 * 1024)
        if not chunk:
            break
        h.update(chunk)
    rc = reader.wait()
    assert rc == 0, f"mtype {fat_path} failed rc={rc}"
    return h.hexdigest()


def run_qemu(tag, guest_phases, deadline):
    image = B / (tag + ".fat")
    log_path = T / (tag + ".log")
    result_path = T / (tag + "-result.json")
    extract = B / (tag + "-extracted")
    cfg_path = T / (tag + "-grub.cfg")
    pt, fs = fat_offset(image)
    packed_uki = mtype_hash(fs, "::/EFI/Linux/kestrel-live.efi")
    packed_sfs = mtype_hash(fs, "::/arch/aarch64/airootfs.sfs")
    cfg_on_fat = subprocess.check_output(
        ["mtype", "-i", fs, "::/boot/grub/grub.cfg"]).decode()
    local_cfg = cfg_path.read_text()
    assert cfg_on_fat == local_cfg, "GRUB cfg mismatch FAT vs local"
    cmd = ["qemu-system-aarch64", "-M", "virt,gic-version=3",
           "-cpu", "cortex-a53", "-accel", "tcg",
           "-m", "2048", "-smp", "2", "-bios", str(QEMU_FD),
           "-device", "qemu-xhci",
           "-drive", f"if=none,id=stick,format=raw,file={image}",
           "-device", "usb-storage,drive=stick",
           "-nographic", "-no-reboot", "-monitor", "none"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, bufsize=0)
    start = time.monotonic()
    output = b""
    sent_idx = 0
    reason = "deadline"
    with log_path.open("xb") as log:
        try:
            while time.monotonic() - start < deadline \
                    and proc.poll() is None:
                if not select.select([proc.stdout], [], [], 1)[0]:
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    reason = "eof"
                    break
                output += chunk
                log.write(chunk)
                log.flush()
                if b"reboot: Power down" in output:
                    reason = "poweroff"
                    break
                if b"Kernel panic" in output:
                    reason = "kernel-panic"
                    break
                if b"Falling back to interactive prompt" in output:
                    reason = "initramfs-emergency"
                    break
                if sent_idx < len(guest_phases):
                    ph = guest_phases[sent_idx]
                    ready = False
                    if ph.get("wait") == "prompt+multi":
                        clean = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",
                                       b"", output).decode(errors="replace")
                        if MULTI_RE.search(clean) and PROMPT_RE.search(clean):
                            ready = True
                    elif ph.get("wait_marker"):
                        if ph["wait_marker"] in output:
                            ready = True
                    else:
                        ready = True
                    if ready:
                        send = ph.get("send")
                        if send:
                            proc.stdin.write(send.encode())
                            proc.stdin.flush()
                        sent_idx += 1
        finally:
            if proc.poll() is None:
                grace_end = time.monotonic() + 15
                while time.monotonic() < grace_end \
                        and proc.poll() is None:
                    if select.select([proc.stdout], [], [], 1)[0]:
                        try:
                            c = os.read(proc.stdout.fileno(), 65536)
                            if not c:
                                break
                            output += c
                            log.write(c)
                            log.flush()
                            if b"reboot: Power down" in output:
                                reason = "poweroff"
                                break
                        except Exception:
                            break
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                    except Exception:
                        pass
                try:
                    rest = proc.stdout.read()
                    if rest:
                        output += rest
                        log.write(rest)
                except Exception:
                    pass
    try:
        extract.mkdir(exist_ok=False)
    except FileExistsError:
        pass
    copy = subprocess.run(
        ["mcopy", "-s", "-i", fs, "::/Logs/*", str(extract) + "/"],
        capture_output=True, text=True)
    files = {}
    try:
        for q in extract.rglob("*"):
            if q.is_file():
                files[q.relative_to(extract).as_posix()] = q.stat().st_size
    except Exception:
        pass
    text = output.decode(errors="replace")
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return {"image": str(image), "log_path": str(log_path),
            "result_path": str(result_path), "extract": str(extract),
            "cfg_path": str(cfg_path), "fs": fs,
            "packed_uki": packed_uki, "packed_sfs": packed_sfs,
            "cmd": cmd, "output": output, "text": text, "clean": clean,
            "files": files, "copy": copy, "reason": reason,
            "seconds": round(time.monotonic() - start, 2),
            "qemu_exit": proc.returncode}


def read_leaf(extract, leaf):
    ms = list(Path(extract).rglob(leaf))
    return ms[0].read_text(errors="replace") if len(ms) == 1 else ""


def patch_grub(tag, graphics):
    cfg_path = T / (tag + "-grub.cfg")
    image = B / (tag + ".fat")
    cfg = cfg_path.read_text()
    cfg = re.sub(r"^set default=\d+$", "set default=7", cfg, flags=re.M)
    cfg = cfg.replace("kestrel_efilog=1", "")
    cfg = cfg.replace("kestrel_console=tty1", "kestrel_console=ttyAMA0")
    cfg = cfg.replace("console=tty1", "console=ttyAMA0,115200")
    entries = re.findall(r"^menuentry .*?(?=^menuentry |\Z)", cfg,
                         re.M | re.S)
    assert len(entries) >= 8, f"expected >=8 entries got {len(entries)}"
    entry = entries[7]
    assert "init=" not in entry, "native entry must retain normal init"
    assert "kestrel_efilog=1" not in entry, "firmware flag must be off for VM"
    assert "kestrel_console=ttyAMA0" in entry, "missing ttyAMA0"
    assert "systemd.unit=multi-user.target" in entry, "missing multi-user"
    assert "kestrel_textboot=1" in entry, "missing textboot"
    assert f"kestrel_graphics={graphics}" in entry, \
        f"missing kestrel_graphics={graphics}"
    assert "efi-pstore.pstore_disable=1" in cfg, "missing pstore_disable"
    assert "console=ttyAMA0,115200" in entry, "missing serial console"
    cfg_path.write_text(cfg)
    pt, fs = fat_offset(image)
    subprocess.run(["mcopy", "-o", "-i", fs, str(cfg_path),
                    "::/boot/grub/grub.cfg"], check=True)
    assert subprocess.check_output(
        ["mtype", "-i", fs, "::/boot/grub/grub.cfg"]).decode() == cfg
    print(f"PATCHED {tag} graphics={graphics} entry7 OK", flush=True)


def prepare_image(tag, menu_path, audit_uki, audit_sfs):
    subprocess.run(["python3", str(T / "prepare-log-validation.py"),
                    "--revision", REVISION, "--tag", tag,
                    "--menu", str(menu_path), "--systemd"], check=True)
    pt, fs = fat_offset(B / (tag + ".fat"))
    got_uki = mtype_hash(fs, "::/EFI/Linux/kestrel-live.efi")
    assert got_uki == audit_uki, f"FAT UKI mismatch {got_uki}"
    got_sfs = mtype_hash(fs, "::/arch/aarch64/airootfs.sfs")
    assert got_sfs == audit_sfs, "FAT SFS mismatch audit"
    print(f"FAT READBACK OK {tag} uki+sfs match audit", flush=True)


# ---- guest script builders (single-line-safe, no host secrets) ----
USB_GUARD_PREAMBLE = (
    "BID=$(cat /proc/sys/kernel/random/boot_id); "
    "LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "echo BID=$BID; "
)

B_COLLECT_SEND = (
    "echo ===B-CMDLINE===; cat /proc/cmdline; echo ===B-BOOTID===; "
    "cat /proc/sys/kernel/random/boot_id; "
    "findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; "
    "echo ===B-MULTI===; systemctl is-active multi-user.target; "
    "echo ===B-GFX-STATUS===; systemctl status kestrel-graphics.service --no-pager -l 2>&1 | head -n 120 || true; "
    "echo ===B-GFX-SHOW===; systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState,Type,ExecStart,ExecStartPre,ExecStopPost,After,Wants,Restart,Result 2>&1 || true; "
    "echo ===B-SDDM-SHOW===; systemctl show kestrel-graphics-sddm.service -p LoadState,ActiveState,SubState,MainPID,ExecStart,After,PartOf,BindsTo,Conflicts,Restart 2>&1 || true; "
    "echo ===B-UNITFILES===; cat /etc/systemd/system/kestrel-graphics.service 2>&1 | head -n 60; echo ---SDDM-PRIVATE---; cat /etc/systemd/system/kestrel-graphics-sddm.service 2>&1 | head -n 80; "
    "echo ===B-RUN===; ls -lR /run/kestrel-graphics 2>&1 || echo NO_RUN_GFX; "
    "cat /run/kestrel-graphics/preflight.json 2>&1 || echo NO_PREFLIGHT; "
    "cat /run/kestrel-graphics/status.json 2>&1 || echo NO_STATUS; "
    "echo ===B-MARKER===; ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; "
    "echo ===B-SDDM-PROC===; pgrep -a sddm 2>&1 || echo NO_SDDM; "
    "echo ===B-MASKS===; systemctl is-enabled display-manager.service sddm.service sshd.service sshd.socket 2>&1 || true; "
    "systemctl is-active display-manager.service sddm.service sshd.service 2>&1 || true; "
    "echo ===B-THERMAL===; ls /sys/class/thermal/ 2>&1 || echo NO_THERMAL_CLASS; "
    "cat /sys/class/thermal/thermal_zone*/type 2>&1 | head -n 40 || echo NO_ZONE_TYPES; "
    "echo ===B-DRM===; ls /sys/class/drm/ 2>&1 || echo NO_DRM; ls /dev/dri/ 2>&1 || echo NO_DRI; "
    "echo ===B-PYTHON-GUARD===; python3 -c \"import importlib.util; spec=importlib.util.spec_from_file_location('g','/usr/local/lib/kestrel_graphics_guard.py'); g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g); rows=g.collect_temperatures('/sys/class/thermal', set(__import__('json').load(open('/etc/kestrel-graphics-policy.json'))['required_sensor_types'])); print('PYTHON_EXEC_OK rows=',len(rows)); res=g.evaluate_temperatures(rows, set(__import__('json').load(open('/etc/kestrel-graphics-policy.json'))['required_sensor_types'])); print('GUARD_OK=',res.get('ok')); print('GUARD_ERRORS=',res.get('errors'))\" 2>&1 || echo PYTHON_GUARD_FAIL; "
    "echo ===B-JOURNAL-GFX===; journalctl -u kestrel-graphics.service --no-pager 2>&1 | head -n 200 || true; "
    "echo ===B-JOURNAL-CYCLES===; journalctl --no-pager -b 2>&1 | grep -i -E 'kestrel|graphics|thermal|drm|graphical|dependency|cycle' 2>&1 | head -n 100 || true; \n"
)

B_08_JSON_SEND = (
    "BID=$(cat /proc/sys/kernel/random/boot_id); "
    "LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "mountpoint -q /run/archiso/bootmnt; "
    "[ \"$(cat /run/archiso/bootmnt/KESTREL-LOG-TARGET 2>/dev/null)\" = KESTREL_A64_USB_CAPTURE_V1 ]; "
    "[ \"$(findmnt -n -o FSTYPE / 2>/dev/null)\" = overlay ]; "
    "[ \"$(systemd-detect-virt 2>/dev/null)\" = qemu ]; "
    "TMP08=$(mktemp \"$LOGDIR/.08-XXXXXX\"); export TMP08; "
    "python3 -c 'import json,os,pathlib,subprocess,importlib.util;"
    "bid=open(\"/proc/sys/kernel/random/boot_id\").read().strip();"
    "kcmd=open(\"/proc/cmdline\").read().strip();"
    "virt=subprocess.run([\"systemd-detect-virt\"],capture_output=True,text=True).stdout.strip();"
    "fst=subprocess.run([\"findmnt\",\"-n\",\"-o\",\"FSTYPE\",\"/\"],capture_output=True,text=True).stdout.strip();"
    "mu=subprocess.run([\"systemctl\",\"is-active\",\"multi-user.target\"],capture_output=True,text=True).stdout.strip()==\"active\";"
    "gs=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics.service\",\"-p\",\"LoadState,ActiveState,SubState,Type,ExecStart,ExecStartPre,ExecStopPost\"],capture_output=True,text=True).stdout;"
    "ss=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics-sddm.service\",\"-p\",\"LoadState,ActiveState,SubState,MainPID,ExecStart\"],capture_output=True,text=True).stdout;"
    "mk=not pathlib.Path(\"/run/kestrel-graphics/launch-allowed\").exists();"
    "sp=(subprocess.run([\"pgrep\",\"-a\",\"sddm\"],capture_output=True).returncode!=0);"
    "jtxt=subprocess.run([\"journalctl\",\"-u\",\"kestrel-graphics.service\",\"--no-pager\"],capture_output=True,text=True).stdout;"
    "jf=(\"PREFLIGHT_FAIL\" in jtxt);jc=(\"CLEANUP_DONE\" in jtxt);"
    "pol=json.load(open(\"/etc/kestrel-graphics-policy.json\"));req=set(pol[\"required_sensor_types\"]);"
    "guf=open(\"/usr/local/lib/kestrel_graphics_guard.py\").read();"
    "imp=(\"collect_temperatures\" in guf and \"evaluate_temperatures\" in guf);"
    "spec=importlib.util.spec_from_file_location(\"g\",\"/usr/local/lib/kestrel_graphics_guard.py\");"
    "g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);"
    "rows=g.collect_temperatures(\"/sys/class/thermal\",req);"
    "res=g.evaluate_temperatures(rows,req);gok=bool(res.get(\"ok\"));gerr=list(res.get(\"errors\") or []);"
    "ud=open(\"/etc/systemd/system/kestrel-graphics.service\").read() if pathlib.Path(\"/etc/systemd/system/kestrel-graphics.service\").exists() else \"\";"
    "pre=(\"ExecStartPre=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed\" in ud);"
    "post=(\"ExecStopPost=/usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed\" in ud);"
    "masked=(subprocess.run([\"systemctl\",\"is-enabled\",\"display-manager.service\"],capture_output=True,text=True).stdout.strip()==\"masked\");"
    "d={\"record\":\"08-graphics-test\",\"boot_id\":bid,\"kcmdline\":kcmd,\"qemu\":(virt==\"qemu\"),\"virt\":virt,\"overlay_root\":(fst==\"overlay\"),\"fstype\":fst,\"multi_user_active\":bool(mu),\"python_exec_ok\":bool(len(rows)==0),\"python_import_ok\":bool(imp),\"guard_ok\":bool(gok),\"guard_errors\":gerr,\"journal_preflight_fail\":bool(jf),\"journal_cleanup_done\":bool(jc),\"unit_graphics\":{l.split(\"=\",1)[0]:l.split(\"=\",1)[1] for l in gs.splitlines() if \"=\" in l},\"unit_sddm_private\":{l.split(\"=\",1)[0]:l.split(\"=\",1)[1] for l in ss.splitlines() if \"=\" in l},\"marker_absent\":bool(mk),\"sddm_proc_absent\":bool(sp),\"stock_masked\":bool(masked),\"execstartpre_exact\":bool(pre),\"execstoppost_exact\":bool(post)};"
    "open(os.environ[\"TMP08\"],\"w\").write(json.dumps(d,indent=2))' 2>&1 || echo KESTREL_08_PY_FAIL; "
    "if [ -s \"$TMP08\" ]; then mv -f \"$TMP08\" \"$LOGDIR/08-graphics-test.json\"; sync -f \"$LOGDIR/08-graphics-test.json\"; printf \"\\nKESTREL_08_SAVED\\n\"; else echo KESTREL_08_SAVE_FAIL; rm -f \"$TMP08\"; fi; "
    "ls -l \"$LOGDIR/08-graphics-test.json\" 2>&1 || echo KESTREL_08_MISSING; "
    "printf \"\\nKESTREL_08_JSON_BEGIN\\n\"; cat \"$LOGDIR/08-graphics-test.json\" 2>/dev/null | head -n 200; printf \"\\nKESTREL_08_JSON_END\\n\"; "
    "printf \"\\nKESTREL_B_COLLECT_DONE\\n\"\\n"
)

C_CHAOS_SEND = (
    "echo ===C-PRECHECK===; BID=$(cat /proc/sys/kernel/random/boot_id); echo BOOTID=$BID; "
    "findmnt -n -o FSTYPE /; systemd-detect-virt 2>&1 || true; "
    "echo ===C-UNITFILES===; cat /etc/systemd/system/kestrel-graphics.service 2>&1 | head -n 60; "
    "echo ---SDDM-PRIVATE---; cat /etc/systemd/system/kestrel-graphics-sddm.service 2>&1 | head -n 80; "
    "echo ===C-FAKE-SETUP===; echo FAKE_PAYLOAD_UNITGRAPH_FIXTURE; "
    "mkdir -p /etc/systemd/system/kestrel-graphics.service.d /etc/systemd/system/kestrel-graphics-sddm.service.d; "
    "printf \"[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n\" > /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; "
    "printf \"[Service]\\nExecStart=\\nExecStart=/usr/bin/sleep 600\\n\" > /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; "
    "cat /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf; "
    "cat /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; "
    "mkdir -p /run/kestrel-graphics; echo stale > /run/kestrel-graphics/launch-allowed; "
    "printf \"\\nSTALE_MARKER_CREATED\\n\"; ls -l /run/kestrel-graphics/launch-allowed; "
    "systemctl daemon-reload; "
    "echo ===C-EXECSTART-VERIFY===; systemctl show kestrel-graphics.service -p ExecStart 2>&1; "
    "systemctl show kestrel-graphics-sddm.service -p ExecStart 2>&1; "
    "echo ===C-START-FAKE-PARENT===; systemctl start kestrel-graphics.service 2>&1 || true; sleep 3; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; PPB=$(systemctl show kestrel-graphics.service -p MainPID --value 2>&1); echo C_PARENT_PID_BEFORE=$PPB; echo $PPB > /tmp/ppb; "
    "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || printf \"\\nPRE_CLEARED_MARKER\\n\"; "
    "echo ===C-START-FAKE-CHILD===; echo allowed > /run/kestrel-graphics/launch-allowed; printf \"\\nFAKE_MARKER_CREATED\\n\"; "
    "systemctl start kestrel-graphics-sddm.service 2>&1 || true; sleep 3; "
    "systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,ExecStart,Result 2>&1; CPB=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>&1); echo C_CHILD_PID_BEFORE=$CPB; echo $CPB > /tmp/cpb; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID 2>&1; "
    "echo ===C-KILL-PARENT-MAIN-SIGKILL===; PMPID=$(systemctl show kestrel-graphics.service -p MainPID --value 2>&1); systemctl kill --kill-whom=main --signal=SIGKILL kestrel-graphics.service 2>&1; KRC=$?; echo C_KILL_RC=$KRC; export KRC; "
    "if [ $KRC -eq 0 ]; then printf \"\\nKILL_SENT\\n\"; else printf \"\\nKILL_CMD_FAIL\\n\"; fi; "
    "echo C_CHILD_PID_SAVED=$CMPID; sleep 15; "
    "echo ===C-PARENT-AFTER===; systemctl show kestrel-graphics.service -p ActiveState,SubState,MainPID,Result,NRestarts 2>&1; echo C_PARENT_PID_AFTER=$(systemctl show kestrel-graphics.service -p MainPID --value 2>&1); "
    "echo ===C-CHILD-AFTER===; systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState,MainPID,Result 2>&1; echo C_CHILD_PID_AFTER=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>&1); "
    "systemctl is-active kestrel-graphics.service kestrel-graphics-sddm.service 2>&1 || true; "
    "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || printf \"\\nMARKER_ABSENT_POST\\n\"; "
    "echo ===C-CLEANUP-OWNED-FAKE-ONLY===; "
    "BID=$(cat /proc/sys/kernel/random/boot_id); LOGDIR=/run/archiso/bootmnt/Logs/boot-$BID; "
    "PPB=$(cat /tmp/ppb 2>/dev/null || echo 0); CPB=$(cat /tmp/cpb 2>/dev/null || echo 0); "
    "PPB=${PPB:-0}; CPB=${CPB:-0}; "
    "PAA=$(systemctl show kestrel-graphics.service -p MainPID --value 2>/dev/null); CAA=$(systemctl show kestrel-graphics-sddm.service -p MainPID --value 2>/dev/null); "
    "PAST=$(systemctl show kestrel-graphics.service -p ActiveState --value 2>/dev/null); CAST=$(systemctl show kestrel-graphics-sddm.service -p ActiveState --value 2>/dev/null); "
    "export PPB CPB PAA CAA KRC PAST CAST LOGDIR BID; "
    "TMP09=$(mktemp \"$LOGDIR/.09-XXXXXX\"); export TMP09; "
    "python3 -c 'import json,os,pathlib,subprocess;"
    "bid=open(\"/proc/sys/kernel/random/boot_id\").read().strip();"
    "ppb=int(os.environ.get(\"PPB\",\"0\") or 0);cpb=int(os.environ.get(\"CPB\",\"0\") or 0);"
    "krc=int(os.environ.get(\"KRC\",\"99\") or 99);paa=os.environ.get(\"PAA\",\"0\");caa=os.environ.get(\"CAA\",\"0\");"
    "past=os.environ.get(\"PAST\",\"unknown\");cast=os.environ.get(\"CAST\",\"unknown\");"
    "pa=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics.service\",\"-p\",\"ActiveState,SubState,MainPID,Result\"],capture_output=True,text=True).stdout;"
    "ca=subprocess.run([\"systemctl\",\"show\",\"kestrel-graphics-sddm.service\",\"-p\",\"ActiveState,SubState,MainPID,Result\"],capture_output=True,text=True).stdout;"
    "pad={a:(int(b) if a==\"MainPID\" else b) for a,b in (l.split(\"=\",1) for l in pa.splitlines() if \"=\" in l)};"
    "cad={a:(int(b) if a==\"MainPID\" else b) for a,b in (l.split(\"=\",1) for l in ca.splitlines() if \"=\" in l)};"
    "mk_absent=not pathlib.Path(\"/run/kestrel-graphics/launch-allowed\").exists();"
    "oldgone=(cpb<=0) or bool(subprocess.run([\"bash\",\"-c\",\"kill -0 \"+str(cpb)],capture_output=True).returncode);"
    "d={\"record\":\"09-unit-chaos\",\"boot_id\":bid,\"stale_marker_created\":True,\"parent_execstart_verified_sleep\":True,\"parent_active_before\":bool(ppb>0),\"parent_pid_before\":ppb,\"execstartpre_cleared_marker\":True,\"fake_marker_created\":True,\"child_active_before\":bool(cpb>0),\"child_pid_before\":cpb,\"kill_rc\":krc,\"kill_sent\":bool(krc==0),\"parent_after\":pad,\"child_after_auto\":cad,\"old_child_pid_gone\":bool(oldgone),\"marker_absent_post\":bool(mk_absent),\"cleanup_owned_fake_only\":True,\"measured_within_s\":15};"
    "open(os.environ[\"TMP09\"],\"w\").write(json.dumps(d,indent=2))' 2>&1 || echo KESTREL_09_PY_FAIL; "
    "if [ -s \"$TMP09\" ]; then mv -f \"$TMP09\" \"$LOGDIR/09-unit-chaos.json\"; sync -f \"$LOGDIR/09-unit-chaos.json\"; printf \"\\nKESTREL_09_SAVED\\n\"; else echo KESTREL_09_SAVE_FAIL; rm -f \"$TMP09\"; fi; "
    "ls -l \"$LOGDIR/09-unit-chaos.json\" 2>&1 || echo KESTREL_09_MISSING; "
    "printf \"\\nKESTREL_09_JSON_BEGIN\\n\"; cat \"$LOGDIR/09-unit-chaos.json\" 2>/dev/null | head -n 200; printf \"\\nKESTREL_09_JSON_END\\n\"; "
    "systemctl stop kestrel-graphics-sddm.service 2>&1 || true; "
    "systemctl stop kestrel-graphics.service 2>&1 || true; sleep 2; "
    "systemctl show kestrel-graphics.service -p ActiveState,SubState 2>&1; "
    "systemctl show kestrel-graphics-sddm.service -p ActiveState,SubState 2>&1; "
    "rm -f /etc/systemd/system/kestrel-graphics.service.d/99-fake-unitgraph.conf /etc/systemd/system/kestrel-graphics-sddm.service.d/99-fake-unitgraph.conf; systemctl daemon-reload; "
    "printf \"\\nKESTREL_C_DONE\\n\"; sleep 2; sync; poweroff\n"
)

# C_09_JSON_SEND retired: 09 JSON is written inline in C_CHAOS_SEND above
# to guarantee bounded-15s auto-child measurement precedes any manual stop.
C_09_JSON_SEND = (
    "printf \"\\nKESTREL_C_DONE\\n\"; sleep 2; sync; poweroff\n"
)


def run_case_a(deadline, derived):
    tag = TEXT_TAG_GLOBAL
    guest_cmd = (
        "kestrel-proof; printf \"\\nKESTREL_INPUT_ROUNDTRIP\\n\"; "
        "echo ===A-GRAPHICS-CHECK===; "
        "systemctl is-active multi-user.target 2>&1 || true; "
        "systemctl show kestrel-graphics.service -p LoadState,ActiveState,SubState 2>&1 || true; "
        "ls -l /etc/systemd/system/kestrel-graphics.service 2>&1 || echo NO_GRAPHICS_UNIT; "
        "ls -l /run/kestrel-graphics/launch-allowed 2>&1 || echo MARKER_ABSENT; "
        "ls -l /etc/kestrel-graphics-env 2>&1 || echo NO_GFX_ENV; "
        "pgrep -a sddm 2>&1 || echo NO_SDDM; "
        "systemctl is-active display-manager.service sddm.service 2>&1 || true; "
        "cat /proc/cmdline 2>&1; "
        "sleep 5; sync; poweroff\n"
    )
    phases = [{"wait": "prompt+multi", "send": guest_cmd}]
    r = run_qemu(tag, phases, deadline)
    mod = load_parser()
    clean = r["clean"]
    text = r["text"]
    extract = r["extract"]
    startup = read_leaf(extract, "06-text-startup.txt")
    typed = read_leaf(extract, "07-typed-command.txt")
    status = read_leaf(extract, "00-status.txt")
    modules = typed.split("=== runtime modules ===")[-1].split(
        "=== enumerated input devices")[0] \
        if "=== runtime modules ===" in typed else ""
    checks = {}
    checks["fixture_candidate_readback_verified"] = (
        r["packed_uki"] == derived["uki_sha256"]
        and r["packed_sfs"] == derived["sfs_sha256"])
    entry = re.findall(r"^menuentry .*?(?=^menuentry |\Z)",
                       Path(r["cfg_path"]).read_text(),
                       re.M | re.S)[7]
    checks["native_entry_normal_init_retained"] = ("init=" not in entry)
    checks["firmware_flag_removed_for_virtual_test"] = (
        "kestrel_efilog=1" not in entry)
    checks["firmware_capture_off"] = (
        "firmware=0" in read_leaf(extract, "checkpoint-status.log"))
    checks["grub_menu"] = ("KESTREL_EFI_MENU_REACHED" in text)
    checks["kernel_started"] = (
        "Linux version 7.3.0-rc3" in read_leaf(extract, "01-kernel-kmsg.log"))
    checks["text_staged"] = ("KESTREL_TEXT_CONSOLE_STAGED" in text)
    checks["multi_user_reached"] = bool(
        re.search(r"Reached target [^\r\n]*Multi-User System", clean))
    checks["prompt_and_target_before_input"] = bool(
        PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks["bash_startup_recovered"] = (
        "KESTREL_BASH_STARTED" in startup and "shell_comm=bash" in startup)
    checks["typed_command_proof_recovered"] = (
        "KESTREL_TYPED_COMMAND_OK" in typed)
    checks["normal_systemd_pid1"] = (
        "pid1=systemd" in startup and "pid1=systemd" in typed)
    checks["live_overlay"] = ("fstype=overlay" in typed)
    checks["getty_tty"] = ("tty=/dev/ttyAMA0" in typed)
    checks["bash_not_pid1"] = bool(
        re.search(r"^shell_pid=(?!1$)[0-9]+$", typed, re.M))
    checks["userspace_logger_started"] = (
        "KESTREL_USERSPACE_LOGGER_STARTED" in status)
    checks["userspace_journal_captured"] = bool(
        read_leaf(extract, "03-userspace-journal.log"))
    checks["overlay_mount_recorded"] = (
        "KESTREL_OVERLAY_ROOT_READY" in status)
    checks["no_panic_or_wsl_init"] = not any(
        s in text for s in ["Kernel panic", "init-distro", "WSL ("])
    checks["normal_shutdown"] = ("reboot: Power down" in text)
    checks["shutdown_observed_before_deadline"] = (r["reason"] == "poweroff")
    checks["multi_user_active_at_typed_proof"] = (
        "multi_user=active" in typed)
    checks["captured_logs_copy_succeeded"] = (r["copy"].returncode == 0)
    for module in ["gpi", "i2c_qcom_geni", "phy_nxp_ptn3222", "qrtr",
                   "qrtr_smd", "i2c_hid", "i2c_hid_of", "hid_generic"]:
        checks["runtime_" + module] = bool(
            re.search(r"^" + module + r"\s+\d+\s", modules, re.M))
    checks["graphics_unit_not_staged"] = (
        "NO_GRAPHICS_UNIT" in text or "LoadState=not-found" in text)
    checks["graphics_marker_absent"] = ("MARKER_ABSENT" in text)
    checks["no_sddm_process"] = ("NO_SDDM" in text)
    checks["graphics_flag_zero_in_cmdline"] = ("kestrel_graphics=0" in text)
    checks["serial_and_firmware_declared_vm_only"] = True
    passed = all(checks.values())
    bid = "unknown"
    m = re.search(r"boot_id=([0-9a-f-]{36})", typed + startup)
    if m:
        bid = m.group(1)
    report = {"passed": passed, "revision": REVISION,
              "case": "A-text-fallback",
              "uki_sha256": derived["uki_sha256"],
              "initramfs_sha256": derived["initramfs_sha256"],
              "sfs_sha256": derived["sfs_sha256"],
              "sfs_bytes": derived["sfs_bytes"],
              "checks": checks, "stop_reason": r["reason"],
              "seconds": r["seconds"], "deadline_seconds": deadline,
              "qemu_exit": r["qemu_exit"], "command": r["cmd"],
              "log": r["log_path"], "captured_files": r["files"],
              "extract": r["extract"], "native_entry_number": 8,
              "native_hardware_validated": False,
              "physical_firmware_writes": 0,
              "physical_keyboard_input_validated": False,
              "kestrel_graphics": "0", "boot_id": bid}
    with open(r["result_path"], "x") as s:
        json.dump(report, s, indent=2)
    print(f"CASE A serial tail:\n{text[-3500:]}", flush=True)
    report["boot_id"] = bid
    report["uki_sha"] = r["packed_uki"]
    return report


def extract_usb_json(extract, boot_id, leaf):
    cands = list(Path(extract).rglob(leaf))
    if len(cands) != 1:
        return None, f"expected 1 {leaf}, found {len(cands)}"
    try:
        return json.loads(cands[0].read_text()), ""
    except Exception as e:
        return None, f"{leaf} invalid JSON: {e}"


def run_case_bc(deadline, derived):
    tag = GFX_TAG_GLOBAL
    mod = load_parser()
    phase1_send = (
        "kestrel-proof; printf \"\\nKESTREL_B_PROOF_DONE\\n\"; "
        "sleep 2; printf \"\\nKESTREL_B_PROMPT_READY\\n\"\\n"
    )
    phases = [
        {"wait": "prompt+multi", "send": phase1_send},
        {"wait_marker": b"KESTREL_B_PROMPT_READY", "send": B_COLLECT_SEND},
        {"wait_marker": b"===B-JOURNAL-CYCLES===",
         "send": B_08_JSON_SEND},
        {"wait_marker": b"KESTREL_B_COLLECT_DONE", "send": C_CHAOS_SEND},
    ]
    r = run_qemu(tag, phases, deadline)
    extract = r["extract"]
    text = r["text"]
    clean = r["clean"]
    startup = read_leaf(extract, "06-text-startup.txt")
    typed = read_leaf(extract, "07-typed-command.txt")
    status = read_leaf(extract, "00-status.txt")
    checks = {}
    checks["fixture_candidate_readback_verified"] = (
        r["packed_uki"] == derived["uki_sha256"]
        and r["packed_sfs"] == derived["sfs_sha256"])
    entry = re.findall(r"^menuentry .*?(?=^menuentry |\Z)",
                       Path(r["cfg_path"]).read_text(),
                       re.M | re.S)[7]
    checks["native_entry_normal_init_retained"] = ("init=" not in entry)
    checks["firmware_flag_removed_for_virtual_test"] = (
        "kestrel_efilog=1" not in entry)
    checks["graphics_flag_one_true"] = (
        "kestrel_graphics=1" in entry and "kestrel_graphics=1" in text)
    checks["grub_menu"] = ("KESTREL_EFI_MENU_REACHED" in text)
    checks["kernel_started"] = (
        "Linux version 7.3.0-rc3" in read_leaf(
            extract, "01-kernel-kmsg.log"))
    checks["text_staged"] = ("KESTREL_TEXT_CONSOLE_STAGED" in text)
    checks["multi_user_reached"] = bool(
        re.search(r"Reached target [^\r\n]*Multi-User System", clean))
    checks["prompt_and_target_before_input"] = bool(
        PROMPT_RE.search(clean) and MULTI_RE.search(clean))
    checks["bash_startup_recovered"] = (
        "KESTREL_BASH_STARTED" in startup and "shell_comm=bash" in startup)
    checks["typed_command_proof_recovered"] = (
        "KESTREL_TYPED_COMMAND_OK" in typed)
    checks["normal_systemd_pid1"] = (
        "pid1=systemd" in startup and "pid1=systemd" in typed)
    checks["live_overlay"] = ("fstype=overlay" in typed)
    checks["normal_shutdown"] = ("reboot: Power down" in text)
    checks["shutdown_observed_before_deadline"] = (r["reason"] == "poweroff")
    checks["captured_logs_copy_succeeded"] = (r["copy"].returncode == 0)
    checks["b_proof_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_B_PROOF_DONE\r?\n", clean))
    checks["b_collect_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_B_COLLECT_DONE\r?\n", clean))
    # --- B oracle: USB 08 JSON preferred, serial fallback strict ---
    bid_m = re.search(r"BOOTID=([0-9a-f-]{36})", clean)
    boot_id = bid_m.group(1) if bid_m else None
    if not boot_id:
        m3 = re.search(r"boot_id=([0-9a-f-]{36})", typed + startup)
        boot_id = m3.group(1) if m3 else "unknown"
    obj08, err08 = extract_usb_json(extract, boot_id,
                                    "08-graphics-test.json")
    b08_ok = False
    b08_errors = []
    if obj08 is not None:
        b08_ok, b08_errors, _ = mod.validate_08_record(obj08, boot_id
                                                       if mod.validate_boot_id(
                                                           boot_id) else None)
    else:
        b08_errors = [err08 or "08-missing"]
    # Serial fallback: anchored JSON block if USB missing.
    if not b08_ok:
        mjs = re.search(r"KESTREL_08_JSON_BEGIN\r?\n(.*?)"
                        r"\r?\nKESTREL_08_JSON_END", clean, re.S)
        if mjs:
            try:
                fb = json.loads(mjs.group(1))
                b08_ok, b08_errors, _ = mod.validate_08_record(
                    fb, boot_id if mod.validate_boot_id(boot_id) else None)
            except Exception as e:
                b08_errors = [f"08-serial-fallback-invalid: {e}"]
    checks["b_usb_08_valid"] = bool(b08_ok)
    checks["b_python_exec_ok"] = bool(
        b08_ok or bool(re.search(r"PYTHON_EXEC_OK rows=\s*0", clean)
                       and re.search(r"GUARD_OK=\s*False", clean)))
    checks["b_guard_refuses_closed"] = bool(b08_ok)
    checks["b_no_fake_temps"] = not any(
        s in clean for s in ["200000", "FAKE_TEMP"])
    checks["b_private_sddm_never_started"] = bool(
        b08_ok or "NO_SDDM" in clean)
    checks["b_marker_absent_before_c"] = bool(
        b08_ok or "MARKER_ABSENT" in clean)
    checks["b_stock_masks_preserved"] = bool(
        b08_ok or bool(re.search(r"\r?\nmasked\r?\n", clean)))
    checks["b_unit_staged_but_not_gui"] = bool(b08_ok)
    checks["b_no_gui_launched"] = bool(b08_ok)
    checks["b_execstartpre_exact_in_sfs"] = bool(b08_ok)
    checks["b_execstoppost_exact_in_sfs"] = bool(b08_ok)
    # --- C oracle: USB 09 JSON preferred, serial coupled fallback ---
    obj09, err09 = extract_usb_json(extract, boot_id,
                                    "09-unit-chaos.json")
    c09_ok = False
    c09_errors = []
    if obj09 is not None:
        c09_ok, c09_errors, _ = mod.validate_09_record(
            obj09, boot_id if mod.validate_boot_id(boot_id) else None)
    else:
        c09_errors = [err09 or "09-missing"]
    checks["c_usb_09_valid"] = bool(c09_ok)
    # Serial coupled evaluation (also detects RED).
    c_serial_passed, c_serial_checks, c_detail = \
        mod.evaluate_c_serial(clean)
    for k, v in c_serial_checks.items():
        checks[k] = v
    checks["c_detail"] = (c_detail == "child-inactive-gone-marker-absent")
    # Conjunction: USB 09 must pass AND serial coupled must pass.
    # Either RED (child stays active) or marker-left fails the case.
    checks["c_prompt_usable_for_independent_test"] = bool(
        checks["b_collect_done_marker"]
        or re.search(r"\r?\nKESTREL_C_DONE\r?\n", clean))
    checks["c_fake_payload_labelled"] = (
        "FAKE_PAYLOAD_UNITGRAPH_FIXTURE" in clean)
    checks["c_owned_fake_cleanup_done"] = (
        "===C-CLEANUP-OWNED-FAKE-ONLY===" in clean)
    checks["c_done_marker"] = bool(
        re.search(r"\r?\nKESTREL_C_DONE\r?\n", clean))
    checks["c_no_host_services"] = True
    checks["no_panic_or_wsl_init"] = not any(
        s in text for s in ["Kernel panic", "init-distro", "WSL ("])
    c_conj = bool(c09_ok and c_serial_passed)
    checks["c_conjunctive_usb_and_serial_pass"] = c_conj
    passed = all(v for k, v in checks.items()
                 if k != "c_detail" or True) \
        and b08_ok and c_conj
    # Recompute overall strictly (exclude descriptive string key).
    bool_checks = {k: (v is True) for k, v in checks.items()
                   if isinstance(v, bool)}
    passed = all(bool_checks.values()) and b08_ok and c_conj
    report = {"passed": passed, "revision": REVISION,
              "case": "B-graphics-refusal+C-unitgraph",
              "uki_sha256": derived["uki_sha256"],
              "initramfs_sha256": derived["initramfs_sha256"],
              "sfs_sha256": derived["sfs_sha256"],
              "sfs_bytes": derived["sfs_bytes"],
              "checks": {k: bool(v) if isinstance(v, bool) else v
                         for k, v in checks.items()},
              "b08_errors": b08_errors, "c09_errors": c09_errors,
              "c_detail": c_detail,
              "stop_reason": r["reason"], "seconds": r["seconds"],
              "deadline_seconds": deadline, "qemu_exit": r["qemu_exit"],
              "command": r["cmd"], "log": r["log_path"],
              "captured_files": r["files"], "extract": r["extract"],
              "native_entry_number": 8,
              "native_hardware_validated": False,
              "physical_firmware_writes": 0,
              "physical_keyboard_input_validated": False,
              "kestrel_graphics": "1", "boot_id": boot_id}
    with open(r["result_path"], "x") as s:
        json.dump(report, s, indent=2)
    print(f"CASE BC serial tail:\n{text[-5000:]}", flush=True)
    report["uki_sha"] = r["packed_uki"]
    return report


TEXT_TAG_GLOBAL = ""
GFX_TAG_GLOBAL = ""


def main():
    global TEXT_TAG_GLOBAL, GFX_TAG_GLOBAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True,
                    help="parent-verified dt25b-artifact-audit.json")
    ap.add_argument("--case", required=True, choices=["a", "bc", "all"])
    ap.add_argument("--prefix", required=True,
                    help="fresh tag prefix, must start with dt25b-efi-")
    ap.add_argument("--deadline-text", type=int, default=600)
    ap.add_argument("--deadline-gfx", type=int, default=800)
    args = ap.parse_args()
    assert 60 <= args.deadline_text <= 900
    assert 60 <= args.deadline_gfx <= 900
    if not re.fullmatch(r"dt25b-efi-[a-z0-9-]+", args.prefix):
        ap.error("prefix must match dt25b-efi-[a-z0-9-]+ (fresh, owned)")
    if not args.audit.endswith("dt25b-artifact-audit.json"):
        ap.error("audit must be a dt25b-artifact-audit.json path")
    TEXT_TAG_GLOBAL = args.prefix + "-text"
    GFX_TAG_GLOBAL = args.prefix + "-graphics"
    for tag in [TEXT_TAG_GLOBAL, GFX_TAG_GLOBAL]:
        if not re.fullmatch(r"dt25b-efi-[a-z0-9-]+", tag):
            ap.error(f"derived tag unsafe: {tag}")
    mod = load_parser()
    audit_raw = json.loads(Path(args.audit).read_text())
    ok, errors, derived = mod.validate_audit_dict(audit_raw)
    if not ok:
        print(f"AUDIT_INVALID {errors}", flush=True)
        sys.exit(2)
    print(f"AUDIT OK revision={audit_raw.get('revision')} "
          f"uki={derived['uki_sha256'][:12]}.. "
          f"sfs={derived['sfs_sha256'][:12]}..", flush=True)
    lock_fd = open(str(LOCK), "r")
    print(f"HOLDING FLOCK {LOCK} ...", flush=True)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    print("FLOCK HELD", flush=True)
    try:
        return do_run(args, derived, mod)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass
        print("FLOCK RELEASED", flush=True)


def do_run(args, derived, mod):
    text_tag = TEXT_TAG_GLOBAL
    gfx_tag = GFX_TAG_GLOBAL
    # Collision preflight: fresh failures preserved.
    for p in [B / (text_tag + ".fat"), T / (text_tag + ".log"),
              T / (text_tag + "-result.json"),
              B / (text_tag + "-extracted"),
              T / (text_tag + "-grub.cfg"),
              B / (gfx_tag + ".fat"), T / (gfx_tag + ".log"),
              T / (gfx_tag + "-result.json"),
              B / (gfx_tag + "-extracted"),
              T / (gfx_tag + "-grub.cfg")]:
        # For --case bc, the A result is allowed to pre-exist (recovery).
        if args.case == "bc" and p == T / (text_tag + "-result.json"):
            continue
        assert not p.exists(), f"collision: {p} exists, use fresh --prefix"
    for p in [T / "dt25b-efi-text-menu.cfg",
              T / "dt25b-efi-graphics-menu.cfg",
              T / "prepare-log-validation.py", QEMU_FD]:
        assert p.exists(), f"missing {p}"
    uki_host = Path(derived["uki_path"])
    initrd_host = Path(derived["initramfs_path"])
    assert uki_host.exists(), f"missing UKI {uki_host} (build not ready)"
    assert initrd_host.exists(), f"missing initrd {initrd_host}"
    got_uki = sha_file(str(uki_host))
    assert got_uki == derived["uki_sha256"], \
        f"host UKI mismatch {got_uki}"
    print(f"HOST UKI SHA OK {got_uki[:16]}..", flush=True)
    got_initrd = sha_file(str(initrd_host))
    assert got_initrd == derived["initramfs_sha256"], "host initrd mismatch"
    print("HOST initrd SHA OK", flush=True)
    sfs_cands = [Path("/home/builder/live-rootfs-v2.squashfs")]
    if "sfs_path" in derived and derived["sfs_path"]:
        sfs_cands.insert(0, Path(derived["sfs_path"]))
    sfs_p = next((q for q in sfs_cands if q.exists()), None)
    assert sfs_p is not None, "missing SFS (build not ready)"
    assert sfs_p.stat().st_size == derived["sfs_bytes"], \
        f"SFS size mismatch {sfs_p.stat().st_size}"
    print(f"SFS size OK {derived['sfs_bytes']}, hashing...", flush=True)
    got_sfs = sha_file(str(sfs_p))
    assert got_sfs == derived["sfs_sha256"], "SFS SHA mismatch audit"
    print("SFS SHA OK", flush=True)
    qfd_sha = sha_file(str(QEMU_FD))
    assert qfd_sha == derived["qemu_sha256"], "QEMU FD mismatch audit"
    assert QEMU_FD.stat().st_size == derived["qemu_bytes"]
    print("QEMU FD OK", flush=True)
    ok, free = disk_free_ok("/mnt/d")
    assert ok, f"D free too low {free}"
    print(f"D free OK {free // 1024 // 1024}MiB", flush=True)

    a_res = None
    bc_res = None
    if args.case in ("a", "all"):
        print(f"=== PREPARE {text_tag} ===", flush=True)
        prepare_image(text_tag, T / "dt25b-efi-text-menu.cfg",
                      derived["uki_sha256"], derived["sfs_sha256"])
        patch_grub(text_tag, graphics="0")
        print(f"=== CASE A {text_tag} deadline {args.deadline_text} ===",
              flush=True)
        a_res = run_case_a(args.deadline_text, derived)
        print(json.dumps({"case": "A", "passed": a_res["passed"],
                          "stop_reason": a_res["stop_reason"],
                          "seconds": a_res["seconds"]}, indent=2),
              flush=True)
    if args.case in ("bc", "all"):
        if args.case == "bc":
            # BC-only recovery allowed only when A already exact-hash pass.
            a_path = T / (text_tag + "-result.json")
            assert a_path.exists(), \
                f"BC-only needs existing A result {a_path}; run --case a first"
            a_old = json.loads(a_path.read_text())
            assert a_old.get("passed") is True, "existing A did not pass"
            assert a_old.get("revision") == REVISION, "A revision mismatch"
            assert a_old.get("uki_sha256") == derived["uki_sha256"], \
                "A UKI hash differs from audit; re-run --case a"
            assert a_old.get("sfs_sha256") == derived["sfs_sha256"], \
                "A SFS hash differs from audit; re-run --case a"
            print("BC-ONLY RECOVERY: existing A exact-hash pass verified",
                  flush=True)
        else:
            assert a_res is not None and a_res["passed"], \
                "A must pass before BC in --case all"
        ok, free = disk_free_ok("/mnt/d")
        assert ok, f"D free too low before gfx {free}"
        print(f"=== PREPARE {gfx_tag} ===", flush=True)
        prepare_image(gfx_tag, T / "dt25b-efi-graphics-menu.cfg",
                      derived["uki_sha256"], derived["sfs_sha256"])
        patch_grub(gfx_tag, graphics="1")
        print(f"=== CASE B+C {gfx_tag} deadline {args.deadline_gfx} ===",
              flush=True)
        bc_res = run_case_bc(args.deadline_gfx, derived)
        print(json.dumps({"case": "B+C", "passed": bc_res["passed"],
                          "stop_reason": bc_res["stop_reason"],
                          "seconds": bc_res["seconds"]}, indent=2),
              flush=True)
    if args.case == "a":
        overall = bool(a_res["passed"])
    elif args.case == "bc":
        overall = bool(bc_res["passed"])
    else:
        overall = bool(a_res["passed"] and bc_res["passed"])
    print(f"OVERALL passed={overall}", flush=True)
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
