#!/usr/bin/env python3
"""Gate dt25 provenance, graphics closure, DT scope and unchanged logger/SFS.

- PE sections: new .linux/.text/.hwids/base cmdline/.uname equal dt24;
  new .dtbauto == accepted DT25; new .initrd == built image.
- Old fallback UKI+SFS hashes unchanged.
- Re-runs board52 gate with fresh result, real guard20 policy + USB/I2C gates.
- Snapshots candidate source hashes + explicit SFS closure.
- Only after pass writes fresh dt25-candidate.efi + dt25-artifact-audit.json.
- NOT native validated.
"""
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

P = Path("/mnt/d/CachyOS-ARM64")
T = P / "testing/boot-failure"
K = Path("/home/builder/src/ksrc")
OUT = Path("/home/builder/uki-v2-dt25")
OLD_OUT = Path("/home/builder/uki-v2-dt24")
SFS = Path("/mnt/d/CachyOS-ARM64/live-staging-v2/arch/aarch64/airootfs.sfs")
ROOT = Path("/home/builder/imgroot")

EXP_OLD_UKI_SHA = "4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02"
EXP_SFS_SHA = "5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c"
EXP_SFS_SIZE = 1748525056
EXP_IMAGE_SHA = "682273a91f2016b9d5484857639bd043e021b961d7f4cfd385a09566b2df3abc"
EXP_NEW_DTB_SHA = "f5f67c13bdfe975998b083ac06465c36231c0bae205e8e60fff99832264f5232"
EXP_NEW_DTB_SIZE = 207772
EXP_QEMU_SHA = "a996c72d5258dabf5fcb11a64bd22e0cc6673e3d193031feea02ac643f16dad5"


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sections(path):
    data = Path(path).read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe : pe + 4] == b"PE\0\0"
    machine, count = struct.unpack_from("<HH", data, pe + 4)
    assert machine == 0xAA64
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    result = {}
    for i in range(count):
        off = pe + 24 + opt + 40 * i
        name = data[off : off + 8].rstrip(b"\0").decode()
        size = struct.unpack_from("<I", data, off + 8)[0]
        raw_size, ptr = struct.unpack_from("<II", data, off + 16)
        assert size <= raw_size or raw_size == 0
        result[name] = data[ptr : ptr + size]
    return data, result


# Fresh exclusive outputs.
BOARD_JSON = T / "dt25-integration-board.json"
POLICY_JSON = T / "dt25-integration-policy.json"
VALID_JSON = T / "dt25-integration-validation.json"
AUDIT_JSON = T / "dt25-artifact-audit.json"
CANDIDATE = T / "dt25-candidate.efi"
for p in (BOARD_JSON, POLICY_JSON, VALID_JSON, AUDIT_JSON, CANDIDATE):
    if p.exists():
        fail(f"refusing: fresh output already exists {p}")

assert OUT.is_dir(), f"missing OUT {OUT}"
assert (OUT / "vmlinuz-live.efi").is_file()
assert (OUT / "live-initramfs.img").is_file()

# Old fallback unchanged.
old_uki_sha = sha(OLD_OUT / "vmlinuz-live.efi")
assert old_uki_sha == EXP_OLD_UKI_SHA, f"old UKI changed {old_uki_sha}"
sfs_size = SFS.stat().st_size
assert sfs_size == EXP_SFS_SIZE, f"SFS size {sfs_size}"
# SFS hash is 1.7GB; verify (slow but required).
print("hashing SFS (1.7GB)...", flush=True)
sfs_sha = sha(SFS)
assert sfs_sha == EXP_SFS_SHA, f"SFS hash {sfs_sha}"
print(f"SFS_OK size={sfs_size} sha={sfs_sha}", flush=True)

# Image + DTB provenance.
assert sha(K / "arch/arm64/boot/Image") == EXP_IMAGE_SHA
dtb_bytes = (K / "arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb").read_bytes()
assert hashlib.sha256(dtb_bytes).hexdigest() == EXP_NEW_DTB_SHA
assert len(dtb_bytes) == EXP_NEW_DTB_SIZE

# PE sections.
_, old = sections(OLD_OUT / "vmlinuz-live.efi")
data, new = sections(OUT / "vmlinuz-live.efi")
for name in (".linux", ".text", ".hwids", ".cmdline", ".uname"):
    assert old[name] == new[name], f"boot/kernel change {name}"
