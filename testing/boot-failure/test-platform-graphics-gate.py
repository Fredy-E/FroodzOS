#!/usr/bin/env python3
"""Per-clause graphics gate tests + RED dt24 / GREEN candidate.

Synthetic fixtures for each clause (no native boot). Real dt24 RED and
real candidate GREEN via lsinitcpio extraction. No skips.
"""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P / "builder"))
from platform_graphics_gate import check_platform_graphics

DT24_IMG = Path("/home/builder/uki-v2-dt24/live-initramfs.img")
DT25_IMG = Path("/home/builder/uki-v2-dt25/live-initramfs.img")
BASE = Path("/home/builder/boot-failure-tests")
LOCK = Path("/home/builder/boot-failure-tests/dt25-build.lock")
T = Path(__file__).parent

HOOK_GOOD = (P / "builder/initcpio/hooks/kestrel_graphics").read_bytes()
POLICY_GOOD = (P / "builder/diagnostics/kestrel-graphics-policy.json").read_bytes()

# Immutable baseline captured before fix (7 files). Must remain unchanged.
OLD_BASELINE = {
    "dt25-artifact-audit.json": {"sha256": "7133b357371fea37ae72b40b5fcbf4b341dc63e2d67b09e08c83d143446a4308", "bytes": 10415},
    "dt25-integration-platform-graphics-gate.json": {"sha256": "6f2bfe4a3fda28ec5a456f3f31f52afe360494db8144a38dbec5e8a69192f3e5", "bytes": 194},
    "dt25-integration-packed-graphics.json": {"sha256": "a29a983b0aced0f8a4779f6ce5bb42ce491a8b5ea5427374412e2da86b06256e", "bytes": 224},
    "dt25-integration-summary.json": {"sha256": "00aa46083fd91f836a7c96fcaf7ab98b13116e25f8a3e90e5bd29035a547c646", "bytes": 1331},
    "dt25-integration-board.json": {"sha256": "652254ec51f37d7eb97df8bcb218dbb1a2e289707f7c59fe2b90375481ec423b", "bytes": 2138},
    "dt25-integration-policy.json": {"sha256": "df1143bdf4690a7e582e5135957db14e42acfac03961dab962995fd81c68f51a", "bytes": 708},
    "dt25-integration-validation.json": {"sha256": "b6d8fefff812965cf32e68d409482bf1ebe930b43ebf8e78264c5495028da1e2", "bytes": 3010},
}
OLD_RESULT_NAMES = (
    "dt25-integration-platform-graphics-gate.json",
    "dt25-integration-packed-graphics.json",
)


def make_valid_fixture(root):
    root = Path(root)
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "etc").mkdir(parents=True, exist_ok=True)
    (root / "usr/bin").mkdir(parents=True, exist_ok=True)
    (root / "usr/lib").mkdir(parents=True, exist_ok=True)
    (root / "hooks/kestrel_graphics").write_bytes(HOOK_GOOD)
    (root / "hooks/kestrel_text").write_bytes(b"# text hook\n")
    (root / "etc/kestrel-usb-log.service").write_bytes(b"[Unit]\n")
    mapping = {
        "etc/kestrel-graphics-supervisor": P / "builder/diagnostics/kestrel-graphics-supervisor.py",
        "etc/kestrel-graphics-guard": P / "builder/diagnostics/kestrel_graphics_guard.py",
        "etc/kestrel-graphics-env": P / "builder/diagnostics/kestrel-graphics-env.conf",
        "etc/kestrel-graphics-service": P / "builder/diagnostics/kestrel-graphics.service",
        "etc/kestrel-graphics-sddm": P / "builder/diagnostics/kestrel-graphics-sddm.service",
        "etc/kestrel-graphics-policy": P / "builder/diagnostics/kestrel-graphics-policy.json",
        "etc/kestrel-graphics-tty2": P / "builder/diagnostics/kestrel-graphics-tty2.conf",
        "etc/kestrel-text-login": P / "builder/diagnostics/kestrel-text-login.sh",
        "etc/kestrel-text-proof": P / "builder/diagnostics/kestrel-text-proof.sh",
        "etc/kestrel-text-bashrc": P / "builder/diagnostics/kestrel-text-bashrc",
        "etc/kestrel-text-getty.conf": P / "builder/diagnostics/kestrel-text-getty.conf",
    }
    for rel, src in mapping.items():
        (root / rel).write_bytes(src.read_bytes())
    for name in ("findmnt", "mountpoint"):
        b = root / f"usr/bin/{name}"
        b.write_bytes(b"\x7fELF" + b"\x00" * 64)
        b.chmod(0o755)
    for lib in (
        "libmount.so.1",
        "libblkid.so.1",
        "libsmartcols.so.1",
        "libudev.so.1",
        "libsystemd.so.0",
        "libc.so.6",
    ):
        (root / f"usr/lib/{lib}").write_bytes(b"x")
    (root / "config").write_text('LATEHOOKS="kestrel_log kestrel_text kestrel_graphics"\n')
    return root


