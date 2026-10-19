#!/usr/bin/env python3
"""Focused staging tests: execute unmodified ash hook in disposable fixtures.

Derives project root from __file__ (Windows + WSL). Fails when required
files are missing (no required skips). Actually executes the unmodified
builder/initcpio/hooks/kestrel_graphics via sh in temp sysroot/etc fixtures
with explicit mock mount/overlay/cmdline predicates. Asserts byte-for-byte
destinations, unit symlinks/masks, opt-out no-op, persistent-root rejection,
partial-copy rollback, missing-policy build refusal, and no unguarded SDDM
with/without the text hook. Static presence checks are supplementary.
Native graphics NOT validated.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
HOOK = P / "builder/initcpio/hooks/kestrel_graphics"
INSTALL = P / "builder/initcpio/install/kestrel_graphics"
TEXT_HOOK = P / "builder/initcpio/hooks/kestrel_text"
SUP_SRC = P / "builder/diagnostics/kestrel-graphics-supervisor.py"
ENV_SRC = P / "builder/diagnostics/kestrel-graphics-env.conf"
SVC_SRC = P / "builder/diagnostics/kestrel-graphics.service"
SDDM_PRIV_SRC = P / "builder/diagnostics/kestrel-graphics-sddm.service"
TTY2_SRC = P / "builder/diagnostics/kestrel-graphics-tty2.conf"
GUARD_SRC = P / "builder/diagnostics/kestrel_graphics_guard.py"
POLICY_SRC = P / "builder/diagnostics/kestrel-graphics-policy.json"
TEXT_LOGIN = P / "builder/diagnostics/kestrel-text-login.sh"
TEXT_PROOF = P / "builder/diagnostics/kestrel-text-proof.sh"
TEXT_BASHRC = P / "builder/diagnostics/kestrel-text-bashrc"
TEXT_GETTY = P / "builder/diagnostics/kestrel-text-getty.conf"

REQUIRED = [HOOK, INSTALL, TEXT_HOOK, SUP_SRC, ENV_SRC, SVC_SRC,
            SDDM_PRIV_SRC, TTY2_SRC, GUARD_SRC, POLICY_SRC,
            TEXT_LOGIN, TEXT_PROOF, TEXT_BASHRC, TEXT_GETTY]

FORBIDDEN_SHELL = [
    "useradd", "usermod", "userdel", "chpasswd",
    "modprobe", "insmod", "rmmod",
    "systemctl reboot", "systemctl poweroff",
    "kexec",
    "trip_point", "thermal_trip", "cooling_device",
    "cpufreq", "/dev/mmcblk", "dd if=", "mkfs",
    "KESTREL-LOG-TARGET", "bootmnt/Logs",
]

FORBIDDEN_COMMANDS = [
    '["systemctl", "reboot"', "['systemctl', 'reboot'",
    '["systemctl", "poweroff"', "['systemctl', 'poweroff'",
    '["reboot"', "['reboot'", '["poweroff"', "['poweroff'",
    '["useradd"', "['useradd'", '["usermod"', "['usermod'",
    '["modprobe"', "['modprobe'", '["insmod"', "['insmod'",
    '"trip_point"', "'trip_point'",
    "/dev/mmcblk", "bootmnt/Logs",
]


def run_sh(script, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    # Use sh (dash on WSL, git-bash sh on Windows). Hook is POSIX ash.
    return subprocess.run(["sh", "-c", script], capture_output=True, text=True, env=env, timeout=30)


def make_live_fixture(tmp, with_stock_gui=True):
    tmp = Path(tmp)
    sysroot = tmp / "sysroot"
    etc = tmp / "etc"
    units = sysroot / "etc/systemd/system"
    (units).mkdir(parents=True, exist_ok=True)
    (sysroot / "usr/lib/systemd/system").mkdir(parents=True, exist_ok=True)
    (sysroot / "usr/lib/systemd/system/getty@.service").write_text("[Service]\n")
    if with_stock_gui:
        # Stock live: display-manager -> sddm (lower layer simulation in upper for test).
        try:
            (units / "display-manager.service").symlink_to("/usr/lib/systemd/system/sddm.service")
        except FileExistsError:
            pass
    mapping = {
        "kestrel-graphics-supervisor": SUP_SRC,
        "kestrel-graphics-guard": GUARD_SRC,
        "kestrel-graphics-env": ENV_SRC,
        "kestrel-graphics-service": SVC_SRC,
        "kestrel-graphics-sddm": SDDM_PRIV_SRC,
        "kestrel-graphics-policy": POLICY_SRC,
        "kestrel-graphics-tty2": TTY2_SRC,
        "kestrel-text-login": TEXT_LOGIN,
        "kestrel-text-proof": TEXT_PROOF,
        "kestrel-text-bashrc": TEXT_BASHRC,
        "kestrel-text-getty.conf": TEXT_GETTY,
    }
    etc.mkdir(parents=True, exist_ok=True)
    for etc_name, src in mapping.items():
        assert src.is_file(), f"missing required source {src}"
        (etc / etc_name).write_bytes(src.read_bytes())
    return sysroot, etc


def hook_script(hook_path, extra=""):
    # Mock predicates explicitly via shell functions; KESTREL_* isolates fixture.
    return f"""
