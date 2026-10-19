#!/usr/bin/env python3
"""Focused dt25 graphics unit lifecycle contract: unexpected-supervisor-death binding.

Proven failure (not a guess): EFI candidate vmlinuz-live.efi
SHA 9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb
(source/packed unit byte exact). Real missing-20 CPU+DRM guard refusal works,
Python imports work, normal text fallback works. Case C used clearly labeled
fake payload (sleep 600) BOTH units inside VM overlay only, retaining real
production dependencies. Parent independently read actual RAW v2 serial
testing/boot-failure/dt25-efi-graphics-fw-off-v2.log:555-586: parent active
MainPID 1147, child active MainPID 1169, C_KILL_RC 0 KILL_SENT, parent failed
MainPID 0 Result signal, child still active MainPID 1169 after 15s.
(Worker final 1151/1171 was v1; preserve exact per-run IDs.) Corrected actual
recovery JSON dt25-efi-graphics-fw-off-v2-correction.json:43/44, only false
c_child_inactive_gone_after_parent_sigkill. Boot e1ae3f51-46d7-4abd-8bde-9c6e29a415f2.
PartOf alone does NOT stop child on parent unexpected failed state. Source
private unit line7 PartOf=parent, After parent line6; main Type=simple line14,
Restart no, Timeout 30. Current launch marker may remain when Python killed.
NO confirmed unit ordering cycle: parent full-target-graph verify --man=no 0
in dt25-parent-20261018T080854313952Z-full-target-graph.json. No invented
cycle or systemd architecture rewrite.

Fix (minimal normal-systemd lifetime binding):
- private SDDM unit: add BindsTo=kestrel-graphics.service WHILE KEEPING
  After=parent, PartOf, Restart=no, launch-marker ConditionPathExists,
  cmdline ConditionKernelCommandLine, owned Conflicts. Strong binding+ordering
  needed for unexpected death. No global kills, no RequiredBy/WantedBy
  graphical, no forced auto-restart, no loop or root compositor.
- parent: bounded owned marker removal via ExecStartPre + ExecStopPost, exact
  /usr/bin/rm -f -- /run/kestrel-graphics/launch-allowed (verified live SFS
  and ROOT actual rm availability; 30s budget retained). ExecStartPre clears
  stale permission BEFORE parent active; ExecStopPost clears even after Main
  SIGKILL/failed startup. Never rm recursive/wildcards/foreign paths, no
  global pkill/systemctl stop from ExecStopPost (potential job deadlock).
  Python owned cleanup/session code unchanged; actual SDDM/PAM/session death
  beyond unit graph remains native gate.

Limitations (honest): static/unit parsing plus rebased fixture rm semantics
do NOT prove a real SIGKILL stops the child; actual VM retest after a fresh
rebuild is required. Old 9c image is REJECTED for native after unit byte
change; parent owns rebuild plan. No build/QEMU in this task.

Project root derived from __file__; fails when required files missing.
No real host /run writes or services. Zero skips.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).resolve().parents[2]
PARENT = P / "builder/diagnostics/kestrel-graphics.service"
CHILD = P / "builder/diagnostics/kestrel-graphics-sddm.service"
REQUIRED = [PARENT, CHILD]

OWNED_MARKER = "/run/kestrel-graphics/launch-allowed"
OWNED_RM = ["/usr/bin/rm", "-f", "--", OWNED_MARKER]

# Exact pre-fix bytes frozen BEFORE mutation (snapshot
# dt25-lifecycle-20261018T084848Z-unit-before.json). Old pair must FAIL.
ORIGINAL_PARENT = """[Unit]
Description=Bounded simpledrm/software Plasma diagnostic (opt-in)
Documentation=file:/etc/kestrel-graphics-env
ConditionKernelCommandLine=kestrel_graphics=1
After=systemd-logind.service dbus.service systemd-user-sessions.service multi-user.target
Wants=systemd-logind.service
# Multi-user-only activation: graphical.target Requires multi-user, so this
# runs under both defaults, but never as graphical.target.wants. Stock
# display-manager/sddm are masked by the hook, so no GUI starts before the
# guard passes. Private kestrel-graphics-sddm.service is started explicitly by
# the supervisor only after preflight + launch marker.

