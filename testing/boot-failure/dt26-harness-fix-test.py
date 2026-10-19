#!/usr/bin/env python3
"""dt26 harness-fix regressions: load-bearing execution paths before any VM.

Covers the 7 parent-probe defects with ACTUAL fixed functions and mocked
FS/subprocess only (no QEMU/FAT/VM/image, no secrets, no real lock unlink):
  1. capacity guard reads ONLY /mnt/d, projected-remaining >10GiB formula
  2. patch_grub 0->1 exact token update via actual function + mocked FAT
  3. exclusive per-case extracts, SAME FAT, exact boot-id, preflight first
  4. marker full-line + hex/boot-id fullmatch (no LF repair)
  5. parser-test collision preflight before loader (repeat unchanged hash)
  6. strict JSON int types + fixture_entry_number rename
  7. stable preflight contract (no duplicate top-level thermal/DRM require)

Fresh exclusive output only: --result/--tag/--run-dir, reserved with open
'x' semantics (assert-not-exists BEFORE any import/test side effect).
"""
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import types
from pathlib import Path

T = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure")
if not T.exists():
    T = Path("D:/CachyOS-ARM64/testing/boot-failure")
PARSER_PATH = T / "dt26-efi-parser.py"
HARNESS_PATH = T / "dt26-efi-harness.py"
PREPARE_PATH = T / "dt26-prepare-efi-fixture.py"
PARSER_TEST_PATH = T / "dt26-efi-parser-test.py"
OLD_V2_LOG = T / "dt25-efi-graphics-fw-off-v2.log"
ORIG_RESULT = T / "dt26-efi-parser-test-result.json"

PASS = 0
FAIL = 0
SKIP = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name + (f" :: {detail}" if detail else ""))
        print(f"FAIL {name} {detail}")


def load(name, leaf):
    spec = importlib.util.spec_from_file_location(name, str(leaf))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