getarg() {{
  case "$1" in
    kestrel_graphics) echo "$MOCK_GFX" ;;
    kestrel_textboot) echo "$MOCK_TEXT" ;;
    *) echo "" ;;
  esac
}}
mountpoint() {{
  return $MOCK_MOUNTPOINT_RC
}}
findmnt() {{
  if [ "$MOCK_FINDMNT_RC" != "0" ]; then return $MOCK_FINDMNT_RC; fi
  echo "$MOCK_FSTYPE"
  return 0
}}
. "{hook_path}"
{extra}
"""


def make_seeded_prestate_fixture(tmp):
    """Seed REAL inherited text/security state, return (sysroot, etc, baseline)."""
    tmp = Path(tmp)
    sysroot, etc = make_live_fixture(tmp, with_stock_gui=False)
    units = sysroot / "etc/systemd/system"
    # Real inherited text helpers with correct modes.
    for rel, src, mode in [
        ("usr/local/sbin/kestrel-text-login", TEXT_LOGIN, 0o755),
        ("usr/local/sbin/kestrel-text-proof", TEXT_PROOF, 0o755),
        ("usr/local/lib/kestrel-text-bashrc", TEXT_BASHRC, 0o644),
    ]:
        p = sysroot / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(src.read_bytes())
        os.chmod(p, mode)
    # Inherited masks (text hook / live): stock GUI + SSH masked.
    for name in ["display-manager.service", "sddm.service",
                 "sshd.service", "sshd.socket"]:
        try:
            (units / name).unlink()
        except FileNotFoundError:
            pass
        (units / name).symlink_to("/dev/null")
    # tty1 fallback (text hook): drop-in + wants + default.target.
    (units / "getty@tty1.service.d").mkdir(parents=True, exist_ok=True)
    (units / "getty@tty1.service.d/90-kestrel-live.conf").write_bytes(
        TEXT_GETTY.read_bytes())
    (units / "getty.target.wants").mkdir(parents=True, exist_ok=True)
    try:
        (units / "getty.target.wants/getty@tty1.service").symlink_to(
            "/usr/lib/systemd/system/getty@.service")
    except FileExistsError:
        pass
    baseline = {}
    for rel in ["usr/local/sbin/kestrel-text-login",
                "usr/local/sbin/kestrel-text-proof",
                "usr/local/lib/kestrel-text-bashrc"]:
        p = sysroot / rel
        baseline[rel] = (p.read_bytes(), oct(p.stat().st_mode & 0o777))
    baseline["masks"] = {}
    for name in ["display-manager.service", "sddm.service",
                 "sshd.service", "sshd.socket"]:
        q = units / name
        baseline["masks"][name] = os.readlink(q) if q.is_symlink() else None
    tty1_conf = units / "getty@tty1.service.d/90-kestrel-live.conf"
    baseline["tty1_conf"] = tty1_conf.read_bytes() if tty1_conf.is_file() else None
    tty1_wants = units / "getty.target.wants/getty@tty1.service"
    baseline["tty1_wants"] = os.readlink(tty1_wants) if tty1_wants.is_symlink() else None
    return sysroot, etc, baseline


class StagingContract(unittest.TestCase):
    def test_hook_and_install_exist(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")

    def test_hook_gated_opt_in_inert(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        text = HOOK.read_text()
        self.assertIn("kestrel_graphics", text)
        self.assertIn("getarg kestrel_graphics", text)
        self.assertIn("= 1", text)
        self.assertIn("return 0", text)
        for bad in ["reboot", "poweroff", "kexec"]:
            # Allow documentation "no reboot/poweroff" but no command.
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("#"):
                    continue
                self.assertNotIn(bad, line, f"hook executable contains {bad!r}")

    def test_install_references_verified_helpers(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        text = INSTALL.read_text()
        self.assertIn("add_file", text)
        self.assertIn("add_runscript", text)
        for token in ["kestrel-graphics-supervisor", "kestrel-graphics.service",
                      "kestrel-graphics-sddm.service", "kestrel-graphics-env",
                      "kestrel-graphics-policy"]:
            self.assertIn(token, text)

    def test_no_account_firmware_commands(self):
        for p in [HOOK, INSTALL]:
            self.assertTrue(p.is_file(), f"missing required {p}")
        for path in [HOOK, INSTALL]:
            data = path.read_text(errors="replace")
            for bad in FORBIDDEN_SHELL:
                # comments may mention; check non-comment lines
                for line in data.splitlines():
                    if line.strip().startswith("#"):
                        continue
                    self.assertNotIn(bad, line, f"{path.name} executable contains {bad!r}")
        data = SUP_SRC.read_text(errors="replace")
        for bad in FORBIDDEN_COMMANDS:
            self.assertNotIn(bad, data, f"supervisor contains forbidden {bad!r}")
        for bad in ["KESTREL-LOG-TARGET", "bootmnt/Logs", "/dev/mmcblk"]:
            self.assertNotIn(bad, data)
        # Strict ownership: no process-name kill, no broad user kill in executable.
        for bad in ["pkill", "terminate-user"]:
            self.assertNotIn(bad, data, f"supervisor must not contain {bad!r}")

    def test_flag_off_is_noop_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-off-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=True)
            stock_link = sysroot / "etc/systemd/system/display-manager.service"
            self.assertTrue(stock_link.is_symlink())
            script = hook_script(HOOK.as_posix(), "run_latehook\necho \"exit=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("exit=0", proc.stdout)
            # No staging when flag off.
            self.assertFalse((sysroot / "etc/systemd/system/multi-user.target.wants/kestrel-graphics.service").exists())
            self.assertFalse((sysroot / "usr/local/sbin/kestrel-graphics-supervisor").exists())
            # Stock GUI untouched when flag off.
            self.assertTrue(stock_link.is_symlink())
            self.assertEqual(os.readlink(stock_link), "/usr/lib/systemd/system/sddm.service")

    def test_valid_overlay_staging_executes(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-stage-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=True)
            units = sysroot / "etc/systemd/system"
            script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("stage=0", proc.stdout, proc.stderr + proc.stdout)
            # Byte-for-byte destinations.
            pairs = [
                (SUP_SRC, sysroot / "usr/local/sbin/kestrel-graphics-supervisor"),
                (GUARD_SRC, sysroot / "usr/local/lib/kestrel_graphics_guard.py"),
                (ENV_SRC, sysroot / "etc/kestrel-graphics-env"),
                (POLICY_SRC, sysroot / "etc/kestrel-graphics-policy.json"),
                (SVC_SRC, units / "kestrel-graphics.service"),
                (SDDM_PRIV_SRC, units / "kestrel-graphics-sddm.service"),
                (TEXT_LOGIN, sysroot / "usr/local/sbin/kestrel-text-login"),
                (TEXT_PROOF, sysroot / "usr/local/sbin/kestrel-text-proof"),
                (TEXT_BASHRC, sysroot / "usr/local/lib/kestrel-text-bashrc"),
                (TTY2_SRC, units / "getty@tty2.service.d/90-kestrel-live.conf"),
            ]
            for src, dst in pairs:
                self.assertTrue(dst.is_file(), f"missing staged {dst}")
                self.assertEqual(dst.read_bytes(), src.read_bytes(), f"not byte-exact {dst}")
            # Unit symlinks/masks.
            self.assertEqual(os.readlink(units / "multi-user.target.wants/kestrel-graphics.service"),
                             "../kestrel-graphics.service")
            self.assertFalse((units / "graphical.target.wants/kestrel-graphics.service").exists())
            self.assertEqual(os.readlink(units / "display-manager.service"), "/dev/null")
            self.assertEqual(os.readlink(units / "sddm.service"), "/dev/null")
            self.assertEqual(os.readlink(units / "getty.target.wants/getty@tty2.service"),
                             "/usr/lib/systemd/system/getty@.service")
            for s in ["sshd.service", "sshd.socket", "ssh.service"]:
                self.assertEqual(os.readlink(units / s), "/dev/null", f"{s} must stay masked")
            # Drop-ins: no restart loops, env reaches user manager.
            priv_drop = (units / "kestrel-graphics-sddm.service.d/90-kestrel-graphics-env.conf").read_text()
            self.assertIn("EnvironmentFile=/etc/kestrel-graphics-env", priv_drop)
            self.assertIn("Restart=no", priv_drop)
            self.assertIn("Restart=no", (units / "display-manager.service.d/90-kestrel-graphics-env.conf").read_text())
            self.assertIn("Restart=no", (units / "sddm.service.d/90-kestrel-graphics-env.conf").read_text())
            user_drop = (units / "user@.service.d/90-kestrel-graphics-env.conf").read_text()
            self.assertIn("EnvironmentFile=/etc/kestrel-graphics-env", user_drop)
            # Ordering: supervisor multi-user only, private unit not auto-enabled.
            svc_text = (units / "kestrel-graphics.service").read_text()
            self.assertIn("WantedBy=multi-user.target", svc_text)
            self.assertNotIn("WantedBy=graphical.target", svc_text)
            priv_text = (units / "kestrel-graphics-sddm.service").read_text()
            self.assertIn("Restart=no", priv_text)
            self.assertIn("PartOf=kestrel-graphics.service", priv_text)
            self.assertIn("ConditionPathExists=", priv_text)
            self.assertNotIn("WantedBy=", priv_text)

    def test_persistent_root_rejected_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        for fstype, mnt_rc in [("ext4", "0"), ("overlay", "1")]:
            with tempfile.TemporaryDirectory(prefix="dt25-gfx-persist-") as tmp:
                sysroot, etc = make_live_fixture(tmp, with_stock_gui=False)
                script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\nrun_latehook\necho \"late=$?\"\n")
                env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                       "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": mnt_rc,
                       "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": fstype}
                proc = run_sh(script, env_extra=env)
                self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
                self.assertIn("stage=1", proc.stdout, f"fstype={fstype} mnt={mnt_rc}: {proc.stdout} {proc.stderr}")
                self.assertIn("late=0", proc.stdout)
                self.assertFalse((sysroot / "usr/local/sbin/kestrel-graphics-supervisor").exists())
                self.assertFalse((sysroot / "etc/systemd/system/multi-user.target.wants/kestrel-graphics.service").exists())

    def test_partial_copy_failure_rolls_back_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-partial-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=False)
            # Remove one required input to force cp failure.
            (etc / "kestrel-graphics-env").unlink()
            script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=1", proc.stdout, proc.stderr + proc.stdout)
            # Rollback: no partial enabling left. Fail-closed: owned files
            # absent when never pre-existing; diagnostic masks may remain
            # /dev/null (never weakened to unmasked/enabled).
            self.assertFalse((sysroot / "usr/local/sbin/kestrel-graphics-supervisor").exists())
            self.assertFalse((sysroot / "etc/systemd/system/kestrel-graphics.service").exists())
            self.assertFalse((sysroot / "etc/systemd/system/kestrel-graphics-sddm.service").exists())
            self.assertFalse((sysroot / "etc/systemd/system/multi-user.target.wants/kestrel-graphics.service").exists())
            for name in ["display-manager.service", "sddm.service"]:
                q = sysroot / f"etc/systemd/system/{name}"
                if q.is_symlink() or q.exists():
                    self.assertEqual(os.readlink(q), "/dev/null",
                                     f"{name} must stay masked or absent, never unmasked")
            self.assertFalse((sysroot / "etc/systemd/system/graphical.target.wants/kestrel-graphics.service").exists())

    def test_overlay_requires_mountpoint_and_fstype_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        # Non-overlay FSTYPE and mountpoint failure must fail closed.
        for fstype, mnt_rc, findmnt_rc in [
            ("ext4", "0", "0"), ("tmpfs", "0", "0"), ("", "0", "0"),
            ("overlay", "1", "0"), ("overlay", "0", "1"),
        ]:
            with tempfile.TemporaryDirectory(prefix="dt25-gfx-ovl-") as tmp:
                sysroot, etc = make_live_fixture(tmp, with_stock_gui=False)
                script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
                env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                       "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": mnt_rc,
                       "MOCK_FINDMNT_RC": findmnt_rc, "MOCK_FSTYPE": fstype}
                proc = run_sh(script, env_extra=env)
                self.assertIn("stage=1", proc.stdout,
                              f"fstype={fstype!r} mnt={mnt_rc} findmnt_rc={findmnt_rc}: {proc.stdout} {proc.stderr}")
                self.assertFalse((sysroot / "usr/local/sbin/kestrel-graphics-supervisor").exists())
        # Static: strict gate, no existence fallback in executable code.
        hook_text = HOOK.read_text()
        self.assertIn("command -v mountpoint", hook_text)
        self.assertIn("command -v findmnt", hook_text)
        self.assertIn('= "overlay"', hook_text)
        self.assertNotIn("[ -e /run/archiso/cowspace ]", hook_text)
        for line in hook_text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            self.assertNotIn("cowspace", line,
                             "executable gate must not use cowspace existence fallback")

    def test_install_packs_overlay_helpers_execute(self):
        self.assertTrue(INSTALL.is_file(), f"missing required {INSTALL}")
        text = INSTALL.read_text()
        self.assertIn("add_binary findmnt", text)
        self.assertIn("add_binary mountpoint", text)
        # Execute build with mocked mkinitcpio helpers and capture binaries.
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-buildbin-") as tmp:
            proj = Path(tmp) / "proj"
            (proj / "builder/diagnostics").mkdir(parents=True)
            for src in [SUP_SRC, GUARD_SRC, ENV_SRC, SVC_SRC, SDDM_PRIV_SRC, TTY2_SRC,
                        TEXT_LOGIN, TEXT_PROOF, TEXT_BASHRC, TEXT_GETTY, POLICY_SRC]:
                shutil.copy(src, proj / "builder/diagnostics" / src.name)
            script = f"""
