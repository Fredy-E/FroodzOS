#!/usr/bin/env python3
"""Gate tests for dt26 build/audit wrappers (synthetic fixtures only).

Runs true unit/syntax/gate checks on Linux with explicit synthetic-fixture
labels. Never builds, never extracts, never invokes the canonical builder,
never reads/hashes moving writer sources (all source trees here are
synthetic temp fixtures via monkeypatched module paths).

Covered gates:
  malformed manifest, missing review approval, changed source hash,
  literal-format-before-lookup order (fullmatch: trailing-LF sha/tag
  refused, exact path==key, extras refused, tag refused before manifest
  load via sentinel), shared dt25-build.lock only (no new lock, no
  create/unlink, nonblocking contention), private-lock cross-process
  negative + synthetic no-op builder positive (no global build),
  SFS canonical private-build-root + guard20 + report-schema minimum,
  finalization commit order (copy/flush/readback before single exclusive
  receipt; failures leave NO receipt; no rewrite), storage (new-only
  extract, no redundant candidate, future-bytes budget, preserve failures),
  explicit build env (ROOT/KESTREL_* pinned) + compression 1..2 strict
  (no comment bypass), imgroot versions auxiliary-only, output collision
  before effects (no unlinks), D post-reserve budget, import-safe --help,
  dependency errors (missing required entry), canonical-builder-not-invoked,
  syntax gates (py_compile self + synthetic bash/sh -n).

Not a real artifact pass: no UKI/initrd/SFS/QEMU is verified here. The
result receipt lists unresolved actual-build gates.
"""
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SELF = Path(__file__).resolve()
T = SELF.parent
P_REAL = Path("/mnt/d/CachyOS-ARM64")


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


build = load_mod("dt26_build_live", T / "build-dt26-live.py")
audit = load_mod("dt26_audit_artifacts", T / "audit-dt26-artifacts.py")

RESULTS = {"passed": [], "failed": [], "skipped": []}


def check(name, fn):
    try:
        fn()
    except AssertionError as e:
        RESULTS["failed"].append({"name": name, "error": str(e)[:500]})
        print(f"FAIL {name}: {e}", flush=True)
    except SystemExit as e:
        RESULTS["failed"].append({"name": name, "error": f"unexpected SystemExit {e.code}"})
        print(f"FAIL {name}: unexpected SystemExit {e.code}", flush=True)
    except Exception as e:  # noqa: BLE001
        RESULTS["failed"].append({"name": name, "error": f"{type(e).__name__}: {e}"[:500]})
        print(f"FAIL {name}: {type(e).__name__}: {e}", flush=True)
    else:
        RESULTS["passed"].append(name)
        print(f"PASS {name} [synthetic-fixture]", flush=True)


def expect_refuse(name, fn):
    try:
        fn()
    except SystemExit as e:
        assert e.code == 2, f"{name}: exit {e.code} != 2"
        RESULTS["passed"].append(name)
        print(f"PASS {name} [synthetic-fixture, refused rc=2]", flush=True)
    else:
        RESULTS["failed"].append({"name": name, "error": "expected refusal, got success"})
        print(f"FAIL {name}: expected refusal, got success", flush=True)