def extract_image(image, dest):
    # Legacy helper retained for compatibility; new code uses locked variant.
    return extract_image_locked(image, dest)


def extract_image_locked(image, dest):
    dest = Path(dest)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.touch(exist_ok=True)
    with LOCK.open("a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            proc = subprocess.run(
                ["lsinitcpio", "-x", str(image)], cwd=dest, capture_output=True, text=True, timeout=120
            )
            assert proc.returncode == 0, proc.stdout + proc.stderr
        finally:
            try:
                fcntl.flock(lf, fcntl.LOCK_UN)
            except OSError:
                pass
    return dest


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class GraphicsGateClauseTests(unittest.TestCase):
    FIX_TAG = "nofix-direct"
    FIX_RESULT = None

    def test_complete_fixture_passes(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            checks = check_platform_graphics(root)
            self.assertEqual(len(checks), 32, f"expected 32 clauses, got {len(checks)}: {sorted(checks)}")
            self.assertTrue(all(checks.values()), json.dumps({k: v for k, v in checks.items() if not v}, indent=2))

    def test_all_32_clauses_load_bearing_counted(self):
        # Each of the 32 predicates must independently fail on targeted mutation.
        import json as _j
        mutations = {
            "graphics_hook_present": lambda r: (r / "hooks/kestrel_graphics").unlink(),
            "graphics_hook_gated": lambda r: (r / "hooks/kestrel_graphics").write_text("# no gating\nreturn 0\n"),
            "graphics_hook_requires_mountpoint": lambda r: (r / "hooks/kestrel_graphics").write_text((r / "hooks/kestrel_graphics").read_text().replace("command -v mountpoint", "true")),
            "graphics_hook_requires_findmnt": lambda r: (r / "hooks/kestrel_graphics").write_text((r / "hooks/kestrel_graphics").read_text().replace("command -v findmnt", "true")),
            "graphics_hook_requires_overlay": lambda r: (r / "hooks/kestrel_graphics").write_text((r / "hooks/kestrel_graphics").read_text().replace('"overlay"', '"overlayX"')),
            "graphics_no_cowspace_fallback": lambda r: (r / "hooks/kestrel_graphics").write_text((r / "hooks/kestrel_graphics").read_text() + "\n[ -e /run/archiso/cowspace ] && echo hi\n"),
            "graphics_no_global_efi_writer": lambda r: (r / "usr/bin/kestrel-efilog-loop").write_bytes(b"x"),
            "graphics_no_python_packed": lambda r: (r / "usr/bin/python3").write_bytes(b"x"),
            "graphics_kestrel_graphics_supervisor_present": lambda r: (r / "etc/kestrel-graphics-supervisor").unlink(),
            "graphics_kestrel_graphics_guard_present": lambda r: (r / "etc/kestrel-graphics-guard").unlink(),
            "graphics_kestrel_graphics_env_present": lambda r: (r / "etc/kestrel-graphics-env").unlink(),
            "graphics_kestrel_graphics_service_present": lambda r: (r / "etc/kestrel-graphics-service").unlink(),
            "graphics_kestrel_graphics_sddm_present": lambda r: (r / "etc/kestrel-graphics-sddm").unlink(),
            "graphics_kestrel_graphics_policy_present": lambda r: (r / "etc/kestrel-graphics-policy").unlink(),
            "graphics_kestrel_graphics_tty2_present": lambda r: (r / "etc/kestrel-graphics-tty2").unlink(),
            "graphics_text_kestrel_text_login_preserved": lambda r: (r / "etc/kestrel-text-login").unlink(),
            "graphics_text_kestrel_text_proof_preserved": lambda r: (r / "etc/kestrel-text-proof").unlink(),
            "graphics_text_kestrel_text_bashrc_preserved": lambda r: (r / "etc/kestrel-text-bashrc").unlink(),
            "graphics_text_kestrel_text_getty_conf_preserved": lambda r: (r / "etc/kestrel-text-getty.conf").unlink(),
            "graphics_text_hook_preserved": lambda r: (r / "hooks/kestrel_text").unlink(),
            "graphics_logger_service_preserved": lambda r: (r / "etc/kestrel-usb-log.service").unlink(),
            "graphics_findmnt_elf_present": lambda r: (r / "usr/bin/findmnt").write_bytes(b"#!/bin/sh\necho hi\n"),
            "graphics_mountpoint_elf_present": lambda r: (r / "usr/bin/mountpoint").write_bytes(b"#!/bin/sh\necho hi\n"),
            "graphics_lib_libmount_so_1_present": lambda r: (r / "usr/lib/libmount.so.1").unlink(),
            "graphics_lib_libblkid_so_1_present": lambda r: (r / "usr/lib/libblkid.so.1").unlink(),
            "graphics_lib_libsmartcols_so_1_present": lambda r: (r / "usr/lib/libsmartcols.so.1").unlink(),
            "graphics_lib_libudev_so_1_present": lambda r: (r / "usr/lib/libudev.so.1").unlink(),
            "graphics_lib_libsystemd_so_0_present": lambda r: (r / "usr/lib/libsystemd.so.0").unlink(),
            "graphics_lib_libc_so_6_present": lambda r: (r / "usr/lib/libc.so.6").unlink(),
            "graphics_config_ordered_after_text": lambda r: (r / "config").write_text('LATEHOOKS="kestrel_graphics kestrel_text"\n'),
            "graphics_config_contains_hook": lambda r: (r / "config").write_text('LATEHOOKS="kestrel_log kestrel_text"\n'),
            "graphics_policy_valid": lambda r: (lambda d: (d.update({"experiment_stop_mc": 80001}), (r / "etc/kestrel-graphics-policy").write_text(_j.dumps(d))))(_j.loads((r / "etc/kestrel-graphics-policy").read_text())),
        }
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxcover-") as tmp0:
            keys = sorted(check_platform_graphics(make_valid_fixture(tmp0)).keys())
        self.assertEqual(len(keys), 32, keys)
        self.assertEqual(set(mutations.keys()), set(keys), "mutation map must equal 32 predicates")
        covered = 0
        for key in keys:
            with self.subTest(clause=key), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxmut-") as tmp:
                root = make_valid_fixture(tmp)
                mutations[key](root)
                if key in ("graphics_findmnt_elf_present", "graphics_mountpoint_elf_present"):
                    name = "findmnt" if "findmnt" in key else "mountpoint"
                    try:
                        (root / f"usr/bin/{name}").chmod(0o755)
                    except OSError:
                        pass
                checks = check_platform_graphics(root)
                self.assertIn(key, checks)
                self.assertFalse(checks[key], f"{key} must fail on targeted mutation")
                covered += 1
        self.assertEqual(covered, 32, "all 32 clauses must be load-bearing")

    def test_each_required_etc_missing_is_load_bearing(self):
        rels = [
            "etc/kestrel-graphics-supervisor",
            "etc/kestrel-graphics-guard",
            "etc/kestrel-graphics-env",
            "etc/kestrel-graphics-service",
            "etc/kestrel-graphics-sddm",
            "etc/kestrel-graphics-policy",
            "etc/kestrel-graphics-tty2",
        ]
        expected_key = {
            "etc/kestrel-graphics-supervisor": "graphics_kestrel_graphics_supervisor_present",
            "etc/kestrel-graphics-guard": "graphics_kestrel_graphics_guard_present",
            "etc/kestrel-graphics-env": "graphics_kestrel_graphics_env_present",
            "etc/kestrel-graphics-service": "graphics_kestrel_graphics_service_present",
            "etc/kestrel-graphics-sddm": "graphics_kestrel_graphics_sddm_present",
            "etc/kestrel-graphics-policy": "graphics_kestrel_graphics_policy_present",
            "etc/kestrel-graphics-tty2": "graphics_kestrel_graphics_tty2_present",
        }
        for rel in rels:
            with self.subTest(missing=rel), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
                root = make_valid_fixture(tmp)
                (root / rel).unlink()
                checks = check_platform_graphics(root)
                bad = [k for k, v in checks.items() if not v]
                self.assertTrue(len(bad) >= 1, rel)
                self.assertFalse(checks[expected_key[rel]], f"{rel} must fail {expected_key[rel]}")
                self.assertTrue(any("present" in k for k in bad), f"{rel} -> {bad}")

    def test_each_text_etc_missing_is_load_bearing(self):
        mapping = {
            "etc/kestrel-text-login": "graphics_text_kestrel_text_login_preserved",
            "etc/kestrel-text-proof": "graphics_text_kestrel_text_proof_preserved",
            "etc/kestrel-text-bashrc": "graphics_text_kestrel_text_bashrc_preserved",
            "etc/kestrel-text-getty.conf": "graphics_text_kestrel_text_getty_conf_preserved",
        }
        for rel, key in mapping.items():
            with self.subTest(missing=rel), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxtext-") as tmp:
                root = make_valid_fixture(tmp)
                (root / rel).unlink()
                checks = check_platform_graphics(root)
                self.assertFalse(checks[key], f"{rel} must fail {key}")

    def test_each_lib_missing_is_load_bearing(self):
        mapping = {
            "usr/lib/libmount.so.1": "graphics_lib_libmount_so_1_present",
            "usr/lib/libblkid.so.1": "graphics_lib_libblkid_so_1_present",
            "usr/lib/libsmartcols.so.1": "graphics_lib_libsmartcols_so_1_present",
            "usr/lib/libudev.so.1": "graphics_lib_libudev_so_1_present",
            "usr/lib/libsystemd.so.0": "graphics_lib_libsystemd_so_0_present",
            "usr/lib/libc.so.6": "graphics_lib_libc_so_6_present",
        }
        for rel, key in mapping.items():
            with self.subTest(missing=rel), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxlib-") as tmp:
                root = make_valid_fixture(tmp)
                (root / rel).unlink()
                checks = check_platform_graphics(root)
                self.assertFalse(checks[key], f"{rel} must fail {key}")

    def test_hook_present_missing_fails(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxhook-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "hooks/kestrel_graphics").unlink()
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_hook_present"])
            self.assertFalse(checks["graphics_hook_gated"])

    def test_hook_gating_mutation_fails(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "hooks/kestrel_graphics").write_text("# no gating\nreturn 0\n")
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_hook_gated"])

    def test_hook_overlay_mutation_fails(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            txt = (root / "hooks/kestrel_graphics").read_text()
            txt2 = txt.replace("command -v mountpoint", "true")
            (root / "hooks/kestrel_graphics").write_text(txt2)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_hook_requires_mountpoint"])
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxoverlay-") as tmp:
            root = make_valid_fixture(tmp)
            txt = (root / "hooks/kestrel_graphics").read_text()
            self.assertIn('"overlay"', txt)
            txt = txt.replace('"overlay"', '"overlayX"')
            (root / "hooks/kestrel_graphics").write_text(txt)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_hook_requires_overlay"])

    def test_hook_findmnt_mutation_fails(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            txt = (root / "hooks/kestrel_graphics").read_text()
            txt = txt.replace("command -v findmnt", "true")
            (root / "hooks/kestrel_graphics").write_text(txt)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_hook_requires_findmnt"])

    def test_cowspace_fallback_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            with (root / "hooks/kestrel_graphics").open("a") as f:
                f.write("\n[ -e /run/archiso/cowspace ] && echo hi\n")
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_no_cowspace_fallback"])

    def test_no_global_efi_writer_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxefi-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/kestrel-efilog-loop").write_bytes(b"x")
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_no_global_efi_writer"])
        for marker in ("efivarfs", "KestrelBoot", "efivars"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxefi-") as tmp:
                root = make_valid_fixture(tmp)
                with (root / "hooks/kestrel_graphics").open("a") as f:
                    f.write(f"\necho {marker} > /tmp/kestrel-efi-probe\n")
                checks = check_platform_graphics(root)
                self.assertFalse(checks["graphics_no_global_efi_writer"], marker)

    def test_no_python_packed_rejected(self):
        for name in ("usr/bin/python3", "usr/bin/python"):
            with self.subTest(bin=name), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxpy-") as tmp:
                root = make_valid_fixture(tmp)
                (root / name).write_bytes(b"x")
                checks = check_platform_graphics(root)
                self.assertFalse(checks["graphics_no_python_packed"], name)

    def test_text_hook_and_logger_preserved(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxtext-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "hooks/kestrel_text").unlink()
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_text_hook_preserved"])
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxlog-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "etc/kestrel-usb-log.service").unlink()
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_logger_service_preserved"])

    def test_policy_battery_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            import json as _j
            d = _j.loads((root / "etc/kestrel-graphics-policy").read_text())
            d["required_sensor_types"] = ["qcom-battmgr-bat"] * 20
            (root / "etc/kestrel-graphics-policy").write_text(_j.dumps(d))
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_policy_valid"])

    def test_policy_count_mutation_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            import json as _j
            d = _j.loads((root / "etc/kestrel-graphics-policy").read_text())
            d["required_sensor_types"] = d["required_sensor_types"][:19]
            (root / "etc/kestrel-graphics-policy").write_text(_j.dumps(d))
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_policy_valid"])

    def test_policy_minmax_stop_count_batt_duplicate_rejected(self):
        import json as _j
        cases = {
            "stop_high": lambda d: d.update({"experiment_stop_mc": 80001}),
            "stop_low": lambda d: d.update({"experiment_stop_mc": 79999}),
            "min_high": lambda d: d.update({"experiment_minimum_mc": 5001}),
            "min_low": lambda d: d.update({"experiment_minimum_mc": 4999}),
            "count_19": lambda d: d.update({"required_sensor_count": 19}),
            "count_21": lambda d: d.update({"required_sensor_count": 21}),
            "batt_true": lambda d: d.update({"battery_substitution_allowed": True}),
            "duplicate": lambda d: d.update({"required_sensor_types": d["required_sensor_types"][:19] + [d["required_sensor_types"][0]]}),
            "empty_types": lambda d: d.update({"required_sensor_types": []}),
        }
        for name, mut in cases.items():
            with self.subTest(policy=name), tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxpol-") as tmp:
                root = make_valid_fixture(tmp)
                d = _j.loads((root / "etc/kestrel-graphics-policy").read_text())
                mut(d)
                (root / "etc/kestrel-graphics-policy").write_text(_j.dumps(d))
                checks = check_platform_graphics(root)
                self.assertFalse(checks["graphics_policy_valid"], name)

    def test_findmnt_non_elf_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/findmnt").write_bytes(b"#!/bin/sh\necho hi\n")
            (root / "usr/bin/findmnt").chmod(0o755)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_findmnt_elf_present"])

    def test_findmnt_elf_mode_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/findmnt").unlink()
            (root / "usr/bin/findmnt").symlink_to("busybox")
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_findmnt_elf_present"])
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/findmnt").chmod(0o644)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_findmnt_elf_present"])

    def test_mountpoint_elf_mode_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/mountpoint").write_bytes(b"#!/bin/sh\necho hi\n")
            (root / "usr/bin/mountpoint").chmod(0o755)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_mountpoint_elf_present"])
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/mountpoint").unlink()
            (root / "usr/bin/mountpoint").symlink_to("busybox")
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_mountpoint_elf_present"])
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxelf-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "usr/bin/mountpoint").chmod(0o644)
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_mountpoint_elf_present"])

    def test_config_order_mutation_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgate-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "config").write_text('LATEHOOKS="kestrel_graphics kestrel_text"\n')
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_config_ordered_after_text"])
            self.assertTrue(checks["graphics_config_contains_hook"])

    def test_config_contains_hook_missing_rejected(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxcfg-") as tmp:
            root = make_valid_fixture(tmp)
            (root / "config").write_text('LATEHOOKS="kestrel_log kestrel_text"\n')
            checks = check_platform_graphics(root)
            self.assertFalse(checks["graphics_config_contains_hook"])
            self.assertFalse(checks["graphics_config_ordered_after_text"])

    def test_collision_regression_originals_preserved_no_side_effect(self):
        for rel, exp in OLD_BASELINE.items():
            p = T / rel
            self.assertTrue(p.is_file(), f"original missing {rel}")
            data = p.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), exp["sha256"], f"original changed {rel}")
            self.assertEqual(len(data), exp["bytes"], f"original size changed {rel}")
        for name in OLD_RESULT_NAMES:
            with self.assertRaises(FileExistsError, msg=f"colliding {name} must refuse"):
                (T / name).open("x")
        res = getattr(self.__class__, "FIX_RESULT", None)
        if res is not None:
            rp = Path(res)
            self.assertTrue(str(rp.name).startswith("dt25-integration-fix-"), rp.name)
            self.assertNotIn(rp.name, OLD_RESULT_NAMES)

    def test_dt24_red(self):
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxred-") as tmp:
            extract_image_locked(DT24_IMG, tmp)
            checks = check_platform_graphics(tmp)
            self.assertFalse(all(checks.values()))
            self.assertFalse(checks["graphics_hook_present"])
            self.assertFalse(checks["graphics_config_contains_hook"])

    def test_dt25_green(self):
        self.assertTrue(DT25_IMG.is_file(), "candidate initramfs missing; build first")
        with tempfile.TemporaryDirectory(dir=BASE, prefix="dt25-integration-fix-gfxgreen-") as tmp:
            extract_image_locked(DT25_IMG, tmp)
            checks = check_platform_graphics(tmp)
            self.assertTrue(all(checks.values()), json.dumps({k: v for k, v in checks.items() if not v}, indent=2))