add_file() {{ echo "ADD $1 $2 $3"; return 0; }}
add_binary() {{ echo "BIN $1"; return 0; }}
add_runscript() {{ echo "RUNSCRIPT"; return 0; }}
. "{INSTALL.as_posix()}"
KESTREL_PROJECT="{proj.as_posix()}" build
echo "build=$?"
"""
            proc = run_sh(script)
            self.assertIn("build=0", proc.stdout, proc.stderr + proc.stdout)
            self.assertIn("BIN findmnt", proc.stdout)
            self.assertIn("BIN mountpoint", proc.stdout)

    def test_seeded_prestate_survives_first_copy_failure_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-seedfail-") as tmp:
            sysroot, etc, baseline = make_seeded_prestate_fixture(tmp)
            units = sysroot / "etc/systemd/system"
            # Force FIRST cp failure like parent probe (cp always fails).
            script = hook_script(
                HOOK.as_posix(),
                "cp() { return 1; }\n"
                "run_latehook\necho \"late=$?\"\n"
                "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertIn("late=0", proc.stdout)
            self.assertIn("stage=1", proc.stdout)
            # Inherited helpers byte/mode-exact, never deleted/truncated.
            for rel in ["usr/local/sbin/kestrel-text-login",
                        "usr/local/sbin/kestrel-text-proof",
                        "usr/local/lib/kestrel-text-bashrc"]:
                q = sysroot / rel
                self.assertTrue(q.is_file(), f"lost inherited {rel}")
                exp_bytes, exp_mode = baseline[rel]
                self.assertEqual(q.read_bytes(), exp_bytes, f"altered {rel}")
                self.assertEqual(oct(q.stat().st_mode & 0o777), exp_mode, f"mode changed {rel}")
            # Inherited masks never lost/weakened.
            for name, exp_target in baseline["masks"].items():
                q = units / name
                self.assertTrue(q.is_symlink(), f"lost mask {name}")
                self.assertEqual(os.readlink(q), "/dev/null", f"weakened {name}")
            # tty1 fallback preserved; private GUI never enabled/started.
            self.assertEqual(
                (units / "getty@tty1.service.d/90-kestrel-live.conf").read_bytes(),
                baseline["tty1_conf"])
            self.assertEqual(os.readlink(units / "getty.target.wants/getty@tty1.service"),
                             baseline["tty1_wants"])
            self.assertFalse((units / "graphical.target.wants/kestrel-graphics.service").exists())
            # Stock GUI must not be re-enabled (still masked or absent fail-closed).
            for name in ["display-manager.service", "sddm.service"]:
                q = units / name
                self.assertTrue(q.is_symlink(), f"{name} must stay masked")
                self.assertEqual(os.readlink(q), "/dev/null")

    def test_seeded_prestate_survives_late_link_failure_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-seedlate-") as tmp:
            sysroot, etc, baseline = make_seeded_prestate_fixture(tmp)
            units = sysroot / "etc/systemd/system"
            # Fail late: allow file installs but fail symlink creation.
            script = hook_script(
                HOOK.as_posix(),
                "ln() { return 1; }\n"
                "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=1", proc.stdout, proc.stderr + proc.stdout)
            for rel in ["usr/local/sbin/kestrel-text-login",
                        "usr/local/sbin/kestrel-text-proof",
                        "usr/local/lib/kestrel-text-bashrc"]:
                q = sysroot / rel
                self.assertTrue(q.is_file(), f"lost inherited {rel} on late failure")
                self.assertEqual(q.read_bytes(), baseline[rel][0])
                self.assertEqual(oct(q.stat().st_mode & 0o777), baseline[rel][1])
            for name in ["display-manager.service", "sddm.service",
                         "sshd.service", "sshd.socket"]:
                q = units / name
                self.assertTrue(q.is_symlink(), f"lost mask {name} on late failure")
                self.assertEqual(os.readlink(q), "/dev/null")
            self.assertFalse((units / "graphical.target.wants/kestrel-graphics.service").exists())

    def test_atomic_midcopy_preserves_prestate_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-atomic-") as tmp:
            sysroot, etc, baseline = make_seeded_prestate_fixture(tmp)
            # cp writes partial tmp then fails: original must stay intact.
            script = hook_script(
                HOOK.as_posix(),
                "cp() {\n"
                '  case "$2" in\n'
                '    *.tmp) printf "PARTIAL" >"$2"; return 1;;\n'
                '    *) command cp "$@";;\n'
                "  esac\n"
                "}\n"
                "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=1", proc.stdout, proc.stderr + proc.stdout)
            for rel in ["usr/local/sbin/kestrel-text-login",
                        "usr/local/sbin/kestrel-text-proof",
                        "usr/local/lib/kestrel-text-bashrc"]:
                q = sysroot / rel
                self.assertTrue(q.is_file(), f"truncated {rel}")
                self.assertEqual(q.read_bytes(), baseline[rel][0],
                                 f"mid-copy truncated {rel}")
            # No stray .tmp left behind.
            leftovers = list(sysroot.rglob("*.tmp"))
            self.assertEqual(leftovers, [], f"stray tmp files: {leftovers}")

    def test_missing_policy_build_refusal_execute(self):
        self.assertTrue(INSTALL.is_file(), f"missing required {INSTALL}")
        self.assertTrue(POLICY_SRC.is_file(), f"missing required {POLICY_SRC}")
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-build-") as tmp:
            proj_ok = Path(tmp) / "proj-ok"
            proj_bad = Path(tmp) / "proj-bad"
            for proj in [proj_ok, proj_bad]:
                (proj / "builder/diagnostics").mkdir(parents=True)
                for src in [SUP_SRC, GUARD_SRC, ENV_SRC, SVC_SRC, SDDM_PRIV_SRC, TTY2_SRC,
                            TEXT_LOGIN, TEXT_PROOF, TEXT_BASHRC, TEXT_GETTY]:
                    shutil.copy(src, proj / "builder/diagnostics" / src.name)
            shutil.copy(POLICY_SRC, proj_ok / "builder/diagnostics" / POLICY_SRC.name)
            # proj_bad has no policy.json
            for proj, should_pass in [(proj_ok, True), (proj_bad, False)]:
                script = f"""
