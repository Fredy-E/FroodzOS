#!/usr/bin/env python3
"""Validate packed graphics archive closure for dt25.

Fail-closed: every clause must independently reject a broken image.
This does not validate native graphics, temperature, or boot.
"""
import json
import re
from pathlib import Path

REQUIRED_GRAPHICS_ETC = (
    "etc/kestrel-graphics-supervisor",
    "etc/kestrel-graphics-guard",
    "etc/kestrel-graphics-env",
    "etc/kestrel-graphics-service",
    "etc/kestrel-graphics-sddm",
    "etc/kestrel-graphics-policy",
    "etc/kestrel-graphics-tty2",
)

REQUIRED_TEXT_ETC = (
    "etc/kestrel-text-login",
    "etc/kestrel-text-proof",
    "etc/kestrel-text-bashrc",
    "etc/kestrel-text-getty.conf",
)

REQUIRED_OVERLAY_HELPERS = (
    "usr/bin/findmnt",
    "usr/bin/mountpoint",
)

REQUIRED_LIBS = (
    "usr/lib/libmount.so.1",
    "usr/lib/libblkid.so.1",
    "usr/lib/libsmartcols.so.1",
    "usr/lib/libudev.so.1",
    "usr/lib/libsystemd.so.0",
    "usr/lib/libc.so.6",
)


def _noncomment_lines(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        yield line


def check_platform_graphics(root):
    root = Path(root)
    checks = {}
    hook = root / "hooks/kestrel_graphics"
    hook_text = hook.read_text(errors="replace") if hook.is_file() else ""
    hook_exec = "\n".join(_noncomment_lines(hook_text))
    checks["graphics_hook_present"] = hook.is_file()
    checks["graphics_hook_gated"] = (
        hook.is_file()
        and "getarg kestrel_graphics" in hook_text
        and "= 1" in hook_text
        and "return 0" in hook_text
    )
    checks["graphics_hook_requires_mountpoint"] = "command -v mountpoint" in hook_text
    checks["graphics_hook_requires_findmnt"] = "command -v findmnt" in hook_text
    checks["graphics_hook_requires_overlay"] = (
        '"overlay"' in hook_text and "FSTYPE" in hook_text
    )
    checks["graphics_no_cowspace_fallback"] = "cowspace" not in hook_exec
    checks["graphics_no_global_efi_writer"] = (
        not (root / "usr/bin/kestrel-efilog-loop").exists()
        and "efivarfs" not in hook_exec
        and "KestrelBoot" not in hook_exec
        and "efivars" not in hook_exec
    )
    checks["graphics_no_python_packed"] = (
        not (root / "usr/bin/python3").exists()
        and not (root / "usr/bin/python").exists()
    )
    for rel in REQUIRED_GRAPHICS_ETC:
        key = "graphics_" + Path(rel).name.replace("-", "_").replace(".", "_") + "_present"
        checks[key] = (root / rel).is_file()
    for rel in REQUIRED_TEXT_ETC:
        key = "graphics_text_" + Path(rel).name.replace("-", "_").replace(".", "_") + "_preserved"
        checks[key] = (root / rel).is_file()
    checks["graphics_text_hook_preserved"] = (root / "hooks/kestrel_text").is_file()
    checks["graphics_logger_service_preserved"] = (
        root / "etc/kestrel-usb-log.service"
    ).is_file()
    for rel in REQUIRED_OVERLAY_HELPERS:
        p = root / rel
        key = "graphics_" + Path(rel).name + "_elf_present"
        try:
            is_elf = False
            if p.is_file() and not p.is_symlink():
                with p.open("rb") as f:
                    magic = f.read(4)
                is_elf = magic == b"\x7fELF"
            checks[key] = is_elf and bool(p.stat().st_mode & 0o111)
        except OSError:
            checks[key] = False
    for rel in REQUIRED_LIBS:
        key = "graphics_lib_" + Path(rel).name.replace(".", "_").replace("-", "_") + "_present"
        checks[key] = (root / rel).is_file()
    # Config ordering: kestrel_graphics after kestrel_text in LATEHOOKS.
    try:
        config_text = (root / "config").read_text(errors="replace")
    except OSError:
        config_text = ""
    m = re.search(r'^LATEHOOKS="([^"]*)"', config_text, re.MULTILINE)
    if m:
        parts = m.group(1).split()
        checks["graphics_config_ordered_after_text"] = (
            "kestrel_graphics" in parts
            and "kestrel_text" in parts
            and parts.index("kestrel_graphics") > parts.index("kestrel_text")
        )
        checks["graphics_config_contains_hook"] = "kestrel_graphics" in parts
    else:
        checks["graphics_config_ordered_after_text"] = False
        checks["graphics_config_contains_hook"] = False
    # Policy must be exact fail-closed runtime policy.
    policy_path = root / "etc/kestrel-graphics-policy"
    try:
        data = json.loads(policy_path.read_text())
        types = data.get("required_sensor_types")
        ok_types = (
            isinstance(types, list)
            and len(types) == 20
            and all(isinstance(x, str) and x for x in types)
            and not any("batt" in x.lower() for x in types)
            and len(set(types)) == 20
        )
        ok_stop = data.get("experiment_stop_mc") == 80000
        ok_min = data.get("experiment_minimum_mc") == 5000
        ok_count = data.get("required_sensor_count") == 20
        ok_batt = data.get("battery_substitution_allowed") is False
        checks["graphics_policy_valid"] = ok_types and ok_stop and ok_min and ok_count and ok_batt
    except (OSError, ValueError, UnicodeError):
        checks["graphics_policy_valid"] = False
    return checks
