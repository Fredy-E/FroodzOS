#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-bootmnt-ro: the shipped shutdown helper that remounts the boot stick read-only; checks the unit, the script and the build wiring."""
import shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / 'builder/public-image/rootfs-overlay'
SCRIPT = OVL / 'usr/local/sbin/fz-bootmnt-ro'
UNIT = OVL / 'etc/systemd/system/fz-bootmnt-ro.service'
BUILD = ROOT / 'builder/public-image/build-root.sh'


class BootmntRo(unittest.TestCase):
    def test_unit_runs_the_helper_at_stop_and_before_shutdown(self):
        t = UNIT.read_text()
        self.assertIn('Conflicts=shutdown.target', t)
        self.assertIn('ExecStop=/usr/local/sbin/fz-bootmnt-ro', t)
        self.assertIn('ConditionPathIsMountPoint=/run/archiso/bootmnt', t)   # no effect on media that is not a live stick
        self.assertIn('TimeoutStopSec=', t)

    def test_script_never_kills_init_or_systemd_and_always_exits_zero(self):
        t = SCRIPT.read_text()
        self.assertTrue(t.startswith('#!/bin/sh'))
        self.assertIn('-le 1', t)                                 # PID 1 and below are skipped
        self.assertIn('systemd*|sh|bash) continue', t)
        self.assertTrue(t.rstrip().endswith('exit 0'))            # a failed remount must never block the shutdown
        self.assertNotIn('\r', t)

    @unittest.skipUnless(shutil.which('sh'), 'sh not installed')
    def test_script_syntax(self):
        self.assertEqual(subprocess.run(['sh', '-n', str(SCRIPT)]).returncode, 0)

    def test_build_root_installs_and_enables_it(self):
        b = BUILD.read_text()
        self.assertIn('usr/local/sbin/fz-bootmnt-ro etc/systemd/system/fz-bootmnt-ro.service', b)
        self.assertIn('usr/local/sbin/fz-bootmnt-ro|', b)         # mode 755
        self.assertIn('multi-user.target.wants/fz-bootmnt-ro.service', b)


if __name__ == '__main__':
    unittest.main()
