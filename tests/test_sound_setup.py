#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-sound-setup: stages the laptop's own audio firmware (dry run), refuses an incomplete set, and is wired into the root build."""
import os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / 'builder/public-image/rootfs-overlay'
SCRIPT = OVL / 'usr/local/sbin/fz-sound-setup'
UNIT = OVL / 'etc/systemd/system/fz-sound-setup.service'
BUILD = ROOT / 'builder/public-image/build-root.sh'
NEEDED = ['qcadsp8380.mbn', 'adsp_dtbs.elf', 'adspr.jsn', 'adsps.jsn', 'adspua.jsn', 'battmgr.jsn']
POSIX = sys.platform != 'win32' and shutil.which('bash') and shutil.which('find')


class SoundSetup(unittest.TestCase):
    def run_script(self, src, *extra):
        env = dict(os.environ, FZ_SOUND_TEST='1', FZ_SOUND_LOG=str(Path(src) / 'log.txt'))
        return subprocess.run(['bash', str(SCRIPT), '--dry-run', '--force', '--source', str(src), *extra], capture_output=True, text=True, env=env)

    def test_unit_is_opt_in_by_kernel_option(self):
        t = UNIT.read_text()
        self.assertIn('ConditionKernelCommandLine=fz_sound=1', t)
        self.assertIn('ExecStart=/usr/local/sbin/fz-sound-setup', t)

    def test_script_only_reads_windows_and_writes_to_the_live_firmware_overlay(self):
        t = SCRIPT.read_text()
        self.assertNotIn('\r', t)
        self.assertIn('mount -t ntfs3 -o ro,', t)                 # the Windows partition is only ever mounted read-only
        self.assertIn('ntfs-3g -o ro,', t)
        self.assertIn('/usr/lib/firmware/updates/', t)            # RAM overlay, never the boot stick
        self.assertNotIn('curl', t); self.assertNotIn('wget', t)  # nothing is downloaded or uploaded

    def test_build_root_installs_and_enables_it(self):
        b = BUILD.read_text()
        self.assertIn('usr/local/sbin/fz-sound-setup etc/systemd/system/fz-sound-setup.service', b)
        self.assertIn('usr/local/sbin/fz-sound-setup|', b)        # mode 755
        self.assertIn('multi-user.target.wants/fz-sound-setup.service', b)

    def test_internal_disk_is_read_only_and_hidden_from_the_desktop(self):
        rule = OVL / 'etc/udev/rules.d/90-froodzos-internal-ro.rules'
        t = rule.read_text()
        self.assertIn('KERNEL=="nvme[0-9]*n[0-9]*"', t)          # the disk and its partitions
        self.assertIn('ATTR{ro}="1"', t)
        self.assertIn('UDISKS_IGNORE', t)
        self.assertIn('etc/udev/rules.d/90-froodzos-internal-ro.rules', BUILD.read_text())

    @unittest.skipUnless(POSIX, 'needs bash and find')
    def test_script_syntax(self):
        self.assertEqual(subprocess.run(['bash', '-n', str(SCRIPT)]).returncode, 0)

    @unittest.skipUnless(POSIX, 'needs bash and find')
    def test_dry_run_lists_every_file_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / 'qcadsp8380.inf_arm64_deadbeef'; sub.mkdir()
            for n in NEEDED: (sub / n).write_bytes(b'x' * 10)
            r = self.run_script(d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for n in NEEDED: self.assertIn('stage ' + n, r.stdout)
            self.assertIn('dry run: nothing written', r.stdout)

    @unittest.skipUnless(POSIX, 'needs bash and find')
    def test_incomplete_set_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for n in NEEDED[:-1]: (Path(d) / n).write_bytes(b'x')
            r = self.run_script(d)
            self.assertEqual(r.returncode, 1)
            self.assertIn('MISSING battmgr.jsn', r.stdout)


if __name__ == '__main__':
    unittest.main()
