# SPDX-License-Identifier: GPL-2.0-or-later
"""CLI: fz-smartlog run | once | report | snapshot | status (plus prune)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from .config import Config
from .dest import DestManager
from .snapshot import Snapshotter, run_cli as snapshot_cli


def _boot_roots(config):
    roots = []
    if config.marker_ok:
        roots.append(config.dest_roots()["stick"])
    roots.append(config.dest_roots()["persist"])
    roots.append(config.dest_roots()["ram"])
    return roots


def find_latest_boot(config):
    candidates = []
    for root in _boot_roots(config):
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for name in names:
            path = os.path.join(root, name)
            if not name.startswith("boot-") or not os.path.isdir(path):
                continue
            started = 0.0
            try:
                with open(os.path.join(path, "boot.json"), "r",
                          encoding="utf-8", errors="replace") as fh:
                    started = float(json.load(fh).get("started_epoch") or 0)
            except (OSError, ValueError, TypeError):
                pass
            if not started:
                try:
                    started = os.path.getmtime(path)
                except OSError:
                    started = 0
            candidates.append((started, path))
    candidates.sort(reverse=True)
    return candidates[0][1] if candidates else None


def cmd_report(config):
    boot = find_latest_boot(config)
    if not boot:
        print("fz-smartlog: no boot folder found (marker=%s)" % config.marker_ok)
        return 1
    for path in (os.path.join(boot, "smart", "summary.txt"),
                 os.path.join(boot, "summary.txt")):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                print(fh.read(), end="")
            return 0
        except OSError:
            continue
    print("fz-smartlog: no summary.txt in %s" % boot)
    return 1


def cmd_once(config):
    temp = tempfile.mkdtemp(prefix="fz-smartlog-once-")
    try:
        snap = Snapshotter(temp, boot_id=config.boot_id, where="terminal",
                          max_kb=2048, deadline_s=config.snapshot_deadline_s,
                          privacy=config.privacy)
        body, summary = snap.build_once()
        print(body)
        print("===== summary")
        print(summary, end="")
        return 0
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def cmd_status(config):
    boot = find_latest_boot(config)
    status = {
        "schema": 3,
        "version": "3.0",
        "boot_id": config.boot_id,
        "marker": bool(config.marker_ok),
        "record_full": bool(config.record_full),
        "privacy": config.privacy,
        "dest_candidates": list(config.active_dest_order()),
        "roots": config.dest_roots(),
        "latest_boot": boot,
        "env_path": os.path.join(config.state, "env"),
        "ready": os.path.exists(os.path.join(config.state, "ready")),
        "cmdline": list(config.cmdline_list),
    }
    print(json.dumps(status, indent=1, sort_keys=True))
    return 0


def cmd_prune(config):
    dest = DestManager(config, config.boot_id)
    dest.choose_initial()
    deleted = dest.prune(os.path.basename(dest.current.boot_dir))
    for name in deleted:
        print(name)
    return 0


def cmd_snapshot(config, args):
    """Allow 'fz-smartlog snapshot --reason ...' without an explicit --dest."""
    args = list(args)
    has_dest = any(item == "--dest" or item.startswith("--dest=") for item in args)
    if not has_dest:
        boot = find_latest_boot(config)
        if not boot:
            boot = os.path.join(config.dest_roots()["ram"],
                                "boot-%s" % config.boot_id)
        args = ["--dest", boot] + args
    if not any(item == "--boot-id" or item.startswith("--boot-id=") for item in args):
        args[2:2] = ["--boot-id", config.boot_id]
    if not any(item == "--where" or item.startswith("--where=") for item in args):
        args.extend(["--where", "stick" if config.marker_ok else "ram"])
    if not any(item == "--privacy" or item.startswith("--privacy=") for item in args):
        args.extend(["--privacy", config.privacy])
    if not any(item == "--deadline" or item.startswith("--deadline=") for item in args):
        args.extend(["--deadline", str(config.snapshot_deadline_s)])
    if not any(item == "--max-kb" or item.startswith("--max-kb=") for item in args):
        args.extend(["--max-kb", str(config.snapshot_max_kb)])
    return snapshot_cli(args)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    command = args.pop(0) if args else "run"
    config = Config.from_env()
    if command in ("run", "supervise"):
        from .supervisor import run_supervisor
        return run_supervisor(config)
    if command == "once":
        return cmd_once(config)
    if command == "report":
        return cmd_report(config)
    if command == "snapshot":
        return cmd_snapshot(config, args)
    if command == "status":
        return cmd_status(config)
    if command == "prune":
        return cmd_prune(config)
    if command in ("help", "-h", "--help"):
        print("usage: fz-smartlog run|once|report|snapshot|status|prune")
        return 0
    print("usage: fz-smartlog run|once|report|snapshot|status|prune", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
