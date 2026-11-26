# SPDX-License-Identifier: GPL-2.0-or-later
"""fz_smartlog - smartlog v3, the always-on black-box recorder for FroodzOS.

The package is deliberately stdlib-only.  The public entry points used by
other services are :func:`record_full`, :func:`cmdline_words` and
:class:`fz_smartlog.writer.StreamWriter`.
"""
from __future__ import annotations

import os

SCHEMA = 3
VERSION = "3.0"
MARKER_TEXT = "KESTREL_A64_USB_CAPTURE_V1"
MARKER_FILE = "KESTREL-LOG-TARGET"
DEFAULT_CMDLINE = "/proc/cmdline"
RECORD_FULL_WORD = "fz_record=full"

STREAMS = (
    "kernel", "journal", "systemd", "udev", "network", "power",
    "terminal", "ui", "waydroid",
)
PLUGIN_STREAMS = ("terminal", "ui", "waydroid")


def read_text(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def cmdline_source(path=None):
    """Return the cmdline text from an explicit path, FZ_CMDLINE, or /proc/cmdline.

    FZ_CMDLINE follows the existing fz-persist convention: it is a path when it
    names an existing file, otherwise its value is the cmdline itself (tests).
    """
    if path:
        text = read_text(path, None)
        if text is not None:
            return text
        return "" if path == DEFAULT_CMDLINE else path
    override = os.environ.get("FZ_CMDLINE")
    if override:
        if os.path.exists(override):
            return read_text(override)
        return override
    return read_text(DEFAULT_CMDLINE)


def cmdline_words(path=None):
    return cmdline_source(path).split()


def record_full(path=None):
    """True when the kernel command line contains the exact word fz_record=full."""
    return RECORD_FULL_WORD in cmdline_words(path)


def boot_id(path=None):
    override = os.environ.get("FZ_BOOT_ID")
    if override:
        return override.strip()
    return read_text(path or "/proc/sys/kernel/random/boot_id").strip() or "unknown"


def marker_present(bootmnt):
    text = read_text(os.path.join(bootmnt, MARKER_FILE)).strip()
    return text == MARKER_TEXT and os.path.isdir(os.path.join(bootmnt, "Logs"))
