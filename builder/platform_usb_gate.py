"""Validate pre-pivot module closure for the Slim 3 USB repeater bus.

Presence alone is insufficient: these modular bus/providers must be in
mkinitcpio's MODULES list, before root can be read from USB. This does not
validate physical wiring, PHY operation, Type-C services or native boot.
"""
import re
import shlex
from pathlib import Path

REQUIRED_MODULES = (
    "gpi",
    "i2c-qcom-geni",
    "phy-nxp-ptn3222",
    "qrtr",
    "qrtr-smd",
)


def normalized(name):
    return name.replace("-", "_")


def check_platform_usb(root):
    root = Path(root)
    config = (root / "config").read_text()
    match = re.search(r'^MODULES="([^"\n]*)"$', config, re.MULTILINE)
    forced = {normalized(name) for name in shlex.split(match.group(1))} if match else set()
    packed = {
        normalized(path.name.split(".ko", 1)[0])
        for path in (root / "usr/lib/modules").rglob("*.ko*")
        if path.is_file()
    }
    checks = {}
    for name in REQUIRED_MODULES:
        key = normalized(name)
        checks[f"platform_{key}_packed"] = key in packed
        checks[f"platform_{key}_early_load"] = key in forced
    return checks