add_file() {{ echo "ADD $1 $2"; return 0; }}
add_runscript() {{ echo "RUNSCRIPT"; return 0; }}
. "{INSTALL.as_posix()}"
KESTREL_PROJECT="{proj.as_posix()}" build
echo "build=$?"
"""
                proc = run_sh(script)
                if should_pass:
                    self.assertIn("build=0", proc.stdout, proc.stderr + proc.stdout)
                    self.assertIn("kestrel-graphics-sddm.service", proc.stdout)
                    self.assertIn("kestrel-graphics-policy.json", proc.stdout)
                else:
                    self.assertIn("build=1", proc.stdout, proc.stderr + proc.stdout)

    def test_no_unguarded_sddm_with_and_without_text_execute(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        # Without text hook.
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-noguard-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=True)
            units = sysroot / "etc/systemd/system"
            script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=0", proc.stdout, proc.stderr + proc.stdout)
            self.assertEqual(os.readlink(units / "display-manager.service"), "/dev/null")
            self.assertEqual(os.readlink(units / "sddm.service"), "/dev/null")
            self.assertFalse((units / "graphical.target.wants/kestrel-graphics.service").exists())
            self.assertFalse((units / "graphical.target.wants/display-manager.service").exists())
            priv = (units / "kestrel-graphics-sddm.service").read_text()
            self.assertNotIn("WantedBy=", priv)
        # With text hook state: stage text hook (patched for fixture paths) then graphics.
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-withtext-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=True)
            units = sysroot / "etc/systemd/system"
            patched = Path(tmp) / "kestrel_text_patched"
            text = TEXT_HOOK.read_text()
            # Isolate fixture: rewrite fixed /sysroot and /etc prefixes.
            text = text.replace("/sysroot", str(sysroot)).replace("/etc/kestrel-text", str(etc) + "/kestrel-text")
            text = text.replace("/etc/systemd", str(sysroot) + "/etc/systemd")
            # getty template path /usr/lib stays absolute (target of symlink).
            patched.write_text(text)
            text_script = f"""