# Base cmdline must equal accepted dt24 live-cmdline.
old_cmd = (OLD_OUT / "live-cmdline").read_text().strip()
new_cmd_raw = new[".cmdline"].split(b"\x00")[0].decode().strip()
assert old_cmd == new_cmd_raw, f"cmdline {old_cmd!r} vs {new_cmd_raw!r}"
assert new[".dtbauto"] == dtb_bytes, "dtbauto != accepted DT25"
assert new[".initrd"] == (OUT / "live-initramfs.img").read_bytes(), "initrd != built image"

# Board52 fresh.
subprocess.run(
    ["python3", str(T / "check-dt25-board.py"), str(K / "arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dtb"), "--result", str(BOARD_JSON)],
    check=True,
)
board = json.loads(BOARD_JSON.read_text())
assert board["passed"] and len(board["checks"]) >= 50, board

# Guard20 policy fresh.
subprocess.run(
    ["python3", str(T / "dt25-thermal-check-policy.py"), "--result", str(POLICY_JSON)],
    check=True,
)
policy = json.loads(POLICY_JSON.read_text())
assert policy["passed"] and policy["required_sensor_count"] == 20, policy

# Full validation fresh (includes USB/input/graphics/logger/firmware).
val_out = subprocess.check_output(
    [
        "python3",
        str(P / "builder/validate-live-initramfs.py"),
        str(OUT / "live-initramfs.img"),
        "--require-local-firmware",
        "--require-log-capture",
        "--require-platform-usb",
        "--require-platform-input",
        "--require-graphics",
    ],
    text=True,
)
validation = json.loads(val_out)
assert validation["passed"], validation
with VALID_JSON.open("x") as f:
    json.dump(validation, f, indent=2)

# Logger + text byte-exact vs dt24 (old logger hashes) + new graphics byte-exact.
with tempfile.TemporaryDirectory(prefix="dt25-integration-audit-old-", dir="/home/builder/boot-failure-tests") as a, tempfile.TemporaryDirectory(
    prefix="dt25-integration-audit-new-", dir="/home/builder/boot-failure-tests"
) as b:
    for image, dest in [(str(OLD_OUT / "live-initramfs.img"), a), (str(OUT / "live-initramfs.img"), b)]:
        subprocess.run(["lsinitcpio", "-x", image], cwd=dest, capture_output=True, check=True)
    pa, pb = Path(a), Path(b)
    for name in [
        "usr/bin/kestrel-checkpoint",
        "hooks/kestrel_efilog",
        "hooks/kestrel_log",
        "usr/bin/kestrel-init-log",
        "usr/bin/kestrel-root-log",
        "usr/bin/kestrel-pid1",
        "etc/kestrel-usb-log.service",
    ]:
        assert (pa / name).read_bytes() == (pb / name).read_bytes(), f"logger changed {name}"
    for packed, src in [
        ("hooks/kestrel_text", "builder/initcpio/hooks/kestrel_text"),
        ("etc/kestrel-text-login", "builder/diagnostics/kestrel-text-login.sh"),
        ("etc/kestrel-text-proof", "builder/diagnostics/kestrel-text-proof.sh"),
        ("etc/kestrel-text-bashrc", "builder/diagnostics/kestrel-text-bashrc"),
        ("etc/kestrel-text-getty.conf", "builder/diagnostics/kestrel-text-getty.conf"),
    ]:
        assert (pb / packed).read_bytes() == (P / src).read_bytes(), packed
    for packed, src in [
        ("hooks/kestrel_graphics", "builder/initcpio/hooks/kestrel_graphics"),
        ("etc/kestrel-graphics-supervisor", "builder/diagnostics/kestrel-graphics-supervisor.py"),
        ("etc/kestrel-graphics-guard", "builder/diagnostics/kestrel_graphics_guard.py"),
        ("etc/kestrel-graphics-env", "builder/diagnostics/kestrel-graphics-env.conf"),
        ("etc/kestrel-graphics-service", "builder/diagnostics/kestrel-graphics.service"),
        ("etc/kestrel-graphics-sddm", "builder/diagnostics/kestrel-graphics-sddm.service"),
        ("etc/kestrel-graphics-policy", "builder/diagnostics/kestrel-graphics-policy.json"),
        ("etc/kestrel-graphics-tty2", "builder/diagnostics/kestrel-graphics-tty2.conf"),
    ]:
        assert (pb / packed).read_bytes() == (P / src).read_bytes(), packed
    for module in ["gpi", "i2c-qcom-geni", "phy-nxp-ptn3222", "qrtr", "qrtr-smd", "i2c-hid", "i2c-hid-of", "hid-generic"]:
        txt = subprocess.check_output(["modprobe", "-d", b, "-S", "7.3.0-rc3", "--show-depends", module], text=True)
        assert "insmod " in txt, module