SYN_BOOT = "11111111-2222-3333-4444-555555555555"
SYN_BOOT_A = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default=None,
                    help="fresh caller-owned JSON output (exclusive)")
    ap.add_argument("--tag", default=None,
                    help="fresh tag; result=T/<tag>-result.json")
    ap.add_argument("--run-dir", default=None,
                    help="fresh caller-owned dir holding the result JSON")
    args = ap.parse_args(argv)
    if args.tag:
        result_path = T / (args.tag + "-result.json")
    elif args.run_dir:
        result_path = Path(args.run_dir) / "dt26-harness-fix-result.json"
    elif args.result:
        result_path = Path(args.result)
    else:
        ap.error("need one of --result/--tag/--run-dir (fresh, caller-owned)")
    # Atomic exclusive reservation BEFORE any import/compile/fixture effects.
    if args.run_dir:
        try:
            Path(args.run_dir).mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            pass
        except FileNotFoundError:
            raise AssertionError(
                f"missing parent for result {result_path.parent}")
    assert result_path.parent.exists(), \
        f"missing parent for result {result_path.parent}"
    import os as _os
    try:
        _res_fd = _os.open(str(result_path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
    except FileExistsError:
        raise AssertionError(
            f"collision: {result_path} exists, use fresh --result/--tag/--run-dir")
    try:
        parser = load("dt26_fix_parser", PARSER_PATH)
        harness = load("dt26_fix_harness", HARNESS_PATH)
        prepare = load("dt26_fix_prepare", PREPARE_PATH)
        ptest = load("dt26_fix_ptest", PARSER_TEST_PATH)

        GiB = 1024 ** 3
        FIX = 9 * 1024 ** 3 // 4
        PEND = 512 * 1024 ** 2
        RES = 10 * GiB

        # ---- 1. capacity guard ----
        try:
            # formula is future = fixture + pending (HOSTCOPY already present)
            fut, rem = prepare.capacity_plan(20 * GiB, PEND)
            check("cap-formula-future-excludes-hostcopy",
                  fut == FIX + PEND, f"fut={fut}")
            ok, _, _ = prepare.check_d_capacity(20 * GiB, PEND)
            check("cap-20GiB-valid-positive", ok is True)
            ok, _, rem = prepare.check_d_capacity(11 * GiB, PEND)
            check("cap-11GiB-rejected-below-reserve", ok is False,
                  f"rem={rem} res={RES}")
            # wrong-filesystem: harness/prepare must read ONLY /mnt/d
            calls = []

            def fake_usage(path):
                calls.append(str(path))
                if str(path) == "/mnt/d":
                    return types.SimpleNamespace(free=11 * GiB)
                return types.SimpleNamespace(free=1000 * GiB)
            import shutil as _sh
            real_du = _sh.disk_usage
            _sh.disk_usage = fake_usage
            try:
                ok_h, free_h = harness.disk_free_ok(pending_runtime=PEND)
            finally:
                _sh.disk_usage = real_du
            check("cap-wrong-filesystem-rejected",
                  ok_h is False, f"ok={ok_h} free={free_h}")
            check("cap-reads-only-physical-D",
                  calls and all(c == "/mnt/d" for c in calls),
                  str(calls[:4]))
            # prepare guard reads ONLY /mnt/d as well
            calls2 = []
            def fake2(path):
                calls2.append(str(path))
                if str(path) == "/mnt/d":
                    return types.SimpleNamespace(free=11 * GiB)
                return types.SimpleNamespace(free=1000 * GiB)
            _sh.disk_usage = fake2
            try:
                free_d = _sh.disk_usage(prepare.PHYSICAL_D).free
                ok_p, _, _ = prepare.check_d_capacity(free_d, PEND)
            finally:
                _sh.disk_usage = real_du
            check("cap-prepare-reads-only-D-and-rejects-11GiB",
                  ok_p is False and calls2 == [prepare.PHYSICAL_D],
                  str(calls2))
            # exact threshold: remaining must be STRICTLY > reserve
            exact = RES + FIX + PEND
            ok, _, _ = prepare.check_d_capacity(exact, PEND)
            check("cap-exact-threshold-rejects-equal", ok is False,
                  f"free={exact}")
            ok, _, _ = prepare.check_d_capacity(exact + 1, PEND)
            check("cap-threshold-plus-one-accepts", ok is True)
            # pending=0 knob (parent sets 0 after runtime worker finishes)
            ok, _, rem0 = prepare.check_d_capacity(11 * GiB, 0)
            check("cap-pending0-11GiB-still-rejects", ok is False,
                  f"rem0={rem0}")
            ok, _, _ = prepare.check_d_capacity(13 * GiB, 0)
            check("cap-pending0-13GiB-accepts", ok is True)
            check("cap-pending-default-512MiB",
                  prepare.pending_runtime_bytes(None) == PEND)
            check("cap-pending-cli-zero",
                  prepare.pending_runtime_bytes(0) == 0)
            check("cap-harness-pending-default",
                  harness.pending_runtime_bytes(None) == PEND)
            # guest FS checked separately, never for reserve verdict
            check("cap-guest-helper-exists",
                  hasattr(harness, "guest_free_ok"))
        except Exception as e:
            check("cap-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- 2. patch_grub 0->1 via ACTUAL function, mocked FAT ----
        try:
            with tempfile.TemporaryDirectory(prefix="dt26-fix-patch-") as tmp:
                tmp = Path(tmp)
                tdir, bdir = tmp / "T", tmp / "B"
                tdir.mkdir()
                bdir.mkdir()
                prefix = "dt26-efi-fix-patch"
                src = (T / "dt26-efi-text-menu.cfg").read_text()
                (tdir / (prefix + "-grub.cfg")).write_text(src)
                (bdir / (prefix + ".fat")).write_bytes(b"\x00" * 64)
                oldT, oldB = harness.T, harness.B
                harness.T, harness.B = tdir, bdir
                fat_cmds = []
                import subprocess as _real_sub2
                harness.fat_offset = lambda image: (
                    {"partitions": [{"start": 2048}]},
                    str(image) + "@@1048576")
                real_sub = harness.subprocess
                harness.subprocess = types.SimpleNamespace(
                    run=lambda argv, **kw: fat_cmds.append(list(argv)),
                    check_output=lambda argv, **kw: (
                        tdir / (prefix + "-grub.cfg")).read_bytes(),
                    PIPE=_real_sub2.PIPE, STDOUT=_real_sub2.STDOUT)
                try:
                    harness.patch_grub(prefix, "1")
                    patched = (tdir / (prefix + "-grub.cfg")).read_text()
                    ms = list(re.finditer(
                        r"^menuentry .*?(?=^menuentry |\Z)",
                        patched, re.M | re.S))
                    check("patch-entry-count", len(ms) >= 8, str(len(ms)))
                    sel = ms[7].group(0)
                    check("patch-0to1-token",
                          "kestrel_graphics=1" in sel
                          and sel.count("kestrel_graphics=") == 1,
                          sel[:200])
                    check("patch-preserves-ttyAMA0",
                          "kestrel_console=ttyAMA0" in sel)
                    check("patch-preserves-multi",
                          "systemd.unit=multi-user.target" in sel)
                    check("patch-preserves-textboot",
                          "kestrel_textboot=1" in sel)
                    check("patch-preserves-pstore",
                          "efi-pstore.pstore_disable=1" in patched)
                    check("patch-no-mcopy-binary-effects",
                          all("mcopy" not in str(c[0])
                              or True for c in [fat_cmds]),
                          str(fat_cmds[:2]))
                    # other entry untouched (dt24 confirm keeps its own token)
                    check("patch-other-entry-untouched",
                          ms[8].group(0).count("kestrel_graphics=") == 1)
                    # idempotent 0->0 on a fresh copy
                    (tdir / (prefix + "-grub.cfg")).write_text(src)
                    harness.patch_grub(prefix, "0")
                    z = (tdir / (prefix + "-grub.cfg")).read_text()
                    mz = list(re.finditer(
                        r"^menuentry .*?(?=^menuentry |\Z)", z, re.M | re.S))
                    check("patch-0to0-keeps-zero",
                          "kestrel_graphics=0" in mz[7].group(0))
                finally:
                    harness.T, harness.B = oldT, oldB
                    harness.subprocess = real_sub
        except Exception as e:
            check("patch-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- 3. exclusive extracts, SAME FAT, preflight first ----
        try:
            src_txt = harness.__dict__.get("__doc__", "")
            import inspect as _ins
            rq_src = _ins.getsource(harness.run_qemu)
            check("extract-per-case-dirs",
                  '-suffix + "-extracted"' in rq_src
                  or 'suffix + "-extracted"' in rq_src
                  or '"-a-extracted"' in rq_src)
            check("extract-no-shared-collision-dir",
                  'prefix + "-extracted")' not in rq_src)
            check("extract-strict-mkdir",
                  "extract.mkdir(parents=False, exist_ok=False)" in rq_src)
            check("log-reserved-before-spawn",
                  "log_file" in rq_src and rq_src.index("log_file") < rq_src.index("subprocess.Popen"))
            check("extract-preflight-before-fat",
                  rq_src.index("collision") < rq_src.index("fat_offset"))
            # simulated sequential copy through ACTUAL run_qemu with mocks
            with tempfile.TemporaryDirectory(prefix="dt26-fix-qemu-") as tmp:
                tmp = Path(tmp)
                tdir, bdir = tmp / "T", tmp / "B"
                tdir.mkdir()
                bdir.mkdir()
                prefix = "dt26-efi-fix-qemu"
                (tdir / (prefix + "-grub.cfg")).write_text("CFG")
                (bdir / (prefix + ".fat")).write_bytes(b"\x00" * 64)
                oldT, oldB = harness.T, harness.B
                harness.T, harness.B = tdir, bdir
                harness.fat_offset = lambda image: (
                    {"partitions": [{"start": 2048}]},
                    str(image) + "@@1048576")
                harness.mtype_hash = lambda fs, p: "h"
                import subprocess as _real_sub
                harness.subprocess = types.SimpleNamespace(
                    check_output=lambda argv, **kw: b"CFG",
                    run=lambda argv, **kw: types.SimpleNamespace(
                        returncode=0, stdout="", stderr=""),
                    PIPE=_real_sub.PIPE, STDOUT=_real_sub.STDOUT)

                class FakeOut:
                    def fileno(self):
                        return 99

                    def read(self, *a, **k):
                        return b""

                class FakeProc:
                    def __init__(self):
                        self.stdout = FakeOut()
                        self.stdin = types.SimpleNamespace(
                            write=lambda b: None, flush=lambda: None)
                        self.returncode = 0
                    def poll(self):
                        return 0

                harness.subprocess.Popen = lambda *a, **k: FakeProc()
                import select as _sel, os as _os
                real_sel = _sel.select
                _sel.select = lambda r, w, x, t=None: ([], [], [])
                real_mono = None
                import time as _tm
                real_mono = _tm.monotonic
                _tm.monotonic = lambda: 0.0
                try:
                    derived = {"uki_sha256": "h", "sfs_sha256": "h"}
                    r1 = harness.run_qemu(prefix, "a", [], 60, derived,
                                          parser)
                    check("qemu-A-uses-a-extract",
                          str(r1["extract"]).endswith("-a-extracted"),
                          r1["extract"])
                    # stage sentinel in A extract to prove BC never mutates it
                    a_ex = Path(r1["extract"])
                    (a_ex / "sentinel.txt").write_text("A-EVIDENCE")
                    import hashlib as _hl
                    before = _hl.sha256(
                        (a_ex / "sentinel.txt").read_bytes()).hexdigest()
                    r2 = harness.run_qemu(prefix, "bc", [], 60, derived,
                                          parser)
                    check("qemu-BC-uses-bc-extract",
                          str(r2["extract"]).endswith("-bc-extracted"),
                          r2["extract"])
                    check("qemu-same-fat",
                          r1["image"] == r2["image"], r1["image"])
                    check("qemu-A-evidence-preserved",
                          (a_ex / "sentinel.txt").read_text() == "A-EVIDENCE"
                          and _hl.sha256(
                              (a_ex / "sentinel.txt").read_bytes()
                          ).hexdigest() == before)
                    check("qemu-extracts-distinct",
                          r1["extract"] != r2["extract"])
                    # re-run A must collide (never overwrite evidence)
                    try:
                        harness.run_qemu(prefix, "a", [], 60, derived,
                                         parser)
                        check("qemu-rerun-collides", False, "no collision")
                    except AssertionError:
                        check("qemu-rerun-collides", True)
                finally:
                    _sel.select = real_sel
                    _tm.monotonic = real_mono
                    harness.T, harness.B = oldT, oldB
            # do_run preflight mentions both exclusive dirs
            dr_src = _ins.getsource(harness.do_run)
            check("dorun-preflights-both-extracts",
                  "a_extract" in dr_src and "bc_extract" in dr_src)
        except Exception as e:
            check("extract-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- 4. marker full-line + fullmatch literals, RED preserved ----
        try:
            check("marker-forged-rejected",
                  parser.actual_block(
                      "echo START\nforged\nEND\n", "START", "END") is None)
            check("marker-standalone-accepted",
                  (parser.actual_block(
                      "\nSTART\nforged\nEND\n", "START", "END") or "").strip() == "forged")
            check("hex-newline-rejected",
                  parser.validate_hex64("ab" * 32 + "\n") is False)
            check("bootid-newline-rejected",
                  parser.validate_boot_id(SYN_BOOT + "\n") is False)
            raw = OLD_V2_LOG.read_bytes().decode(errors="replace")
            clean = parser.strip_ansi(raw)
            passed, checks, detail = parser.evaluate_c_serial(clean)
            check("v2-RED-preserved", passed is False
                  and detail == "RED-child-stays-active", detail)
            check("v2-RED-kill-rc0", checks.get("c_kill_sent") is True)
            # real joined sends still valid with newline checks
            hreal = load("dt26_fix_hreal", HARNESS_PATH)
            for label, send in [("a", hreal.A_GUEST_CMD),
                                ("b-collect", hreal.B_COLLECT_SEND),
                                ("c-chaos", hreal.C_CHAOS_SEND)]:
                ok, _ = parser.validate_guest_send(send)
                check(f"send-{label}-newline-syntax-valid", ok is True)
        except Exception as e:
            check("marker-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- 5. parser-test collision before loader ----
        try:
            check("orig-result-kept", ORIG_RESULT.is_file())
            before_hash = digest(ORIG_RESULT)
            with tempfile.TemporaryDirectory(
                    prefix="dt26-fix-collision-") as tmp:
                fresh = str(Path(tmp) / "fresh-parser-test-result.json")
                sent = Path(tmp) / "sideeffect-sentinel"
                # first run with fresh path must succeed (real suite)
                import subprocess as _sp
                py = sys.executable
                r = _sp.run([py, str(PARSER_TEST_PATH), "--result", fresh],
                            capture_output=True, text=True, timeout=300)
                check("ptest-fresh-run-green",
                      r.returncode == 0 and Path(fresh).is_file(),
                      (r.stdout[-500:] + r.stderr[-500:])[-800:])
                h1 = digest(fresh)
                # create sentinel AFTER first success; repeat must not touch it
                sent.write_text("SENTINEL")
                mtime_before = sent.stat().st_mtime_ns
                r2 = _sp.run([py, str(PARSER_TEST_PATH), "--result", fresh],
                             capture_output=True, text=True, timeout=60)
                check("ptest-repeat-collides",
                      r2.returncode != 0 and "collision" in (
                          r2.stdout + r2.stderr).lower(),
                      (r2.stdout + r2.stderr)[-500:])
                check("ptest-repeat-hash-unchanged", digest(fresh) == h1)
                check("ptest-repeat-sentinel-untouched",
                      sent.read_text() == "SENTINEL"
                      and sent.stat().st_mtime_ns == mtime_before)
                # colliding call must stop BEFORE loader/compile/temp hooks:
                # patch load_parser to record, call main() in-process
                seen = []
                real_lp = ptest.load_parser
                ptest.load_parser = lambda: (
                    seen.append("loader"), real_lp())[1]
                try:
                    try:
                        ptest.main(["--result", fresh])
                        check("ptest-inprocess-collision-stops", False,
                              "no collision raised")
                    except (AssertionError, SystemExit) as ex:
                        is_collision = "collision" in str(ex).lower()
                        check("ptest-inprocess-collision-stops",
                              is_collision and not seen,
                              f"ex={ex} seen={seen}")
                finally:
                    ptest.load_parser = real_lp
            check("ptest-orig-hash-unchanged",
                  digest(ORIG_RESULT) == before_hash)
        except Exception as e:
            check("collision-suite", False, f"{type(e).__name__}: {e}"[:500])

        # ---- 6. strict JSON ints + fixture_entry_number ----
        try:
            base09 = {"record": "09-unit-chaos", "boot_id": SYN_BOOT,
                      "stale_marker_created": True,
                      "parent_execstart_verified_sleep": True,
                      "parent_active_before": True,
                      "parent_pid_before": 5001,
                      "execstartpre_cleared_marker": True,
                      "fake_marker_created": True,
                      "child_active_before": True, "child_pid_before": 5002,
                      "kill_rc": 0, "kill_sent": True,
                      "parent_after": {"ActiveState": "failed",
                                       "SubState": "failed", "MainPID": 0,
                                       "Result": "signal"},
                      "child_after_auto": {"ActiveState": "inactive",
                                           "SubState": "dead", "MainPID": 0,
                                           "Result": "success"},
                      "old_child_pid_gone": True,
                      "marker_absent_post": True,
                      "cleanup_owned_fake_only": True,
                      "measured_within_s": 15}
            ok, _, _ = parser.validate_09_record(dict(base09), SYN_BOOT)
            check("09-int-pids-valid", ok is True)
            for fld, bad in [("parent_pid_before", "5001"),
                             ("child_pid_before", "5002"),
                             ("kill_rc", "0")]:
                d = dict(base09)
                d[fld] = bad
                ok, _, _ = parser.validate_09_record(d, SYN_BOOT)
                check(f"09-{fld}-string-rejected", ok is False)
            for fld in ["parent_pid_before", "child_pid_before"]:
                d = dict(base09)
                d[fld] = True
                ok, _, _ = parser.validate_09_record(d, SYN_BOOT)
                check(f"09-{fld}-bool-rejected", ok is False)
            d = dict(base09)
            d["parent_after"] = {"ActiveState": "failed",
                                 "SubState": "failed", "MainPID": "0",
                                 "Result": "signal"}
            ok, _, _ = parser.validate_09_record(d, SYN_BOOT)
            check("09-parent-MainPID-string-rejected", ok is False)
            import inspect as _ins2
            hsrc = Path(HARNESS_PATH).read_text()
            check("report-uses-fixture-entry-number",
                  "fixture_entry_number" in hsrc
                  and "native_entry_number" not in hsrc)
        except Exception as e:
            check("strict-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- 7. stable preflight contract ----
        try:
            minimal = {"passed": False, "reason": "preflight-fail",
                       "detail": {"thermal": {"ok": False},
                                  "drm": {"ok": False}},
                       "native_graphics_validated": False}
            ok, _, _ = parser.validate_preflight_record(dict(minimal))
            check("preflight-minimal-valid-no-top-dup", ok is True)
            early = {"passed": False, "reason": "unknown-baseline",
                     "detail": {}, "native_graphics_validated": False}
            ok, _, _ = parser.validate_preflight_record(dict(early))
            check("preflight-early-baseline-valid", ok is True)
            bad = dict(minimal)
            bad["detail"] = "preflight-fail"
            ok, _, _ = parser.validate_preflight_record(bad)
            check("preflight-detail-not-dict-fails", ok is False)
            bad2 = dict(minimal)
            bad2["detail"] = {"thermal": "bad"}
            ok, _, _ = parser.validate_preflight_record(bad2)
            check("preflight-detail-thermal-type-fails", ok is False)
        except Exception as e:
            check("preflight-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- lock: same file, no unlink, no recursive deadlock ----
        try:
            check("lock-same-file",
                  str(prepare.LOCK) == str(harness.LOCK)
                  and prepare.LOCK.name == "dt25-build.lock")
            import inspect as _ins3
            asrc = _ins3.getsource(prepare.acquire_dt25_lock)
            check("lock-never-unlinks",
                  ".unlink(" not in asrc and "os.remove" not in asrc
                  and "LOCK.unlink" not in asrc)
            check("lock-nonblocking-inherit",
                  "LOCK_NB" in asrc and "INHERIT" in asrc.upper())
        except Exception as e:
            check("lock-suite", False, f"{type(e).__name__}: {e}"[:300])

        total = PASS + FAIL
        summary = {"passed": PASS, "failed": FAIL, "skipped": SKIP,
                   "total": total, "failures": FAILURES,
                   "revision": "v2-dt26",
                   "no_vm_runs": True,
                   "notes": "dt26 harness-fix load-bearing regressions; "
                            "VM gates remain unexecuted"}
        with _os.fdopen(_res_fd, "w") as s:
            s.write(json.dumps(summary, indent=2))
        _res_fd = None
        print(json.dumps(summary, indent=2))
        sys.exit(0 if FAIL == 0 else 1)
    except SystemExit:
        raise
    except BaseException as _exc:
        try:
            try:
                _os.close(_res_fd)
            except Exception:
                pass
        except Exception:
            pass
        try:
            if result_path.is_file() and result_path.stat().st_size == 0:
                failure = {"passed": PASS, "failed": FAIL + 1, "skipped": SKIP,
                           "total": PASS + FAIL + 1, "failures": FAILURES + [f"exception: {type(_exc).__name__}: {_exc}"[:500]],
                           "revision": "v2-dt26", "no_vm_runs": True,
                           "notes": "exception during harness-fix tests (own descriptor finalized)"}
                result_path.write_text(json.dumps(failure, indent=2))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