getarg() {{
  case "$1" in
    kestrel_textboot) echo "1" ;;
    kestrel_graphics) echo "" ;;
    kestrel_console) echo "" ;;
    *) echo "" ;;
  esac
}}
mountpoint() {{ return 0; }}
. "{patched.as_posix()}"
run_latehook
echo "text=$?"
"""
            proc_t = run_sh(text_script)
            # Text hook with empty console returns 1 from stage but latehook 0; accept either.
            self.assertEqual(proc_t.returncode, 0, proc_t.stderr + proc_t.stdout)
            # Now stage graphics into same fixture.
            script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "1", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=0", proc.stdout, proc.stderr + proc.stdout)
            # Still masked, no unmasking, no graphical enablement.
            self.assertEqual(os.readlink(units / "display-manager.service"), "/dev/null")
            self.assertEqual(os.readlink(units / "sddm.service"), "/dev/null")
            self.assertFalse((units / "graphical.target.wants/kestrel-graphics.service").exists())
            self.assertTrue((units / "multi-user.target.wants/kestrel-graphics.service").is_symlink())

    def test_tty2_fallback_retained(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        text = TTY2_SRC.read_text()
        self.assertIn("kestrel_graphics=1", text)
        self.assertIn("kestrel-text-login", text)
        self.assertIn("ExecStart=", text)
        src = TEXT_GETTY.read_text().splitlines()
        dst = text.splitlines()
        src_exec = [l for l in src if l.strip().startswith("ExecStart")]
        dst_exec = [l for l in dst if l.strip().startswith("ExecStart")]
        self.assertEqual(src_exec, dst_exec)
        # Staged drop-in is byte-exact after execution.
        with tempfile.TemporaryDirectory(prefix="dt25-gfx-tty2-") as tmp:
            sysroot, etc = make_live_fixture(tmp, with_stock_gui=False)
            script = hook_script(HOOK.as_posix(), "kestrel_stage_graphics\necho \"stage=$?\"\n")
            env = {"KESTREL_SYSROOT": str(sysroot), "KESTREL_ETC": str(etc),
                   "MOCK_GFX": "1", "MOCK_TEXT": "", "MOCK_MOUNTPOINT_RC": "0",
                   "MOCK_FINDMNT_RC": "0", "MOCK_FSTYPE": "overlay"}
            proc = run_sh(script, env_extra=env)
            self.assertIn("stage=0", proc.stdout, proc.stderr + proc.stdout)
            staged = (sysroot / "etc/systemd/system/getty@tty2.service.d/90-kestrel-live.conf").read_bytes()
            self.assertEqual(staged, TTY2_SRC.read_bytes())

    def test_source_helpers_byte_exact(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        install_text = INSTALL.read_text()
        for src in [TEXT_LOGIN, TEXT_PROOF, TEXT_BASHRC]:
            self.assertIn(src.name, install_text, f"install must stage {src.name}")
        hook_text = HOOK.read_text()
        for etc_name in ["/etc/kestrel-text-login", "/etc/kestrel-text-proof",
                         "/etc/kestrel-text-bashrc",
                         "/etc/kestrel-graphics-supervisor", "/etc/kestrel-graphics-guard",
                         "/etc/kestrel-graphics-env", "/etc/kestrel-graphics-service",
                         "/etc/kestrel-graphics-sddm", "/etc/kestrel-graphics-tty2",
                         "/etc/kestrel-graphics-policy"]:
            self.assertIn(etc_name, install_text + hook_text,
                          f"staging chain must reference {etc_name}")
        for src in [SUP_SRC, ENV_SRC, SVC_SRC, SDDM_PRIV_SRC, TTY2_SRC, GUARD_SRC,
                    TEXT_LOGIN, TEXT_PROOF, TEXT_BASHRC, TEXT_GETTY, POLICY_SRC]:
            self.assertTrue(src.is_file(), f"missing source {src}")
            self.assertGreater(src.stat().st_size, 10, f"empty source {src}")

    def test_install_hook_mapping_consistent(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        install_text = INSTALL.read_text()
        hook_text = HOOK.read_text()
        pairs = [
            ("kestrel-graphics-supervisor.py", "/etc/kestrel-graphics-supervisor"),
            ("kestrel_graphics_guard.py", "/etc/kestrel-graphics-guard"),
            ("kestrel-graphics-env.conf", "/etc/kestrel-graphics-env"),
            ("kestrel-graphics.service", "/etc/kestrel-graphics-service"),
            ("kestrel-graphics-sddm.service", "/etc/kestrel-graphics-sddm"),
            ("kestrel-graphics-policy.json", "/etc/kestrel-graphics-policy"),
            ("kestrel-graphics-tty2.conf", "/etc/kestrel-graphics-tty2"),
            ("kestrel-text-login.sh", "/etc/kestrel-text-login"),
            ("kestrel-text-proof.sh", "/etc/kestrel-text-proof"),
            ("kestrel-text-bashrc", "/etc/kestrel-text-bashrc"),
        ]
        for src_name, etc_name in pairs:
            self.assertIn(src_name, install_text, f"install missing {src_name}")
            self.assertIn(etc_name, install_text, f"install missing {etc_name}")
            base = etc_name.split("/")[-1]
            self.assertIn(base, hook_text, f"hook must reference {etc_name}")
            self.assertIn("cp ", hook_text, "hook must copy staged inputs")
        for src in [SUP_SRC, ENV_SRC, SVC_SRC, SDDM_PRIV_SRC]:
            h = hashlib.sha256(src.read_bytes()).hexdigest()
            self.assertEqual(len(h), 64)

    def test_missing_conditions_fail_closed(self):
        for p in REQUIRED:
            self.assertTrue(p.is_file(), f"missing required {p}")
        hook_text = HOOK.read_text()
        self.assertIn("KESTREL_GRAPHICS_STAGE_FAILED", hook_text)
        self.assertIn("return 0", hook_text)
        self.assertIn("kestrel_graphics_rollback", hook_text)
        self.assertIn("overlay", hook_text)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName("__main__"))
    import json as _json
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(getattr(result, "skipped", [])),
              "synthetic_fixtures_only": True, "native_hardware_validated": False}
    print(_json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