# SFS closure: required runtime usr paths must exist in SFS listing (not only imgroot).
sfs_list = subprocess.check_output(["unsquashfs", "-l", str(SFS)], text=True, timeout=120)
for rel in [
    "squashfs-root/usr/bin/python3.14",
    "squashfs-root/usr/bin/sddm",
    "squashfs-root/usr/bin/kwin_wayland",
    "squashfs-root/usr/lib/dri/kms_swrast_dri.so",
    "squashfs-root/usr/lib/systemd/system/sddm.service",
    "squashfs-root/usr/lib/systemd/user/plasma-plasmashell.service",
]:
    assert rel in sfs_list, f"SFS missing {rel}"
# Imgroot versions (read-only, no account material).
img_versions = {}
for pkg in ["mesa", "sddm", "plasma-desktop", "kwin", "python"]:
    out = subprocess.check_output(["pacman", "--root", str(ROOT), "-Q", pkg], text=True).strip()
    img_versions[pkg] = out
assert "26.2.4" in img_versions["mesa"], img_versions
assert "6.7.5" in img_versions["plasma-desktop"], img_versions

# QEMU firmware exists (no install).
qemu = P / "testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd"
assert qemu.is_file() and qemu.stat().st_size == 3145728
assert sha(qemu) == EXP_QEMU_SHA

# Source snapshot.
sources = [
    "builder/build-live-uki.sh",
    "builder/validate-live-initramfs.py",
    "builder/platform_graphics_gate.py",
    "builder/platform_usb_gate.py",
    "builder/platform_input_gate.py",
    "builder/initcpio/hooks/kestrel_graphics",
    "builder/initcpio/hooks/kestrel_text",
    "builder/initcpio/hooks/kestrel_log",
    "builder/initcpio/hooks/kestrel_efilog",
    "builder/initcpio/install/kestrel_graphics",
    "builder/diagnostics/kestrel-graphics-supervisor.py",
    "builder/diagnostics/kestrel_graphics_guard.py",
    "builder/diagnostics/kestrel-graphics-env.conf",
    "builder/diagnostics/kestrel-graphics-policy.json",
    "builder/diagnostics/kestrel-graphics.service",
    "builder/diagnostics/kestrel-graphics-sddm.service",
    "builder/diagnostics/kestrel-graphics-tty2.conf",
]
snap = {rel: {"sha256": sha(P / rel), "bytes": (P / rel).stat().st_size} for rel in sources}

report = {
    "passed": True,
    "revision": "v2-dt25",
    "uki_bytes": len(data),
    "uki_sha256": hashlib.sha256(data).hexdigest(),
    "initramfs_sha256": hashlib.sha256((OUT / "live-initramfs.img").read_bytes()).hexdigest(),
    "uki_path": str(OUT / "vmlinuz-live.efi"),
    "initramfs_path": str(OUT / "live-initramfs.img"),
    "kernel_stub_hwids_base_cmdline_unchanged": True,
    "dtb_sha256": EXP_NEW_DTB_SHA,
    "dtb_bytes": EXP_NEW_DTB_SIZE,
    "dtb_scope": board,
    "initramfs_validation": validation,
    "guard_policy": policy,
    "logger_preserved": True,
    "text_byte_exact": True,
    "graphics_byte_exact": True,
    "module_dependencies_resolve": True,
    "old_uki_sha256": old_uki_sha,
    "old_uki_preserved": True,
    "sfs_sha256": sfs_sha,
    "sfs_bytes": sfs_size,
    "sfs_preserved": True,
    "sfs_required_paths_present": True,
    "sfs_runtime_closure_proven": False,
    "sfs_runtime_proof_pending_vm": True,
    "imgroot_versions": img_versions,
    "qemu_firmware": {"path": str(qemu), "sha256": EXP_QEMU_SHA, "bytes": 3145728},
    "sources": snap,
    "native_hardware_validated": False,
    "native_graphics_validated": False,
}
with AUDIT_JSON.open("x") as f:
    json.dump(report, f, indent=2)
with CANDIDATE.open("xb") as f:
    f.write(data)
print(json.dumps(report, indent=2))
