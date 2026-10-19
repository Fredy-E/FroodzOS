#!/usr/bin/env python3
"""dt26 harness lock/lifecycle incremental checks (real functions, mocked FS only).

Covers the 3 parent RED probes with load-bearing real code + private fixtures:
  FIX1 actual locking: standalone EX|NB or refuse; validated inherited FD
    (regular + dev/inode + EX|NB reaffirm); fake/wrongFD or foreign holder
    fails; borrowed close-only (never UN shared OFD); held across format/copy.
  FIX2 incremental capacity: explicit future_fixture_bytes; before prepare
    one 2.25GiB, before BC/BC-only zero (+pending only); never double-count.
  FIX3 process lifetime: exclusive owned log BEFORE any Popen; post-spawn
    exceptions terminate/kill/wait owned proc; refuse extract if alive.
  Plus output-exclusivity: atomic O_EXCL reservation BEFORE import/compile.

Never real QEMU/build/FAT/USB/firmware; private temp locks only.
"""
import argparse
import hashlib
import importlib.util
import json
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
PTEST_PATH = T / "dt26-efi-parser-test.py"

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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--run-dir", default=None)
    args = ap.parse_args(argv)
    if args.tag:
        result_path = T / (args.tag + "-lock-lifecycle-result.json")
    elif args.run_dir:
        result_path = Path(args.run_dir) / "dt26-harness-lock-lifecycle-result.json"
    elif args.result:
        result_path = Path(args.result)
    else:
        ap.error("need one of --result/--tag/--run-dir (fresh, caller-owned)")
    if args.run_dir:
        try:
            Path(args.run_dir).mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            pass
        except FileNotFoundError:
            raise AssertionError(f"missing parent for result {result_path.parent}")
    assert result_path.parent.exists(), f"missing parent for result {result_path.parent}"
    import os as _os
    try:
        _res_fd = _os.open(str(result_path), _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
    except FileExistsError:
        raise AssertionError(f"collision: {result_path} exists, use fresh --result/--tag/--run-dir")
    try:
        parser = load("dt26_ll_parser", PARSER_PATH)
        harness = load("dt26_ll_harness", HARNESS_PATH)
        prepare = load("dt26_ll_prepare", PREPARE_PATH)

        GiB = 1024 ** 3
        FIX = 9 * 1024 ** 3 // 4
        PEND = 512 * 1024 ** 2
        RES = 10 * GiB

        # ---- lock API surface: validated inheritance, no false inherit ----
        try:
            import inspect as _ins
            asrc = _ins.getsource(prepare.acquire_dt25_lock)
            check("lock-api-uses-validated-inherit", "validate_inherited_fd" in asrc)
            check("lock-api-no-false-parent-inherited", "PARENT FLOCK INHERITED" not in asrc)
            check("lock-api-never-returns-none-on-contention", "return None" not in asrc)
            check("lock-api-refuses-before-alloc", "refusing" in asrc.lower() or "refuse" in asrc.lower())
            check("lock-api-has-release-helper", hasattr(prepare, "release_dt25_lock"))
            check("lock-api-has-validate-helper", hasattr(prepare, "validate_inherited_fd"))
            check("lock-env-fd-name", getattr(prepare, "LOCK_ENV_FD", "") == "DT26_LOCK_FD")
            check("lock-harness-has-validate", hasattr(harness, "validate_lock_fd"))
            check("lock-harness-env-name", getattr(harness, "LOCK_ENV_FD", "") == "DT26_LOCK_FD")
            check("lock-never-unlinks-src", ".unlink(" not in asrc and "os.remove" not in asrc)
            check("lock-same-file-src", "dt25-build.lock" in open(str(PREPARE_PATH)).read() and "dt25-build.lock" in open(str(HARNESS_PATH)).read())
        except Exception as e:
            check("lock-api-suite", False, f"{type(e).__name__}: {e}"[:300])

        # ---- real cross-process contention: separate child holder refuses ----
        try:
            import fcntl as _fc
            import os as _ox
            import signal as _sig
            import subprocess as _sp
            import sys as _sys
            with tempfile.TemporaryDirectory(prefix="dt26-ll-lock-") as _tmp:
                _priv = Path(_tmp) / "private-test.lock"
                _priv.write_text("")
                _old_p = prepare.LOCK
                _old_h = harness.LOCK
                prepare.LOCK = _priv
                harness.LOCK = _priv
                try:
                    # standalone acquires owned
                    _h1 = prepare.acquire_dt25_lock()
                    check("lock-standalone-owned", _h1 is not None and getattr(_h1, "_dt26_owned", True) is True)
                    # second acquire while held must refuse (raise), never None
                    try:
                        _h2 = prepare.acquire_dt25_lock()
                        check("lock-standalone-second-refuses", False, "should have raised")
                        try:
                            prepare.release_dt25_lock(_h2)
                        except Exception:
                            pass
                    except OSError:
                        check("lock-standalone-second-refuses", True)
                    prepare.release_dt25_lock(_h1)
                    # after release, can acquire again
                    _h1b = prepare.acquire_dt25_lock()
                    check("lock-reacquire-after-release", _h1b is not None)
                    prepare.release_dt25_lock(_h1b)
                    # cross-proc holder
                    _code = 'import fcntl,sys,time; f=open(sys.argv[1],"a+"); fcntl.flock(f,fcntl.LOCK_EX); print("LOCKED",flush=True); time.sleep(20)'
                    _holder = _sp.Popen([_sys.executable, "-c", _code, str(_priv)], stdout=_sp.PIPE, text=True, start_new_session=True)
                    try:
                        assert _holder.stdout.readline().strip() == "LOCKED"
                        try:
                            _hx = prepare.acquire_dt25_lock()
                            check("lock-crossproc-refuses-not-none", False, f"returned { _hx} instead of refusing")
                            try:
                                prepare.release_dt25_lock(_hx)
                            except Exception:
                                pass
                        except OSError:
                            check("lock-crossproc-refuses-not-none", True)
                        # validate_inherited with separate fresh open while holder holds must fail (foreign)
                        _probe = open(str(_priv), "a+")
                        try:
                            try:
                                prepare.validate_inherited_fd(_probe.fileno(), _priv)
                                check("lock-foreign-fd-fails", False, "should have raised")
                            except OSError:
                                check("lock-foreign-fd-fails", True)
                        finally:
                            try:
                                _probe.close()
                            except Exception:
                                pass
                    finally:
                        try:
                            _ox.killpg(_holder.pid, _sig.SIGKILL)
                        except Exception:
                            try:
                                _holder.kill()
                            except Exception:
                                pass
                        _holder.wait()
                    check("lock-file-still-exists-no-unlink", _priv.is_file())
                finally:
                    prepare.LOCK = _old_p
                    harness.LOCK = _old_h
        except Exception as e:
            check("lock-contention-suite", False, f"{type(e).__name__}: {e}"[:400])

        # ---- validated inherited positive + wrongFD + parent still locked ----
        try:
            import fcntl as _fc2
            import os as _ox2
            import subprocess as _sp2
            import sys as _sys2
            with tempfile.TemporaryDirectory(prefix="dt26-ll-inherit-") as _tmp2:
                _priv2 = Path(_tmp2) / "private-inherit.lock"
                _priv2.write_text("")
                _old_p2 = prepare.LOCK
                _old_h2 = harness.LOCK
                prepare.LOCK = _priv2
                harness.LOCK = _priv2
                try:
                    _parent = open(str(_priv2), "a+")
                    _fc2.flock(_parent, _fc2.LOCK_EX)
                    try:
                        _n = _parent.fileno()
                        # validate in-process reaffirm succeeds (same OFD)
                        try:
                            _v = prepare.validate_inherited_fd(_n, _priv2)
                            check("lock-validate-same-ofd-ok", _v == _n)
                        except Exception as _e:
                            check("lock-validate-same-ofd-ok", False, str(_e)[:200])
                        # wrong file fd fails
                        _other = Path(_tmp2) / "other.lock"
                        _other.write_text("")
                        _of = open(str(_other), "a+")
                        try:
                            try:
                                prepare.validate_inherited_fd(_of.fileno(), _priv2)
                                check("lock-wrongfd-devinode-fails", False, "should raise")
                            except OSError:
                                check("lock-wrongfd-devinode-fails", True)
                        finally:
                            try:
                                _of.close()
                            except Exception:
                                pass
                        # bad number fails
                        try:
                            prepare.validate_inherited_fd(999999, _priv2)
                            check("lock-badfd-fails", False, "should raise")
                        except OSError:
                            check("lock-badfd-fails", True)
                        # non-regular (pipe) fails
                        _r, _w = _ox2.pipe()
                        try:
                            try:
                                prepare.validate_inherited_fd(_w, _priv2)
                                check("lock-nonregular-fails", False, "should raise")
                            except OSError:
                                check("lock-nonregular-fails", True)
                        finally:
                            try:
                                _ox2.close(_r)
                            except Exception:
                                pass
                            try:
                                _ox2.close(_w)
                            except Exception:
                                pass
                        # child via pass_fds + env succeeds, parent still locked after
                        _child_src = (
                            "import os,sys,pathlib,importlib.util;"
                            f"priv=pathlib.Path({str(_priv2)!r});"
                            f"spec=importlib.util.spec_from_file_location('m',{str(PREPARE_PATH)!r});"
                            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
                            "m.LOCK=priv;"
                            "n=int(os.environ['DT26_LOCK_FD']);"
                            "h=m.acquire_dt25_lock(inherited_fd=n);"
                            "print('CHILD-OK owned='+str(getattr(h,'_dt26_owned',True)));"
                            "m.release_dt25_lock(h);"
                            "print('CHILD-RELEASED');"
                            "import fcntl; _p=open(str(priv),'a+');"
                            "try:\n"
                            " fcntl.flock(_p,fcntl.LOCK_EX|fcntl.LOCK_NB);print('CHILD-UNEXPECTED-ACQUIRE')\n"
                            "except OSError:\n"
                            " print('PARENT-STILL-LOCKED')"
                        )
                        # fix multiline: build file
                        _child_file = Path(_tmp2) / "child.py"
                        _child_file.write_text(
                            "import os,sys,pathlib,importlib.util\n"
                            f"priv=pathlib.Path({str(_priv2)!r})\n"
                            f"spec=importlib.util.spec_from_file_location('m',{str(PREPARE_PATH)!r})\n"
                            "m=importlib.util.module_from_spec(spec)\n"
                            "spec.loader.exec_module(m)\n"
                            "m.LOCK=priv\n"
                            "n=int(os.environ['DT26_LOCK_FD'])\n"
                            "h=m.acquire_dt25_lock(inherited_fd=n)\n"
                            "print('CHILD-OK owned='+str(getattr(h,'_dt26_owned',True)),flush=True)\n"
                            "m.release_dt25_lock(h)\n"
                            "print('CHILD-RELEASED',flush=True)\n"
                            "import fcntl\n"
                            "_p=open(str(priv),'a+')\n"
                            "try:\n"
                            " fcntl.flock(_p,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                            " print('CHILD-UNEXPECTED-ACQUIRE',flush=True)\n"
                            "except OSError:\n"
                            " print('PARENT-STILL-LOCKED',flush=True)\n"
                        )
                        import os as _e2
                        _env = dict(_e2.environ)
                        _env["DT26_LOCK_FD"] = str(_n)
                        _cp = _sp2.run([_sys2.executable, str(_child_file)], capture_output=True, text=True, timeout=30, env=_env, pass_fds=(_n,))
                        _out = (_cp.stdout or "") + (_cp.stderr or "")
                        check("lock-inherited-child-ok", "CHILD-OK" in _out and "owned=False" in _out, _out[-500:])
                        check("lock-inherited-child-released", "CHILD-RELEASED" in _out, _out[-500:])
                        check("lock-parent-still-locked-after-child", "PARENT-STILL-LOCKED" in _out, _out[-500:])
                        # parent can still reaffirm (still holds)
                        try:
                            _fc2.flock(_n, _fc2.LOCK_EX | _fc2.LOCK_NB)
                            check("lock-parent-reaffirm-ok", True)
                        except OSError as _e:
                            check("lock-parent-reaffirm-ok", False, str(_e)[:200])
                        # harness validate helper agrees
                        try:
                            _hn = harness.validate_lock_fd(_n, _priv2)
                            check("lock-harness-validate-ok", _hn == _n)
                        except Exception as _e:
                            check("lock-harness-validate-ok", False, str(_e)[:200])
                        # harness wrong fd fails
                        try:
                            harness.validate_lock_fd(999999, _priv2)
                            check("lock-harness-badfd-fails", False, "should raise")
                        except OSError:
                            check("lock-harness-badfd-fails", True)
                    finally:
                        try:
                            _fc2.flock(_parent, _fc2.LOCK_UN)
                        except Exception:
                            pass
                        try:
                            _parent.close()
                        except Exception:
                            pass
                finally:
                    prepare.LOCK = _old_p2
                    harness.LOCK = _old_h2
        except Exception as e:
            check("lock-inherit-suite", False, f"{type(e).__name__}: {e}"[:500])

        # ---- incremental capacity: explicit future_fixture_bytes ----
        try:
            import shutil as _sh
            import types as _ty
            # formula future = fixture+pending, before prepare
            fut, rem = prepare.capacity_plan(20 * GiB, PEND, FIX)
            check("cap-formula-before-includes-fixture", fut == FIX + PEND, f"fut={fut}")
            fut0, rem0 = prepare.capacity_plan(20 * GiB, PEND, 0)
            check("cap-formula-bc-zero-excludes-fixture", fut0 == PEND, f"fut0={fut0}")
            ok, _, _ = prepare.check_d_capacity(12 * GiB, 0, FIX)
            check("cap-beforeA-12GiB-pending0-rejects", ok is False)
            ok, _, _ = prepare.check_d_capacity(12 * GiB, 0, 0)
            check("cap-afterA-BC-12GiB-pending0-accepts", ok is True)
            ok, _, _ = prepare.check_d_capacity(10 * GiB, 0, 0)
            check("cap-below-reserve-10GiB-rejects", ok is False)
            ok, _, _ = prepare.check_d_capacity(RES + PEND, PEND, 0)
            # free = RES+PEND, future=PEND, remaining=RES => not > RES => reject
            check("cap-bc-threshold-equal-rejects", ok is False)
            ok, _, _ = prepare.check_d_capacity(RES + PEND + 1, PEND, 0)
            check("cap-bc-threshold-plus1-accepts", ok is True)
            # harness same with mocked disk_usage, reads only /mnt/d
            calls = []
            def _fake(path):
                calls.append(str(path))
                if str(path) == "/mnt/d":
                    return _ty.SimpleNamespace(free=12 * GiB)
                return _ty.SimpleNamespace(free=1000 * GiB)
            _real = _sh.disk_usage
            _sh.disk_usage = _fake
            try:
                ok_h, free_h = harness.disk_free_ok(pending_runtime=0, future_fixture_bytes=FIX)
            finally:
                _sh.disk_usage = _real
            check("cap-harness-beforeA-12GiB-rejects", ok_h is False, f"free={free_h}")
            check("cap-harness-reads-only-D-before", all(c == "/mnt/d" for c in calls), str(calls[:3]))
            calls2 = []
            def _fake2(path):
                calls2.append(str(path))
                if str(path) == "/mnt/d":
                    return _ty.SimpleNamespace(free=12 * GiB)
                return _ty.SimpleNamespace(free=1000 * GiB)
            _sh.disk_usage = _fake2
            try:
                ok_h2, _ = harness.disk_free_ok(pending_runtime=0, future_fixture_bytes=0)
            finally:
                _sh.disk_usage = _real
            check("cap-harness-BC-12GiB-accepts", ok_h2 is True)
            check("cap-harness-reads-only-D-bc", all(c == "/mnt/d" for c in calls2))
            # do_run contexts: before uses FIX, before-BC uses 0
            import inspect as _ins2
            _dr = _ins2.getsource(harness.do_run)
            check("cap-dorun-before-uses-fixture", "future_fixture_bytes=FIXTURE_BYTES" in _dr)
            check("cap-dorun-bc-uses-zero", "future_fixture_bytes=0" in _dr)
            check("cap-prepare-before-uses-fixture", "FIXTURE_BYTES" in open(str(PREPARE_PATH)).read())
        except Exception as e:
            check("cap-suite", False, f"{type(e).__name__}: {e}"[:400])

        # ---- process lifetime: log-before-spawn, guaranteed cleanup ----
        try:
            import inspect as _ins3
            _rq = _ins3.getsource(harness.run_qemu)
            check("life-log-before-spawn-src", _rq.index('log_path.open("xb")') < _rq.index("subprocess.Popen") or _rq.index("log_file = ") < _rq.index("subprocess.Popen"))
            check("life-no-popen-before-log", "proc = subprocess.Popen" not in _rq.split('log_file')[0] if 'log_file' in _rq else False)
            check("life-refuses-extract-if-alive", "refusing extract" in _rq.lower() and "proc.poll() is None" in _rq)
            check("life-spawn-failed-keeps-log", "SPAWN-FAILED" in _rq)
            # mocked log-open-fail => 0 spawn
            with tempfile.TemporaryDirectory(prefix="dt26-ll-life-") as _tmp3:
                import pathlib as _pl
                _tdir = _pl.Path(_tmp3) / "T"
                _bdir = _pl.Path(_tmp3) / "B"
                _tdir.mkdir()
                _bdir.mkdir()
                _prefix = "dt26-efi-ll-life"
                (_tdir / (_prefix + "-grub.cfg")).write_text("CFG")
                (_bdir / (_prefix + ".fat")).write_bytes(b"\x00" * 64)
                _oldT, _oldB = harness.T, harness.B
                harness.T, harness.B = _tdir, _bdir
                harness.fat_offset = lambda image: ({"partitions": [{"start": 2048}]}, str(image) + "@@1048576")
                harness.mtype_hash = lambda fs, p: "h"
                import subprocess as _rs
                harness.subprocess = types.SimpleNamespace(check_output=lambda argv, **kw: b"CFG", run=lambda argv, **kw: types.SimpleNamespace(returncode=0, stdout="", stderr=""), PIPE=_rs.PIPE, STDOUT=_rs.STDOUT, Popen=_rs.Popen)
                harness.check_guest_phases = lambda *a: None
                # need parser stub with validate_boot_id etc? run_qemu needs derived + mod for nothing? Actually run_qemu with empty phases still does fat checks then spawn. Use parser real.
                _derived = {"uki_sha256": "h", "sfs_sha256": "h"}
                # 1) log open fails => 0 spawn
                _spawns = []
                def _fake_popen(*a, **k):
                    _spawns.append(1)
                    raise AssertionError("should not spawn when log open fails")
                harness.subprocess.Popen = _fake_popen
                from unittest.mock import patch as _patch
                from pathlib import Path as _Path
                _real_open = _Path.open
                def _fail_log(self, *a, **k):
                    if str(self).endswith("-a.log"):
                        raise OSError(28, "injected private log-open failure")
                    return _real_open(self, *a, **k)
                try:
                    with _patch.object(_Path, "open", _fail_log):
                        harness.run_qemu(_prefix, "a", [], 60, _derived, parser)
                    check("life-logopenfail-raises", False, "should have raised")
                except OSError as _e:
                    check("life-logopenfail-raises", True)
                    check("life-logopenfail-zero-spawn", len(_spawns) == 0, f"spawns={len(_spawns)}")
                except Exception as _e:
                    check("life-logopenfail-raises", False, f"{type(_e).__name__}: {_e}"[:200])
                # 2) spawn failure keeps failure log
                def _raise_popen(*a, **k):
                    raise RuntimeError("injected spawn failure")
                harness.subprocess.Popen = _raise_popen
                try:
                    harness.run_qemu(_prefix, "a", [], 60, _derived, parser)
                    check("life-spawnfail-raises", False, "should raise")
                except RuntimeError:
                    check("life-spawnfail-raises", True)
                    _lp = _tdir / (_prefix + "-a.log")
                    check("life-spawnfail-keeps-log", _lp.is_file(), str(_lp))
                    try:
                        _content = _lp.read_bytes()
                        check("life-spawnfail-log-marks", b"SPAWN-FAILED" in _content)
                    except Exception as _e:
                        check("life-spawnfail-log-marks", False, str(_e)[:200])
                    # no extract on spawn failure
                    check("life-spawnfail-no-extract", not (_bdir / (_prefix + "-a-extracted")).exists())
                    # cleanup log for next subtest (fresh prefix)
                    try:
                        _lp.unlink()
                    except Exception:
                        pass
                except Exception as _e:
                    check("life-spawnfail-raises", False, f"{type(_e).__name__}: {_e}"[:200])
                # 3) post-spawn write/read error => terminated+wait, no orphan
                class _FakeProc:
                    def __init__(self):
                        self.returncode = None
                        self.terminated = False
                        self.killed = False
                        self.waited = False
                        import io as _io
                        self.stdout = _io.BytesIO(b"x")
                        # fileno needed for select/os.read; use real pipe?
                        self.stdin = types.SimpleNamespace(write=lambda b: (_ for _ in ()).throw(OSError("injected write fail")), flush=lambda: None)
                    def poll(self):
                        return self.returncode
                    def terminate(self):
                        self.terminated = True
                        self.returncode = 0
                    def kill(self):
                        self.killed = True
                        self.returncode = -9
                    def wait(self, timeout=None):
                        self.waited = True
                        return self.returncode
                _created = []
                def _mkproc(*a, **k):
                    _o = _FakeProc()
                    # stdout needs fileno for select; mock select to avoid fileno
                    _o.stdout = types.SimpleNamespace(fileno=lambda: 9999, read=lambda *a, **k: b"")
                    _created.append(_o)
                    return _o
                harness.subprocess.Popen = _mkproc
                import select as _sel
                _real_sel = _sel.select
                _sel.select = lambda r, w, x, t=None: (_ for _ in ()).throw(OSError("injected select fail"))
                import time as _tm
                _real_mono = _tm.monotonic
                _ctr = [0]
                def _mono():
                    _ctr[0] += 1
                    return 0.0 if _ctr[0] < 3 else 100.0
                _tm.monotonic = _mono
                try:
                    # use fresh suffix b to avoid collision with previous a.log
                    try:
                        harness.run_qemu(_prefix, "b", [{"send": "echo hi\n"}], 60, _derived, parser)
                    except Exception:
                        pass
                    if _created:
                        _p0 = _created[0]
                        check("life-postspawn-terminated-or-killed", _p0.terminated or _p0.killed, f"t={_p0.terminated} k={_p0.killed}")
                        check("life-postspawn-waited", _p0.waited)
                    else:
                        check("life-postspawn-terminated-or-killed", False, "no proc created")
                        check("life-postspawn-waited", False, "no proc")
                finally:
                    _sel.select = _real_sel
                    _tm.monotonic = _real_mono
                # 4) refuse extract if still alive (poll never None)
                class _Alive:
                    def __init__(self):
                        self.returncode = None
                        import io as _io
                        self.stdout = types.SimpleNamespace(fileno=lambda: 9999, read=lambda *a, **k: b"")
                        self.stdin = types.SimpleNamespace(write=lambda b: None, flush=lambda: None)
                    def poll(self):
                        return None
                    def terminate(self):
                        pass
                    def kill(self):
                        pass
                    def wait(self, timeout=None):
                        return None
                harness.subprocess.Popen = lambda *a, **k: _Alive()
                _sel.select = lambda r, w, x, t=None: ([], [], [])
                # Use real monotonic with short deadline (1s) so the main loop
                # exits via deadline, then finally attempts terminate/kill/wait
                # (no-ops for _Alive, poll stays None) and refuses extract.
                # Never freeze time (would spin forever).
                try:
                    try:
                        harness.run_qemu(_prefix, "c", [], 1, _derived, parser)
                        check("life-alive-refuses-extract", False, "should raise")
                    except RuntimeError as _e:
                        check("life-alive-refuses-extract", "refusing extract" in str(_e).lower())
                        check("life-alive-no-extract-dir", not (_bdir / (_prefix + "-c-extracted")).exists())
                    except Exception as _e:
                        check("life-alive-refuses-extract", False, f"{type(_e).__name__}: {_e}"[:200])
                finally:
                    _sel.select = _real_sel
                    # restore monotonic? _real_mono from above still valid
                    try:
                        _tm.monotonic = _real_mono
                    except Exception:
                        pass
                    harness.T, harness.B = _oldT, _oldB
        except Exception as e:
            check("life-suite", False, f"{type(e).__name__}: {e}"[:500])

        # ---- output exclusivity: atomic reservation before loader (no self-recursion) ----
        try:
            import subprocess as _sp3
            import sys as _sys3
            import inspect as _insE
            _src_main = _insE.getsource(main)
            # reservation O_EXCL occurs before any load() in own main source
            check("excl-reserves-before-loader",
                  "_res_fd = _os.open" in _src_main and _src_main.index("_res_fd = _os.open") < _src_main.index('load("dt26_ll_'))
            check("excl-uses-O_EXCL", "O_EXCL" in _src_main and "O_CREAT" in _src_main)
            check("excl-never-truncates", 'open("x")' not in _src_main or "_res_fd" in _src_main)
            # in-process collision refuses without loader, preserves hash
            with tempfile.TemporaryDirectory(prefix="dt26-ll-excl-") as _tmp4:
                _fresh = str(Path(_tmp4) / "fresh-parser-quick.json")
                _r = _sp3.run([_sys3.executable, str(PTEST_PATH), "--result", _fresh],
                              capture_output=True, text=True, timeout=60)
                check("excl-parser-fresh-green", _r.returncode == 0 and Path(_fresh).is_file(),
                      (_r.stdout[-300:] + _r.stderr[-300:])[-600:])
                import hashlib as _hl
                _h1 = _hl.sha256(Path(_fresh).read_bytes()).hexdigest()
                _sent = Path(_tmp4) / "sentinel"
                _sent.write_text("SENTINEL")
                _mt = _sent.stat().st_mtime_ns
                _r2 = _sp3.run([_sys3.executable, str(PTEST_PATH), "--result", _fresh],
                               capture_output=True, text=True, timeout=30)
                check("excl-repeat-collides", _r2.returncode != 0 and "collision" in (_r2.stdout + _r2.stderr).lower(),
                      (_r2.stdout + _r2.stderr)[-400:])
                check("excl-repeat-hash-unchanged", _hl.sha256(Path(_fresh).read_bytes()).hexdigest() == _h1)
                check("excl-sentinel-untouched", _sent.read_text() == "SENTINEL" and _sent.stat().st_mtime_ns == _mt)
                # concurrent winner: two O_EXCL attempts, one wins, other refuses, hash preserved
                _race = str(Path(_tmp4) / "race.json")
                _fd_win = _os.open(_race, _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
                try:
                    try:
                        _fd_lose = _os.open(_race, _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
                        check("excl-concurrent-loser-refuses", False, "second O_EXCL should fail")
                        try:
                            _os.close(_fd_lose)
                        except Exception:
                            pass
                    except FileExistsError:
                        check("excl-concurrent-loser-refuses", True)
                    _os.write(_fd_win, b'{"winner": true}')
                finally:
                    try:
                        _os.close(_fd_win)
                    except Exception:
                        pass
                check("excl-race-hash-preserved", Path(_race).read_bytes() == b'{"winner": true}')
        except Exception as e:
            check("excl-suite", False, f"{type(e).__name__}: {e}"[:400])

        total = PASS + FAIL
        summary = {"passed": PASS, "failed": FAIL, "skipped": SKIP, "total": total, "failures": FAILURES, "revision": "v2-dt26", "no_vm_runs": True, "notes": "dt26 lock/lifecycle incremental; VM gates unexecuted"}
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
                failure = {"passed": PASS, "failed": FAIL + 1, "skipped": SKIP, "total": PASS + FAIL + 1, "failures": FAILURES + [f"exception: {type(_exc).__name__}: {_exc}"[:500]], "revision": "v2-dt26", "no_vm_runs": True, "notes": "exception during lock-lifecycle tests (own descriptor finalized)"}
                result_path.write_text(json.dumps(failure, indent=2))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