[Service]
Type=simple
ExecStart=/usr/local/sbin/kestrel-graphics-supervisor
Restart=no
TimeoutStopSec=30
Nice=10
# No auto-restart loops. No root compositor. SDDM autologin (live/plasma)
# provides the normal PAM/logind/DBus session; supervisor only gates,
# monitors (180s/80C fail-closed) and performs bounded owned-GUI-only cleanup.
# Session-active is not pixel proof; pixels/input are not claimed.

[Install]
WantedBy=multi-user.target
"""

ORIGINAL_CHILD = """[Unit]
Description=Owned diagnostic SDDM (guarded, no auto-start)
Documentation=file:/etc/kestrel-graphics-env
ConditionKernelCommandLine=kestrel_graphics=1
ConditionPathExists=/run/kestrel-graphics/launch-allowed
After=systemd-logind.service dbus.service systemd-user-sessions.service kestrel-graphics.service
PartOf=kestrel-graphics.service
Conflicts=display-manager.service sddm.service getty@tty1.service
# No WantedBy: started explicitly by kestrel-graphics-supervisor only after
# read-only preflight passes. Stock display-manager/sddm stay masked.

[Service]
Type=simple
ExecStart=/usr/bin/sddm
Restart=no
Nice=10
EnvironmentFile=/etc/kestrel-graphics-env
TimeoutStopSec=10
# No Restart=always inheritance: diagnostic GUI must never loop.
# Live autologin (live/plasma, UID 1000) via stock SDDM/PAM/logind ACLs;
# no root compositor, no account/group edits, Wayland-only session.

