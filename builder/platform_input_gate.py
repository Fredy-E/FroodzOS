"""Require the modular I2C-HID path before the live-root transition."""
import re
import shlex
from pathlib import Path
from platform_usb_gate import normalized

REQUIRED_MODULES = ('i2c-hid', 'i2c-hid-of', 'hid-generic')


def check_platform_input(root):
    root = Path(root)
    config = (root / 'config').read_text()
    match = re.search(r'^MODULES="([^"\n]*)"$', config, re.MULTILINE)
    forced = {normalized(name) for name in shlex.split(match.group(1))} if match else set()
    packed = {normalized(path.name.split('.ko', 1)[0])
              for path in (root / 'usr/lib/modules').rglob('*.ko*') if path.is_file()}
    checks = {}
    for name in REQUIRED_MODULES:
        key = normalized(name)
        checks['input_' + key + '_packed'] = key in packed
        checks['input_' + key + '_early_load'] = key in forced
    return checks