def _validate_tag_result(tag, result, log=None):
    if not re.fullmatch(r"fix-[A-Za-z0-9._-]{1,64}", tag):
        raise SystemExit(f"refusing: --tag must match fix-* pattern, got {tag!r}")
    rp = Path(result)
    if rp.parent.resolve() != T.resolve():
        raise SystemExit(f"refusing: --result must be under {T}, got {rp}")
    if not rp.name.startswith("dt25-integration-fix-"):
        raise SystemExit(f"refusing: --result must start with dt25-integration-fix-, got {rp.name}")
    if tag not in rp.name:
        raise SystemExit(f"refusing: --result name must contain tag {tag!r}, got {rp.name}")
    if not rp.name.endswith(".json"):
        raise SystemExit(f"refusing: --result must end .json, got {rp.name}")
    if rp.name in OLD_RESULT_NAMES or rp.name in OLD_BASELINE:
        raise SystemExit(f"refusing: --result collides with historical archive {rp.name}")
    if rp.exists():
        raise SystemExit(f"refusing: fresh output already exists {rp}")
    if log is not None:
        lp = Path(log)
        if lp.parent.resolve() != T.resolve():
            raise SystemExit(f"refusing: --log must be under {T}, got {lp}")
        if not lp.name.startswith("dt25-integration-fix-"):
            raise SystemExit(f"refusing: --log must start with dt25-integration-fix-, got {lp.name}")
        if tag not in lp.name:
            raise SystemExit(f"refusing: --log name must contain tag {tag!r}")
        if lp.exists():
            raise SystemExit(f"refusing: fresh log already exists {lp}")
    for rel, exp in OLD_BASELINE.items():
        p = T / rel
        if not p.is_file():
            raise SystemExit(f"refusing: original missing {rel}")
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != exp["sha256"] or len(data) != exp["bytes"]:
            raise SystemExit(f"refusing: original changed before run {rel}")
    return rp, (Path(log) if log is not None else None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="dt25 platform graphics gate (evidence-safe, fix-tagged)")
    ap.add_argument("--tag", required=True, help="fresh tag, e.g. fix-20261018-01")
    ap.add_argument("--result", required=True, help="fresh JSON output under testing/boot-failure/")
    ap.add_argument("--log", required=False, default=None, help="fresh log output under testing/boot-failure/")
    ns = ap.parse_args()
    result_path, log_path = _validate_tag_result(ns.tag, ns.result, ns.log)
    GraphicsGateClauseTests.FIX_TAG = ns.tag
    GraphicsGateClauseTests.FIX_RESULT = str(result_path)
    import io
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GraphicsGateClauseTests)
    runner = unittest.TextTestRunner(verbosity=2, stream=stream)
    result = runner.run(suite)
    output = stream.getvalue()
    preserved = {}
    for rel, exp in OLD_BASELINE.items():
        p = T / rel
        data = p.read_bytes()
        ok = (hashlib.sha256(data).hexdigest() == exp["sha256"] and len(data) == exp["bytes"])
        preserved[rel] = ok
    report = {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(getattr(result, "skipped", [])),
        "clause_total": 32,
        "clause_covered": 32,
        "tag": ns.tag,
        "result_path": str(result_path),
        "fixture_only": False,
        "dt24_red_expected": True,
        "dt25_green_expected": True,
        "native_hardware_validated": False,
        "collision_preflight_passed": True,
        "originals_preserved": preserved,
        "all_originals_preserved": all(preserved.values()),
        "previously_lost_history_note": "prior __main__ unlinked outputs before exclusive creation; overwritten history (if any) is not recoverable and not fabricated; current baseline hashes preserved",
    }
    with result_path.open("x") as f:
        json.dump(report, f, indent=2)
    if log_path is not None:
        with log_path.open("x") as f:
            f.write(f"# tag={ns.tag} result={result_path}\n")
            f.write(output)
            f.write("\n# report\n")
            f.write(json.dumps(report, indent=2))
            f.write("\n")
    sys.stdout.write(output)
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if (result.wasSuccessful() and all(preserved.values())) else 1)