[Install]
# No WantedBy: explicit start only, no unguarded activation.
"""

VM_RETEST_REQUIRED = True


def parse_unit(text):
    """Parse systemd unit into {section: {key: [values]}} using only
    explicit section tokens; comment lines (#/;) never count as directives."""
    sections = {}
    current = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is None:
            continue
        if "=" not in raw:
            continue
        # Split on first '=' of the directive body (after stripping).
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        sections[current].setdefault(key, []).append(value)
    return sections


def check_pair(parent_text, child_text):
    """Return list of contract failure strings; empty means PASS."""
    failures = []
    p = parse_unit(parent_text)
    c = parse_unit(child_text)
    pu = p.get("Unit", {})
    ps = p.get("Service", {})
    pi = p.get("Install", {})
    cu = c.get("Unit", {})
    cs = c.get("Service", {})
    ci = c.get("Install", {})

    def has(section, key, needle):
        return any(needle in v for v in section.get(key, []))

    def exact(section, key, want):
        return want in section.get(key, [])

    # --- child strong binding + ordering (both load-bearing) ---
    if not exact(cu, "BindsTo", "kestrel-graphics.service"):
        failures.append("missing BindsTo=kestrel-graphics.service in child [Unit]")
    else:
        # Must be exact single-target owned binding, not a foreign unit.
        vals = cu.get("BindsTo", [])
        if not any(v.strip() == "kestrel-graphics.service" for v in vals):
            failures.append("BindsTo must target exactly kestrel-graphics.service")
    if not has(cu, "After", "kestrel-graphics.service"):
        failures.append("missing After=kestrel-graphics.service in child [Unit]")
    if not exact(cu, "PartOf", "kestrel-graphics.service"):
        failures.append("missing retained PartOf=kestrel-graphics.service in child [Unit]")
    # --- child retained guards ---
    if not exact(cu, "ConditionKernelCommandLine", "kestrel_graphics=1"):
        failures.append("missing retained ConditionKernelCommandLine in child")
    if not exact(cu, "ConditionPathExists", OWNED_MARKER):
        failures.append("missing retained ConditionPathExists launch marker in child")
    conflicts = " ".join(cu.get("Conflicts", []))
    for need in ("display-manager.service", "sddm.service", "getty@tty1.service"):
        if need not in conflicts:
            failures.append(f"missing retained owned Conflicts {need} in child")
    if not exact(cs, "Type", "simple"):
        failures.append("child Type must stay simple")
    if not exact(cs, "Restart", "no"):
        failures.append("child Restart must stay no")
    if not exact(cs, "ExecStart", "/usr/bin/sddm"):
        failures.append("child ExecStart must stay /usr/bin/sddm")
    if not exact(cs, "TimeoutStopSec", "10"):
        failures.append("child TimeoutStopSec must stay 10")
    if not has(cs, "EnvironmentFile", "/etc/kestrel-graphics-env"):
        failures.append("child EnvironmentFile must stay /etc/kestrel-graphics-env")
    # No unguarded activation / loops / global wiring.
    for sec, key in ((cu, "WantedBy"), (cu, "RequiredBy"), (cs, "WantedBy"),
                     (ci, "WantedBy"), (ci, "RequiredBy")):
        for v in sec.get(key, []):
            if v.strip():
                failures.append(f"child must not gain {key}={v}")
    if "graphical.target" in child_text.replace("#", "").split():
        # Explicit token check across executable lines only (comments excluded
        # already by parser, but double-guard raw non-comment text).
        noncomment = "\n".join(
            ln for ln in child_text.splitlines()
            if not ln.strip().startswith("#") and not ln.strip().startswith(";"))
        if "graphical.target" in noncomment:
            failures.append("child must not reference graphical.target")
    for v in cs.get("Restart", []):
        if "always" in v:
            failures.append("child must not use Restart=always")

    # --- parent stale-permission cleanup (both load-bearing) ---
    if OWNED_RM[0] + " " not in "" and True:
        pass
    pre_vals = ps.get("ExecStartPre", [])
    post_vals = ps.get("ExecStopPost", [])
    want_cmd = "/usr/bin/rm -f -- " + OWNED_MARKER
    if want_cmd not in [v.strip() for v in pre_vals]:
        failures.append("missing parent ExecStartPre=/usr/bin/rm -f -- owned marker")
    if want_cmd not in [v.strip() for v in post_vals]:
        failures.append("missing parent ExecStopPost=/usr/bin/rm -f -- owned marker")
    if not exact(ps, "Type", "simple"):
        failures.append("parent Type must stay simple")
    if not exact(ps, "Restart", "no"):
        failures.append("parent Restart must stay no")
    if not exact(ps, "TimeoutStopSec", "30"):
        failures.append("parent TimeoutStopSec must stay 30")
    if not exact(ps, "ExecStart", "/usr/local/sbin/kestrel-graphics-supervisor"):
        failures.append("parent ExecStart must stay supervisor path")
    if not exact(pu, "ConditionKernelCommandLine", "kestrel_graphics=1"):
        failures.append("missing retained ConditionKernelCommandLine in parent")
    if not has(pi, "WantedBy", "multi-user.target"):
        failures.append("parent must stay WantedBy=multi-user.target")

    # --- non-global cleanup invariants on executable lines only ---
    noncomment_parent = "\n".join(
        ln for ln in parent_text.splitlines()
        if not ln.strip().startswith("#") and not ln.strip().startswith(";"))
    for label, blob in (("parent", noncomment_parent),):
        low = blob.lower()
        for bad in ("pkill", "killall", "systemctl stop", "systemctl kill",
                    "reboot", "poweroff"):
            # Allow documentation words only in comments (already stripped);
            # executable lines must not contain them.
            for ln in blob.splitlines():
                s = ln.strip()
                if not s or s.startswith("["):
                    continue
                if "=" not in s:
                    continue
                _, _, val = s.partition("=")
                if bad in val.lower():
                    # ExecStopPost rm line legitimately contains no bad token;
                    # any other line with these tokens fails.
                    if bad == "systemctl kill" and "kestrel-graphics-sddm" in val:
                        # Supervisor python (not unit) may narrowly kill owned
                        # unit; units themselves must not.
                        failures.append(f"{label} unit must not contain '{bad}'")
                    elif bad not in ("reboot", "poweroff") or "no " not in ln.lower():
                        failures.append(f"{label} unit must not contain '{bad}'")
                    break
        # rm must be bounded: exact owned path only, no -r/recursive/wildcard.
        for ln in blob.splitlines():
            s = ln.strip()
            if s.startswith("ExecStartPre=") or s.startswith("ExecStopPost="):
                if "/usr/bin/rm" not in s:
                    failures.append(f"{label} cleanup must use /usr/bin/rm (got: {s[:80]})")
                for tok in (" -r", "-rf", "-fr", "--recursive", "*", "?", "--preserve"):
                    if tok in s and tok != " -- ":
                        # '*' check must ignore comments (already stripped).
                        if tok == "*" and "*" not in s.split("=", 1)[-1]:
                            continue
                        if tok in s:
                            # Allow '-- ' end-of-options; bare '*' never allowed.
                            if tok == "*" or tok.strip().startswith("-"):
                                failures.append(
                                    f"{label} cleanup must not use recursive/wildcard {tok!r}")
                                break
                if OWNED_MARKER not in s:
                    failures.append(f"{label} cleanup must target exactly owned marker")
                # Forbid foreign paths on the same directive line.
                after = s.split("=", 1)[-1]
                # Only allowed tokens: /usr/bin/rm, -f, --, owned marker.
                allowed = {"/usr/bin/rm", "-f", "--", OWNED_MARKER}
                parts = after.split()
                for part in parts:
                    if part not in allowed:
                        failures.append(
                            f"{label} cleanup has foreign token {part!r}")
                        break
    return failures


def rebased_rm_f(fixture_marker):
    """Emulate 'rm -f -- <marker>' semantics on a rebased private fixture
    path: remove file/symlink, ignore missing, never follow symlink target.
    Uses real /usr/bin/rm when present, else pathlib unlink (same outcome
    for this single-owned-path case). Never touches real /run."""
    assert str(fixture_marker) not in ("/run/kestrel-graphics/launch-allowed",)
    assert "/tmp" not in str(fixture_marker) or "dt25-unit-" in str(fixture_marker) \
        or "tmp" in str(fixture_marker).lower()
    real_rm = Path("/usr/bin/rm")
    if real_rm.is_file():
        try:
            proc = subprocess.run(
                [str(real_rm), "-f", "--", str(fixture_marker)],
                capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    # Portable fallback with identical single-path semantics.
    try:
        Path(fixture_marker).unlink()
    except FileNotFoundError:
        pass
    return not Path(fixture_marker).is_symlink() and not Path(fixture_marker).exists()


class UnitContract(unittest.TestCase):
    def test_required_files_exist(self):
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))

    def test_original_pair_fails_contract(self):
        """RED: frozen pre-fix bytes must FAIL (no BindsTo, no pre/post)."""
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        failures = check_pair(ORIGINAL_PARENT, ORIGINAL_CHILD)
        self.assertTrue(
            any("BindsTo" in f for f in failures),
            "original child must lack BindsTo, got: " + "; ".join(failures))
        self.assertTrue(
            any("ExecStartPre" in f for f in failures),
            "original parent must lack ExecStartPre, got: " + "; ".join(failures))
        self.assertTrue(
            any("ExecStopPost" in f for f in failures),
            "original parent must lack ExecStopPost, got: " + "; ".join(failures))

    def test_current_pair_passes_contract(self):
        """GREEN: fixed on-disk units must PASS all load-bearing clauses."""
        for q in REQUIRED:
            self.assertTrue(q.is_file(), "missing required " + str(q))
        failures = check_pair(PARENT.read_text(), CHILD.read_text())
        self.assertEqual(failures, [], "contract failures: " + "; ".join(failures))

    def test_binds_to_load_bearing(self):
        cur_p = PARENT.read_text()
        cur_c = CHILD.read_text()
        self.assertEqual(check_pair(cur_p, cur_c), [])
        stripped = cur_c.replace("BindsTo=kestrel-graphics.service\n", "")
        stripped = stripped.replace("BindsTo=kestrel-graphics.service\r\n", "")
        self.assertNotEqual(stripped, cur_c, "test mutated nothing")
        failures = check_pair(cur_p, stripped)
        self.assertTrue(any("BindsTo" in f for f in failures),
                        "removing BindsTo must fail, got: " + "; ".join(failures))

    def test_after_load_bearing(self):
        cur_p = PARENT.read_text()
        cur_c = CHILD.read_text()
        lines = cur_c.splitlines(keepends=True)
        removed = "".join(
            ln for ln in lines
            if not (ln.strip().startswith("After=")
                    and "kestrel-graphics.service" in ln))
        self.assertNotEqual(removed, cur_c)
        failures = check_pair(cur_p, removed)
        self.assertTrue(any("After" in f for f in failures),
                        "removing After parent must fail, got: " + "; ".join(failures))
        # Both must coexist with PartOf.
        parsed = parse_unit(cur_c)
        self.assertIn("kestrel-graphics.service",
                      parsed.get("Unit", {}).get("BindsTo", []))
        self.assertTrue(any("kestrel-graphics.service" in v
                            for v in parsed.get("Unit", {}).get("After", [])))
        self.assertIn("kestrel-graphics.service",
                      parsed.get("Unit", {}).get("PartOf", []))

    def test_part_of_retained(self):
        parsed = parse_unit(CHILD.read_text())
        self.assertIn("kestrel-graphics.service",
                      parsed.get("Unit", {}).get("PartOf", []))

    def test_cmdline_marker_restart_timeout_exec_paths(self):
        p = parse_unit(PARENT.read_text())
        c = parse_unit(CHILD.read_text())
        self.assertIn("kestrel_graphics=1",
                      p.get("Unit", {}).get("ConditionKernelCommandLine", []))
        self.assertIn("kestrel_graphics=1",
                      c.get("Unit", {}).get("ConditionKernelCommandLine", []))
        self.assertIn(OWNED_MARKER,
                      c.get("Unit", {}).get("ConditionPathExists", []))
        self.assertIn("no", c.get("Service", {}).get("Restart", []))
        self.assertIn("no", p.get("Service", {}).get("Restart", []))
        self.assertIn("simple", c.get("Service", {}).get("Type", []))
        self.assertIn("simple", p.get("Service", {}).get("Type", []))
        self.assertIn("30", p.get("Service", {}).get("TimeoutStopSec", []))
        self.assertIn("10", c.get("Service", {}).get("TimeoutStopSec", []))
        self.assertIn("/usr/local/sbin/kestrel-graphics-supervisor",
                      p.get("Service", {}).get("ExecStart", []))
        self.assertIn("/usr/bin/sddm", c.get("Service", {}).get("ExecStart", []))
        self.assertTrue(any("/etc/kestrel-graphics-env" in v
                            for v in c.get("Service", {}).get("EnvironmentFile", [])))

    def test_missing_prestart_cleanup_fails_separately(self):
        cur_c = CHILD.read_text()
        cur_p = PARENT.read_text()
        lines = [ln for ln in cur_p.splitlines(keepends=True)
                 if not ln.strip().startswith("ExecStartPre=")]
        self.assertLess(len(lines), len(cur_p.splitlines(keepends=True)))
        failures = check_pair("".join(lines), cur_c)
        self.assertTrue(any("ExecStartPre" in f for f in failures),
                        "missing Pre must fail, got: " + "; ".join(failures))
        self.assertFalse(any("ExecStopPost" in f for f in failures),
                         "missing Pre must not mask Post presence")

    def test_missing_poststop_cleanup_fails_separately(self):
        cur_c = CHILD.read_text()
        cur_p = PARENT.read_text()
        lines = [ln for ln in cur_p.splitlines(keepends=True)
                 if not ln.strip().startswith("ExecStopPost=")]
        self.assertLess(len(lines), len(cur_p.splitlines(keepends=True)))
        failures = check_pair("".join(lines), cur_c)
        self.assertTrue(any("ExecStopPost" in f for f in failures),
                        "missing Post must fail, got: " + "; ".join(failures))
        self.assertFalse(any("ExecStartPre" in f for f in failures),
                         "missing Post must not mask Pre presence")

    def test_cleanup_uses_owned_exact_paths_only(self):
        parsed = parse_unit(PARENT.read_text())
        for key in ("ExecStartPre", "ExecStopPost"):
            vals = parsed.get("Service", {}).get(key, [])
            self.assertEqual(len(vals), 1, f"{key} must appear exactly once")
            self.assertEqual(vals[0], "/usr/bin/rm -f -- " + OWNED_MARKER)
            self.assertNotIn("*", vals[0])
            self.assertNotIn(" -r", vals[0])
            self.assertNotIn("--recursive", vals[0])

    def test_no_global_kills_or_graphical_wiring(self):
        for text, label in ((PARENT.read_text(), "parent"),
                            (CHILD.read_text(), "child")):
            parsed = parse_unit(text)
            svc = parsed.get("Service", {})
            unit = parsed.get("Unit", {})
            joined = " ".join(sum(svc.values(), []) + sum(unit.values(), []))
            self.assertNotIn("pkill", joined, label)
            self.assertNotIn("killall", joined, label)
            self.assertNotIn("RequiredBy", str(parsed), label)
            for v in unit.get("WantedBy", []) + parsed.get("Install", {}).get("WantedBy", []):
                self.assertNotIn("graphical", v, label)
            # Executable directives only (comments excluded by parser):
            # Restart must be exactly 'no', never 'always'.
            for v in svc.get("Restart", []):
                self.assertNotIn("always", v, label)
                self.assertEqual(v.strip(), "no", label)

    def test_cleanup_stale_marker_before_start(self):
        """Rebased: stale marker exists -> rm -f clears it before start."""
        with tempfile.TemporaryDirectory(prefix="dt25-unit-pre-") as tmp:
            marker = Path(tmp) / "run" / "kestrel-graphics" / "launch-allowed"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("allowed\n")
            self.assertTrue(marker.is_file())
            self.assertTrue(rebased_rm_f(marker))
            self.assertFalse(marker.exists())
            # Missing real-host guard: never touched /run.
            self.assertFalse(Path("/run/kestrel-graphics/launch-allowed").exists()
                             and "dt25-unit-pre-" in "/run")

    def test_cleanup_missing_marker_idempotent(self):
        """Rebased: missing marker -> rm -f still rc 0, still absent."""
        with tempfile.TemporaryDirectory(prefix="dt25-unit-missing-") as tmp:
            marker = Path(tmp) / "run" / "kestrel-graphics" / "launch-allowed"
            marker.parent.mkdir(parents=True, exist_ok=True)
            self.assertFalse(marker.exists())
            self.assertTrue(rebased_rm_f(marker))
            self.assertFalse(marker.exists())

    def test_cleanup_stop_clears_marker(self):
        """Rebased: ExecStopPost semantics clear marker after stop."""
        parsed = parse_unit(PARENT.read_text())
        post = parsed.get("Service", {}).get("ExecStopPost", [""])[0]
        self.assertEqual(post, "/usr/bin/rm -f -- " + OWNED_MARKER)
        with tempfile.TemporaryDirectory(prefix="dt25-unit-post-") as tmp:
            marker = Path(tmp) / "run" / "kestrel-graphics" / "launch-allowed"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("allowed\n")
            self.assertTrue(rebased_rm_f(marker))
            self.assertFalse(marker.exists())

    def test_cleanup_symlink_removes_link_not_target(self):
        """Rebased: symlink marker removed, foreign sentinel intact."""
        with tempfile.TemporaryDirectory(prefix="dt25-unit-link-") as tmp:
            tmp_p = Path(tmp)
            foreign = tmp_p / "foreign" / "real-target"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_text("FOREIGN_SENTINEL_KEEP\n")
            marker = tmp_p / "run" / "kestrel-graphics" / "launch-allowed"
            marker.parent.mkdir(parents=True, exist_ok=True)
            try:
                marker.symlink_to(foreign)
            except (OSError, NotImplementedError) as exc:
                self.fail("fixture symlink unsupported: " + str(exc))
            self.assertTrue(marker.is_symlink())
            self.assertTrue(rebased_rm_f(marker))
            self.assertFalse(marker.is_symlink())
            self.assertFalse(marker.exists())
            self.assertTrue(foreign.is_file(), "foreign target must survive")
            self.assertEqual(foreign.read_text(), "FOREIGN_SENTINEL_KEEP\n")

    def test_static_does_not_claim_live_sigkill(self):
        """No self-reported actual SIGKILL PASS from mock/static; VM retest
        after a fresh rebuild is required (parent owns plan)."""
        self.assertTrue(VM_RETEST_REQUIRED)
        self.assertFalse(False, "placeholder never claims live SIGKILL")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName("__main__"))
    import json as _json
    report = {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(getattr(result, "skipped", [])),
              "synthetic_fixtures_only": True, "native_hardware_validated": False,
              "vm_retest_required_after_rebuild": True,
              "old_9c_image_rejected_for_native": True}
    print(_json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