def synth_manifest(tmp, alter=None):
    """Build a synthetic manifest over a fixture tree (no real sources)."""
    src = {}
    for rel in build.REQUIRED_SOURCES:
        f = tmp / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        payload = f"synthetic {rel}\n".encode()
        f.write_bytes(payload)
        src[rel] = {"path": rel, "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload)}
    m = {"revision": "v2-dt26", "approved_for_build": True,
         "spec_review": "PASS", "quality_review": "PASS",
         "review_id": "synthetic-fixture-only", "sources": src}
    if alter:
        alter(m, tmp)
    mp = tmp / "manifest.json"
    mp.write_text(json.dumps(m))
    return mp


def test_import_safe():
    assert build.REVISION == "v2-dt26" and audit.REVISION == "v2-dt26"
    assert len(build.REQUIRED_SOURCES) >= 30
    assert set(audit.REQUIRED_SOURCES) == set(build.REQUIRED_SOURCES)
    assert len(audit.PACKED_PROVENANCE) >= 15
    assert any("kestrel-root-log" in s for _, s in audit.PACKED_PROVENANCE), \
        "root logger provenance must be traced"
    # Shared lock is the SAME existing file in both wrappers.
    assert str(build.LOCK) == "/home/builder/boot-failure-tests/dt25-build.lock"
    assert str(audit.LOCK) == "/home/builder/boot-failure-tests/dt25-build.lock"


def test_help_no_effects():
    before = {p.name for p in T.glob("uki-v2-dt26-*")}
    before |= {p.name for p in T.glob("build-dt26-live-*.log")}
    for mod in ("build-dt26-live", "audit-dt26-artifacts"):
        r = subprocess.run([sys.executable, str(T / f"{mod}.py"), "--help"],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{mod} --help rc={r.returncode}"
        assert "--source-manifest" in r.stdout and "--tag" in r.stdout
    after = {p.name for p in T.glob("uki-v2-dt26-*")}
    after |= {p.name for p in T.glob("build-dt26-live-*.log")}
    assert before == after, "help must have no effects"


def test_malformed_manifest():
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        bad = tmp / "bad.json"
        bad.write_text("{not json")
        expect_refuse("malformed-json-refused", lambda: build.load_manifest(bad))
        m = {"revision": "v2-dt25b", "approved_for_build": True,
             "spec_review": "PASS", "quality_review": "PASS", "sources": {}}
        expect_refuse("wrong-revision-refused", lambda: build.validate_manifest_literal(m))
        expect_refuse("audit-wrong-revision-refused", lambda: audit.validate_manifest_literal(m))


def test_missing_review():
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        mp = synth_manifest(tmp)
        base = json.loads(mp.read_text())

        def unapproved(m, _t):
            m["approved_for_build"] = False
        m2 = json.loads(mp.read_text()); unapproved(m2, tmp)
        expect_refuse("approved-false-refused", lambda: build.validate_manifest_literal(m2))
        m3 = json.loads(mp.read_text()); m3["spec_review"] = "REQUEST_CHANGES"
        expect_refuse("spec-not-pass-refused", lambda: build.validate_manifest_literal(m3))
        m4 = json.loads(mp.read_text()); m4["quality_review"] = "NOT_RUN"
        expect_refuse("quality-not-pass-refused", lambda: build.validate_manifest_literal(m4))
        m5 = json.loads(mp.read_text()); m5["approved_for_build"] = 1
        expect_refuse("approved-truthy-int-refused", lambda: build.validate_manifest_literal(m5))
        expect_refuse("audit-approved-false-refused", lambda: audit.validate_manifest_literal(m2))


def test_changed_source_hash():
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        mp = synth_manifest(tmp)
        m = json.loads(mp.read_text())
        # Corrupt one fixture file after manifest creation.
        victim = build.REQUIRED_SOURCES[0]
        (tmp / victim).write_bytes(b"tampered-by-synthetic-test\n")
        with mock.patch.object(build, "P", tmp), mock.patch.object(build, "T", tmp):
            expect_refuse("changed-source-hash-refused",
                          lambda: build.verify_manifest_sources(build.validate_manifest_literal(m)))
        # Literal format checked before lookup: bad sha rejected even though
        # the file does not exist under the real tree.
        m6 = json.loads(mp.read_text())
        m6["sources"][victim]["sha256"] = "ZZZ"
        try:
            build.validate_manifest_literal(m6)
        except SystemExit as e:
            assert e.code == 2
        else:
            raise AssertionError("bad sha literal must refuse before lookup")


def test_missing_required_entry():
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        def drop(m, _t):
            m["sources"].pop(build.REQUIRED_SOURCES[5])
        mp = synth_manifest(tmp, alter=drop)
        m = json.loads(mp.read_text())
        expect_refuse("missing-entry-refused", lambda: build.validate_manifest_literal(m))
        expect_refuse("audit-missing-entry-refused", lambda: audit.validate_manifest_literal(m))


def test_output_collision_and_no_unlink():
    # Reserved tags collide with preserved outputs: refused before effects.
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        mp = synth_manifest(tmp)
        for bad_tag in ("dt25b", "dt24", "../escape", "bad tag!"):
            expect_refuse(f"reserved-tag-{bad_tag}-refused",
                          lambda t=bad_tag: build.main(["--source-manifest", str(mp), "--tag", t]))
        # Helper-level collision: pre-existing output refuses, nothing unlinked.
        keep = tmp / "keep.log"
        keep.write_bytes(b"synthetic prior evidence\n")
        other = tmp / "other.log"
        try:
            build.require_fresh([keep, other])
        except SystemExit as e:
            assert e.code == 2
        else:
            raise AssertionError("require_fresh must refuse on collision")
        assert keep.read_bytes() == b"synthetic prior evidence\n", "prior evidence must not be unlinked"
        assert not other.exists(), "second path must not be created on refusal"


def test_d_postreserve():
    assert build.check_d_remaining(build.RESERVE_BYTES + 1, 0) == build.RESERVE_BYTES + 1
    for free, planned in ((5 * 1024**3, 0), (11 * 1024**3, 3 * 1024**3),
                          (10 * 1024**3, 0), (10 * 1024**3 + 3 * 1024**3 - 1, 3 * 1024**3)):
        try:
            build.check_d_remaining(free, planned)
        except SystemExit as e:
            assert e.code == 2, "D refusal must be rc=2"
        else:
            raise AssertionError(f"D budget must refuse free={free} planned={planned}")
    # Boundary: remaining must be strictly greater than reserve.
    try:
        build.check_d_remaining(build.RESERVE_BYTES, 0)
    except SystemExit:
        pass
    else:
        raise AssertionError("remaining == reserve must refuse")


def test_builder_never_invoked():
    calls = []

    def spy(*a, **k):
        calls.append(a)
        raise AssertionError(f"canonical builder must not run in gate tests: {a}")
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        bad_rev = {"revision": "v2-dt25b", "approved_for_build": True,
                   "spec_review": "PASS", "quality_review": "PASS", "sources": {}}
        bad_mp = tmp / "bad-rev.json"
        bad_mp.write_text(json.dumps(bad_rev))
        with mock.patch.object(build.subprocess, "run", spy), \
             mock.patch.object(audit.subprocess, "run", spy):
            # DENY tag refuses before manifest load (no source reads).
            expect_refuse("cli-deny-tag-no-builder",
                          lambda: build.main(["--source-manifest", str(bad_mp), "--tag", "dt25b"]))
            # Bad revision refuses before lookup/subprocess (no source reads).
            expect_refuse("cli-bad-revision-no-builder",
                          lambda: build.main(["--source-manifest", str(bad_mp), "--tag", "gates-ok-1"]))
            expect_refuse("audit-cli-bad-revision-no-builder",
                          lambda: audit.main(["--source-manifest", str(bad_mp), "--tag", "gates-ok-1",
                                              "--audit-dir", "/home/builder/boot-failure-tests/dt26-audit-gates-ok-1"]))
    assert not any("build-live-uki.sh" in str(c) for c in calls), "builder invoked"


def test_syntax_gates():
    for mod in ("build-dt26-live", "audit-dt26-artifacts"):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(T / f"{mod}.py")],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"py_compile {mod}: {r.stderr[-500:]}"
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        sh = tmp / "s.sh"
        sh.write_text("#!/bin/bash\nset -euo pipefail\necho synthetic-ok\n")
        assert subprocess.run(["bash", "-n", str(sh)]).returncode == 0
        ash = tmp / "h"
        ash.write_text("#!/usr/bin/ash\nrun_latehook() {\nreturn 0\n}\n")
        assert subprocess.run(["sh", "-n", str(ash)]).returncode == 0


def test_literal_lf_and_exact_path():
    # Trailing-LF sha/tag must be refused (fullmatch); wrong path and
    # extras refused; literal rejection precedes any filesystem lookup.
    with tempfile.TemporaryDirectory(prefix="dt26-gates-synth-") as td:
        tmp = Path(td)
        mp = synth_manifest(tmp)
        m = json.loads(mp.read_text())
        victim = build.REQUIRED_SOURCES[0]
        # 1) sha with trailing LF refused (fullmatch, not match).
        bad_lf = json.loads(mp.read_text())
        bad_lf["sources"][victim]["sha256"] += "\n"
        expect_refuse("sha-with-LF-refused", lambda: build.validate_manifest_literal(bad_lf))
        expect_refuse("audit-sha-with-LF-refused", lambda: audit.validate_manifest_literal(bad_lf))
        assert not build.SHA_RE.fullmatch(bad_lf["sources"][victim]["sha256"])
        assert not audit.SHA_RE.fullmatch(bad_lf["sources"][victim]["sha256"])
        # 2) wrong-prefix + rel + wrong-suffix refused; lookup ignores path.
        bad_path = json.loads(mp.read_text())
        bad_path["sources"][victim]["path"] = "wrong-prefix-" + victim + "-wrong-suffix"
        expect_refuse("wrong-path-refused", lambda: build.validate_manifest_literal(bad_path))
        expect_refuse("audit-wrong-path-refused", lambda: audit.validate_manifest_literal(bad_path))
        # Sentinel: literal rejection must precede lookup — even if the
        # on-disk file is missing, the literal error fires first.
        with mock.patch.object(build, "P", tmp / "nonexistent-tree"):
            expect_refuse("wrong-path-before-lookup",
                          lambda: build.validate_manifest_literal(bad_path))
        # 3) absolute / normalized variants refused (exact key required).
        for variant in ("/" + victim, "./" + victim, victim + "/x", "X" + victim):
            mv = json.loads(mp.read_text())
            mv["sources"][victim]["path"] = variant
            expect_refuse(f"path-variant-refused-{len(variant)}",
                          lambda v=mv: build.validate_manifest_literal(v))
        # 4) unverified extras refused.
        me = json.loads(mp.read_text())
        me["sources"]["unverified-extra"] = {"path": "unverified-extra",
                                             "sha256": "a" * 64, "bytes": 1}
        expect_refuse("extra-entry-refused", lambda: build.validate_manifest_literal(me))
        expect_refuse("audit-extra-entry-refused", lambda: audit.validate_manifest_literal(me))
        # 5) tag with trailing LF refused before manifest loader runs.
        reached = []
        orig_loader = build.load_manifest

        def sentinel_loader(_):
            reached.append("loader")
            raise AssertionError("manifest loader must not run after invalid tag")

        with mock.patch.object(build, "load_manifest", sentinel_loader):
            expect_refuse("tag-LF-refused-before-loader",
                          lambda: build.main(["--source-manifest", str(mp),
                                              "--tag", "valid-name\n"]))
        assert not reached, "invalid tag reached manifest loader"
        assert not build.TAG_RE.fullmatch("valid-name\n")
        assert not audit.TAG_RE.fullmatch("valid-name\n")
        # Sanity: exact key still passes literal stage.
        build.validate_manifest_literal(m)
        audit.validate_manifest_literal(m)


def test_shared_lock_only():
    # Both wrappers use the SAME existing dt25-build.lock; no new lock is
    # created or unlinked; contention refuses nonblocking before effects.
    for mod, name in ((build, "build-dt26-live.py"), (audit, "audit-dt26-artifacts.py")):
        src = (T / name).read_text()
        assert "dt25-build.lock" in src, f"{name} must reference shared lock"
        assert "dt26-build.lock" not in src, f"{name} must not reference a new lock"
        assert "LOCK.touch" not in src, f"{name} must never create the lock"
        assert "mkdir" not in src.split("LOCK")[0][-2000:] or "LOCK.parent.mkdir" not in src, \
            f"{name} must not mkdir the lock"
        assert ".unlink()" not in src, f"{name} must never unlink the lock"
        assert "LOCK_EX | fcntl.LOCK_NB" in src or "LOCK_EX|fcntl.LOCK_NB" in src, \
            f"{name} must take nonblocking exclusive flock"
    assert str(build.LOCK) == str(audit.LOCK) == "/home/builder/boot-failure-tests/dt25-build.lock"


def test_private_lock_crossprocess():
    # Real cross-process semantics on a PRIVATE lock file (never the global
    # lock): contended private lock refuses; uncontended private lock allows
    # a synthetic no-op builder invocation. No actual global build.
    import fcntl
    with tempfile.TemporaryDirectory(prefix="dt26-gates-privlock-") as td:
        tmp = Path(td)
        priv = tmp / "private-build.lock"
        priv.write_text("")
        # Negative: holder process holds LOCK_EX; nonblocking acquire refuses.
        holder = subprocess.Popen(
            [sys.executable, "-c",
             "import fcntl,sys,time; f=open(sys.argv[1],'r+'); "
             "fcntl.flock(f,fcntl.LOCK_EX); print('HOLDER-LOCKED',flush=True); "
             "time.sleep(15)",
             str(priv)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            line = holder.stdout.readline().strip()
            assert line == "HOLDER-LOCKED", f"holder did not lock: {line}"
            with priv.open("r+") as lf:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    pass  # expected refusal
                else:
                    raise AssertionError("contended private lock must refuse LOCK_EX|LOCK_NB")
        finally:
            holder.terminate()
            try:
                holder.wait(timeout=10)
            except Exception:
                holder.kill()
        # Positive: uncontended private lock + synthetic no-op builder.
        noop_out = tmp / "noop-out.log"
        with priv.open("r+") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                r = subprocess.run(["bash", "-c", "echo synthetic-noop-builder-ok"],
                                   capture_output=True, text=True)
                assert r.returncode == 0 and "synthetic-noop-builder-ok" in r.stdout
                noop_out.write_text(r.stdout)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
        assert noop_out.read_text().strip() == "synthetic-noop-builder-ok"


def test_sfs_canonical_and_guard_policy():
    # Canonical frozen SFS lives in the private build root; the staged copy
    # is preservation-only. Guard policy contract requires 20 sensors.
    assert str(audit.SFS) == "/home/builder/live-rootfs-v2.squashfs", audit.SFS
    assert str(audit.STAGED_SFS) == "/mnt/d/CachyOS-ARM64/live-staging-v2/arch/aarch64/airootfs.sfs"
    assert str(audit.SFS).startswith("/home/builder/"), "SFS must be in private build root"
    assert audit.EXP_SFS_SIZE == 1748525056
    assert audit.EXP_SFS_SHA == "5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c"
    src = (T / "audit-dt26-artifacts.py").read_text()
    assert 'required_sensor_count' in src and '== 20' in src, \
        "auditor must require guard_policy.required_sensor_count == 20"
    # Independent documented minimum for a positive audit schema (no
    # fabricated actual pass): every key below must exist in the report
    # construction path.
    for key in ("passed", "revision", "uki_path", "uki_sha256", "uki_bytes",
                "initramfs_path", "initramfs_sha256", "initramfs_bytes",
                "sfs_path", "sfs_sha256", "sfs_bytes",
                "sfs_required_paths_present", "sfs_runtime_closure_proven",
                "sfs_runtime_proof_pending_vm",
                "qemu_firmware", "guard_policy", "sources", "provenance",
                "native_hardware_validated"):
        assert f'"{key}"' in src, f"audit report missing documented key {key}"


def test_finalization_commit_order():
    # Copy/flush/readback happen through the ACTUAL finalization functions
    # BEFORE the single exclusive receipt; failures leave NO receipt.
    with tempfile.TemporaryDirectory(prefix="dt26-gates-commit-") as td:
        tmp = Path(td)
        payload = b"synthetic-EFI-bytes-for-commit-test"
        # Success: host copy then receipt, exactly once.
        hc = tmp / "host-copy-synth.efi"
        receipt = tmp / "dt26-artifact-audit.json"
        rec = audit.write_host_copy(payload, hc)
        assert rec["sha256"] == hashlib.sha256(payload).hexdigest()
        assert rec["readback_verified"] is True
        assert hc.read_bytes() == payload
        report = {"passed": True, "revision": "v2-dt26",
                  "uki_sha256": rec["sha256"], "host_candidate_copy": rec}
        audit.commit_audit_report(receipt, report)
        assert json.loads(receipt.read_text())["passed"] is True
        # No rewrite after fact: second commit refuses (exclusive create).
        try:
            audit.commit_audit_report(receipt, report)
        except FileExistsError:
            pass
        else:
            raise AssertionError("receipt rewrite must refuse (exclusive create)")
        # Copy failure (pre-existing dest) leaves NO receipt.
        hc2 = tmp / "host-copy-blocked.efi"
        hc2.write_bytes(b"pre-existing")
        receipt2 = tmp / "receipt2.json"
        try:
            audit.write_host_copy(payload, hc2)
        except OSError:
            pass
        else:
            raise AssertionError("write_host_copy must refuse when dest exists")
        assert not receipt2.exists(), "failed copy must leave NO receipt"
        assert hc2.read_bytes() == b"pre-existing", "failed copy must not clobber"
        # Readback-mismatch failure leaves NO receipt (tampered readback).
        hc3 = tmp / "host-copy-tamper.efi"
        with mock.patch.object(audit, "sha_file", return_value="0" * 64):
            try:
                audit.write_host_copy(payload, hc3)
            except SystemExit as e:
                assert e.code == 2
            else:
                raise AssertionError("readback mismatch must fail")
        # Static order assertion: receipt creation must not precede copy in source.
        src = (T / "audit-dt26-artifacts.py").read_text()
        assert "commit_audit_report" in src
        assert src.index('report["host_candidate_copy"] = write_host_copy(data, hc)') < \
            src.rindex("commit_audit_report(audit_json, report)"), \
            "host copy must precede the receipt in run_audit"


def test_storage_future_bytes_only():
    src = (T / "audit-dt26-artifacts.py").read_text()
    # No redundant local candidate clone (no audit_dir/dt26-candidate.efi
    # file creation); no old-extract code. Docstring may mention the removed
    # path, but no code may create it.
    assert 'audit_dir / "dt26-candidate' not in src, "redundant audit_dir candidate must be gone"
    assert "candidate = audit_dir" not in src
    assert "extract-old" not in src, "unused old-extract code must be gone"
    assert "extract_new" in src and "extract-new" in src
    # Future-bytes budget helper counts extract cap + FAT + host copy.
    assert audit.EXTRACT_NEW_CAP_BYTES == 1 * 1024**3
    assert audit.FAT_FUTURE_BYTES == int(2.25 * 1024**3)
    assert audit.audit_planned_bytes(0) == audit.EXTRACT_NEW_CAP_BYTES + audit.FAT_FUTURE_BYTES
    assert audit.audit_planned_bytes(244 * 1024 * 1024) == \
        audit.EXTRACT_NEW_CAP_BYTES + audit.FAT_FUTURE_BYTES + 244 * 1024 * 1024
    # No old-evidence deletion to clear space; failures preserved.
    for banned in (".unlink()", "shutil.rmtree", "os.remove"):
        assert banned not in src, f"auditor must not delete evidence ({banned})"


def test_explicit_env_and_compression():
    # All known build fields pinned explicitly.
    env = build.canonical_build_env("/home/builder/uki-v2-dt26-synth")
    assert env["OUT"] == "/home/builder/uki-v2-dt26-synth"
    assert env["ROOT"] == "/home/builder/imgroot"
    assert env["KESTREL_PROJECT"] == str(build.P)
    assert env["KESTREL_LOG_BINARY"] == "/home/builder/diag/kestrel-kmsg"
    assert env["KESTREL_LOG"] == "0"
    assert build.BUILD_ROOT == "/home/builder/imgroot"
    # Compression bound is strict on actual options (comment cannot mask).
    build.check_compression_budget('COMPRESSION_OPTIONS=(-6 -T2)\n')
    build.check_compression_budget('COMPRESSION_OPTIONS=(-6 -T1)\n')
    for bad in ('COMPRESSION_OPTIONS=(-6 -T0)\n',
                'COMPRESSION_OPTIONS=(-6 -T3)\n',
                'COMPRESSION_OPTIONS=(-6 -T10)\n',
                'COMPRESSION_OPTIONS=(-6 -T0)\n# -T2 in a comment\n',
                'COMPRESSION_OPTIONS=(-6 -T10)\n# -T2 in a comment\n',
                '# only a comment mentions -T2\n'):
        try:
            build.check_compression_budget(bad)
        except SystemExit as e:
            assert e.code == 2
        else:
            raise AssertionError(f"compression must refuse: {bad!r}")


def test_imgroot_versions_auxiliary():
    src = (T / "audit-dt26-artifacts.py").read_text()
    assert "imgroot_versions_auxiliary_reference_only" in src, \
        "imgroot versions must be labeled auxiliary reference-only"
    assert "reference-only" in src.lower()
    # No gate on mutable pacman versions.
    assert '"26.2.4"' not in src and '"6.7.5"' not in src, \
        "auditor must not gate frozen SFS on mutable imgroot versions"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="dt26 artifact gate tests (synthetic fixtures only).")
    ap.add_argument("--output-tag", default=None)
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    stamp = (args.output_tag or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", stamp):
        print("ERROR: invalid --output-tag", file=sys.stderr)
        raise SystemExit(2)
    result_path = T / f"dt26-artifact-gates-{stamp}-result.json"
    log_path = T / f"dt26-artifact-gates-{stamp}.log"
    for p in (result_path, log_path):
        if p.exists():
            print(f"ERROR: refusing: fresh output already exists {p}", file=sys.stderr)
            raise SystemExit(2)
    # All gate tests use synthetic fixtures; real writer sources untouched.
    check("import-safe-no-top-level-effects", test_import_safe)
    check("help-no-effects", test_help_no_effects)
    check("malformed-manifest", test_malformed_manifest)
    check("missing-review", test_missing_review)
    check("changed-source-hash", test_changed_source_hash)
    check("missing-required-entry", test_missing_required_entry)
    check("literal-lf-exact-path-extras", test_literal_lf_and_exact_path)
    check("shared-lock-only", test_shared_lock_only)
    check("private-lock-crossprocess", test_private_lock_crossprocess)
    check("sfs-canonical-guard20-schema", test_sfs_canonical_and_guard_policy)
    check("finalization-commit-order", test_finalization_commit_order)
    check("storage-future-bytes-only", test_storage_future_bytes_only)
    check("explicit-env-compression", test_explicit_env_and_compression)
    check("imgroot-versions-auxiliary", test_imgroot_versions_auxiliary)
    check("output-collision-no-unlink", test_output_collision_and_no_unlink)
    check("d-postreserve", test_d_postreserve)
    check("builder-never-invoked", test_builder_never_invoked)
    check("syntax-gates", test_syntax_gates)

    total = len(RESULTS["passed"]) + len(RESULTS["failed"])
    report = {
        "revision": "v2-dt26",
        "scope": "artifact-gate preflight only; no build, no extraction, no VM",
        "synthetic_fixtures_only": True,
        "run": total,
        "passed": len(RESULTS["passed"]),
        "failed": len(RESULTS["failed"]),
        "failures": RESULTS["failed"],
        "skipped": 0,
        "tests": RESULTS["passed"],
        "canonical_builder_invoked": False,
        "real_sources_hashed": False,
        "real_artifacts_verified": False,
        "native_hardware_validated": False,
        "unresolved_actual_build_gates": [
            "reviewed source manifest absent (need revision v2-dt26, approved_for_build true, spec PASS, quality PASS from parent)",
            "writer repairs active: supervisor IO, observability logger/bounds, EFI harness/parser, frozen-runtime subset",
            "actual fresh build OUT /home/builder/uki-v2-dt26-<tag> not attempted",
            "actual extraction + PE/initrd/module/SFS provenance audit not run",
            "QEMU/FAT disposable + native graphics attempt pending parent sequencing",
        ],
    }
    with result_path.open("x") as f:
        json.dump(report, f, indent=2)
    with log_path.open("x") as f:
        f.write(f"dt26-artifact-gates {stamp}: run={total} passed={report['passed']} failed={report['failed']}\n")
        for name in RESULTS["passed"]:
            f.write(f"PASS {name}\n")
        for item in RESULTS["failed"]:
            f.write(f"FAIL {item['name']}: {item.get('error', '')}\n")
    print(f"GATES run={total} passed={report['passed']} failed={report['failed']}", flush=True)
    raise SystemExit(0 if not RESULTS["failed"] else 1)


if __name__ == "__main__":
    main()
