#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-record-on / fz-record-journald / fz-debug / sleep hook: the record-everything switch, the runtime
journald policy, the debug profiles with their hazardous-path blocklist, and the docs that go with them.
Static checks run on Windows and Linux; shell execution is skipped where no POSIX sh exists."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / 'builder/public-image/rootfs-overlay'
REC_ON = OVL / 'usr/local/sbin/fz-record-on'
JOURNALD_HELPER = OVL / 'usr/local/sbin/fz-record-journald'
DEBUG = OVL / 'usr/local/sbin/fz-debug'
SLEEP = OVL / 'usr/lib/systemd/system-sleep/90-fz-record'
JOURNALD_CONF = OVL / 'etc/systemd/journald.conf.d/90-froodzos-record.conf'
SYSCTL_CONF = OVL / 'etc/sysctl.d/90-froodzos-record.conf'
JOURNALD_UNIT = OVL / 'etc/systemd/system/fz-record-journald.service'
KERNEL_UNIT = OVL / 'etc/systemd/system/fz-record-kernel.service'
DEBUG_UNIT = OVL / 'etc/systemd/system/fz-debug-boot.service'
DOC = ROOT / 'docs/smartlog/KERNEL-CMDLINE.md'
CMD_FIXTURE = ROOT / 'tests/fixtures/fz_record_cmdlines.tsv'
HAZARD_FIXTURE = ROOT / 'tests/fixtures/fz_debug_hazards.txt'

SH = shutil.which('sh') or shutil.which('bash')
POSIX = sys.platform != 'win32' and bool(SH)


def read(path):
    return path.read_text(encoding='utf-8')


def active_lines(text):
    return [line for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('FZ_')}
    if extra:
        env.update(extra)
    return env


def run_sh(script, *args, env=None):
    return subprocess.run([SH, str(script), *args], capture_output=True, text=True,
                          env=clean_env(env), timeout=60)


class RecordOn(unittest.TestCase):
    def run_on(self, cmdline, *args):
        return run_sh(REC_ON, *args, env={'FZ_CMDLINE': cmdline})

    def test_truth_table_from_fixture(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        lines = [ln for ln in read(CMD_FIXTURE).splitlines()
                 if ln.strip() and not ln.startswith('#')]
        self.assertTrue(lines)
        for line in lines:
            cmdline, expected = line.split('\t')
            if cmdline == '<empty>':
                cmdline = ''
            with self.subTest(cmdline=cmdline):
                r = self.run_on(cmdline)
                self.assertEqual(r.returncode, int(expected), r.stdout + r.stderr)

    def test_whitespace_separated_words(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        self.assertEqual(self.run_on('\tquiet\nfz_record=full\tother ').returncode, 0)
        self.assertEqual(self.run_on('quiet\nfz_record=off ').returncode, 1)

    def test_print_shows_the_active_profile_and_exits_zero(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.run_on('quiet fz_record=full', '--print')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), 'full')
        r = self.run_on('quiet', '--print')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), 'off')

    def test_unknown_argument_is_an_error(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        self.assertEqual(self.run_on('fz_record=full', '--nonsense').returncode, 2)

    def test_file_style(self):
        t = read(REC_ON)
        self.assertNotIn('\r', t)
        self.assertTrue(t.startswith('#!/bin/sh'))
        self.assertIn('SPDX-License-Identifier: GPL-2.0-or-later', t)
        self.assertIn('FZ_CMDLINE', t)


class JournaldLayer(unittest.TestCase):
    def test_shipped_etc_dropin_is_inert(self):
        t = read(JOURNALD_CONF)
        self.assertNotIn('\r', t)
        self.assertEqual(active_lines(t), [])            # journald reads this on every boot
        self.assertIn('fz_record=full', t)
        self.assertIn('/run/systemd/journald.conf.d/95-froodzos-record.conf', t)

    def test_shipped_sysctl_dropin_is_inert(self):
        t = read(SYSCTL_CONF)
        self.assertNotIn('\r', t)
        self.assertEqual(active_lines(t), [])            # sysctl.d cannot be conditional either
        self.assertIn('kernel.printk = 8 4 1 7', t)
        self.assertIn('log_buf_len', t)

    def test_generated_policy_is_w1_section_6(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = run_sh(JOURNALD_HELPER, '--print', env={'FZ_CMDLINE': 'fz_record=full fz_excess=1',
                                                    'FZ_RECORD_ON': str(REC_ON)})
        self.assertEqual(r.returncode, 0, r.stderr)
        for line in ('[Journal]', 'Storage=volatile', 'RuntimeMaxUse=512M',
                     'RuntimeKeepFree=128M', 'RuntimeMaxFileSize=64M', 'MaxFileSec=1h',
                     'MaxLevelStore=debug', 'MaxLevelSyslog=debug', 'MaxLevelKMsg=debug',
                     'ForwardToKMsg=yes', 'RateLimitIntervalSec=0', 'RateLimitBurst=0',
                     'SyncIntervalSec=1s', 'ReadKMsg=yes'):
            self.assertIn(line, r.stdout)

    def test_balanced_record_does_not_forward_journal_to_the_console_ring(self):
        # fz_record=full without fz_excess=1 must stay quiet on screen and fast: the journal is still stored at
        # debug level (smartlog reads the journal directly) but is not forwarded to kmsg.
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = run_sh(JOURNALD_HELPER, '--print', env={'FZ_CMDLINE': 'fz_record=full',
                                                    'FZ_RECORD_ON': str(REC_ON)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ForwardToKMsg=no', r.stdout)
        self.assertNotIn('ForwardToKMsg=yes', r.stdout)
        self.assertIn('MaxLevelStore=debug', r.stdout)
        self.assertNotIn('MaxLevelKMsg=debug', r.stdout)

    def test_excess_switch_needs_full_and_the_whole_word(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        for cmdline, code in (('fz_record=full fz_excess=1', 0), ('fz_excess=1', 1),
                              ('fz_record=full', 1), ('fz_record=full fz_excess=10', 1),
                              ('fz_record=full xfz_excess=1', 1)):
            r = run_sh(REC_ON, '--excess', env={'FZ_CMDLINE': cmdline})
            self.assertEqual(r.returncode, code, cmdline)

    def test_off_is_a_noop(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / 'journald.conf.d'
            r = run_sh(JOURNALD_HELPER, env={'FZ_CMDLINE': 'quiet', 'FZ_RECORD_ON': str(REC_ON),
                                             'FZ_RECORD_JOURNALD_RUN': str(run_dir)})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('nothing to do', r.stdout)
            self.assertFalse(run_dir.exists())

    def test_dry_run_full_writes_nothing(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / 'journald.conf.d'
            r = run_sh(JOURNALD_HELPER, env={'FZ_CMDLINE': 'fz_record=full',
                                             'FZ_RECORD_ON': str(REC_ON),
                                             'FZ_RECORD_JOURNALD_DRY': '1',
                                             'FZ_RECORD_JOURNALD_RUN': str(run_dir)})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('would write', r.stdout)
            self.assertIn('ForwardToKMsg=no', r.stdout)
            self.assertIn('would restart systemd-journald.service', r.stdout)
            self.assertFalse(run_dir.exists())

    def test_units_are_conditional_and_ordered(self):
        t = read(JOURNALD_UNIT)
        self.assertIn('ConditionKernelCommandLine=fz_record=full', t)
        self.assertIn('ExecStart=/usr/local/sbin/fz-record-journald', t)
        self.assertIn('After=systemd-journald.service', t)
        self.assertIn('Before=fz-smartlog.service', t)
        self.assertIn('WantedBy=sysinit.target', t)
        k = read(KERNEL_UNIT)
        self.assertIn('ConditionKernelCommandLine=fz_record=full', k)
        self.assertIn('printf "8 4 1 7" > /proc/sys/kernel/printk', k)
        self.assertIn('printf "4 4 1 7" > /proc/sys/kernel/printk', k)
        self.assertIn('fz-record-on --excess', k)
        self.assertIn('printf on > /proc/sys/kernel/printk_devkmsg', k)
        self.assertIn('/usr/local/sbin/fz-record-on', k)
        self.assertIn('WantedBy=sysinit.target', k)

    def test_helper_style(self):
        t = read(JOURNALD_HELPER)
        self.assertNotIn('\r', t)
        self.assertTrue(t.startswith('#!/bin/sh'))
        self.assertIn('SPDX-License-Identifier: GPL-2.0-or-later', t)
        self.assertIn('fz-record-journald:', t)


class DebugProfiles(unittest.TestCase):
    def debug(self, *args, cmdline=None, dry=True, same_dir=None):
        d = same_dir or tempfile.mkdtemp(prefix='fz-debug-test-')
        if same_dir is None:
            self.addCleanup(shutil.rmtree, d, True)
        env = {'FZ_DEBUG_CTL': os.path.join(d, 'control'),
               'FZ_DEBUG_TRACE': os.path.join(d, 'trace'),
               'FZ_RECORD_ON': str(REC_ON)}
        if dry:
            env['FZ_DEBUG_DRY'] = '1'
        if cmdline is not None:
            env['FZ_CMDLINE'] = cmdline
        return run_sh(DEBUG, *args, env=env)

    def test_wifi_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'wifi')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('control <- module mhi +pm; module qrtr_mhi +pm', r.stdout)
        for event in ('mhi_pm_st_transition', 'mhi_tryset_pm_state', 'mhi_intvec_states',
                      'mhi_channel_command_start', 'mhi_channel_command_end'):
            self.assertIn('events/mhi_host/%s/enable <- 1' % event, r.stdout)
        self.assertIn('buffer_size_kb <- 8192', r.stdout)
        self.assertIn('tracing_on <- 1', r.stdout)

    def test_audio_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'audio')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for module in ('snd_soc_wsa884x', 'soundwire_bus', 'soundwire_qcom', 'snd_soc_core',
                       'snd_soc_x1e80100', 'snd_q6apm', 'q6apm_dai', 'q6prm', 'snd_q6dsp_common'):
            self.assertIn('module %s +p' % module, r.stdout)
        for event in ('snd_soc_dapm_start', 'snd_soc_dapm_done', 'snd_soc_dapm_widget_power',
                      'snd_soc_dapm_widget_event_start', 'snd_soc_dapm_widget_event_done',
                      'snd_soc_dapm_path', 'snd_soc_dapm_connected', 'snd_soc_dapm_walk_done',
                      'snd_soc_bias_level_start', 'snd_soc_bias_level_done', 'snd_soc_jack_report'):
            self.assertIn('events/asoc/%s/enable <- 1' % event, r.stdout)
        self.assertIn('buffer_size_kb <- 4096', r.stdout)

    def test_usbc_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'usbc')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for selector in ('file drivers/usb/typec/* +p', 'file drivers/usb/typec/ucsi/* +p',
                         'file drivers/usb/typec/mux/* +p', 'file drivers/phy/qualcomm/* +p',
                         'file drivers/usb/dwc3/* +p', 'file drivers/soc/qcom/pmic_glink* +p'):
            self.assertIn(selector, r.stdout)

    def test_gpu_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'gpu')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for module in ('msm', 'drm', 'drm_kms_helper'):
            self.assertIn('module %s +p' % module, r.stdout)
        self.assertIn('/sys/module/drm/parameters/debug <- 0x3', r.stdout)
        self.assertIn('/sys/module/msm/parameters/dumpstate <- 1', r.stdout)

    def test_nvme_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'nvme')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for selector in ('file drivers/pci/pcie/* +p', 'file drivers/pci/controller/* +p',
                         'file drivers/phy/qualcomm/* +p'):
            self.assertIn(selector, r.stdout)

    def test_all_profile(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('on', 'all')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for marker in ('module mhi +pm', 'module snd_soc_wsa884x +p',
                       'drivers/usb/typec/* +p', 'module msm +p', 'drivers/pci/pcie/* +p'):
            self.assertIn(marker, r.stdout)

    def test_off_clears_everything(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('off')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for marker in ('module mhi -pm', 'module msm -p', 'file drivers/usb/typec/* -p',
                       '/sys/module/drm/parameters/debug <- 0',
                       '/sys/module/msm/parameters/dumpstate <- 0',
                       'events/asoc/snd_soc_dapm_path/enable <- 0'):
            self.assertIn(marker, r.stdout)

    def test_boot_trigger_from_cmdline(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.debug('--from-cmdline', cmdline='quiet fz_debug=wifi,audio splash')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('module mhi +pm', r.stdout)
        self.assertIn('module snd_soc_wsa884x +p', r.stdout)
        self.assertIn('events/mhi_host/mhi_pm_st_transition/enable <- 1', r.stdout)
        self.assertIn('events/asoc/snd_soc_dapm_start/enable <- 1', r.stdout)
        r = self.debug('--from-cmdline', cmdline='quiet fz_debug=wifi,bogus')
        self.assertIn('ignoring unknown fz_debug profile: bogus', r.stderr)
        r = self.debug('--from-cmdline', cmdline='quiet splash')
        self.assertIn('no usable fz_debug= profile', r.stderr)

    def test_hazardous_paths_are_refused(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        entries = [ln.strip() for ln in read(HAZARD_FIXTURE).splitlines()
                   if ln.strip() and not ln.startswith('#')]
        self.assertGreaterEqual(len(entries), 10)
        for entry in entries:
            with self.subTest(entry=entry):
                r = run_sh(DEBUG, 'check', entry, env={'FZ_DEBUG_DRY': '1'})
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn('BLOCK ' + entry, r.stdout)

    def test_safe_targets_are_allowed(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        for entry in ('/sys/kernel/debug/dynamic_debug/control',
                      '/sys/kernel/tracing/events/mhi_host/mhi_pm_st_transition/enable',
                      '/sys/kernel/debug/devices_deferred'):
            with self.subTest(entry=entry):
                r = run_sh(DEBUG, 'check', entry, env={'FZ_DEBUG_DRY': '1'})
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn('ALLOW ' + entry, r.stdout)

    def test_dry_run_is_idempotent(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        with tempfile.TemporaryDirectory() as d:
            first = self.debug('on', 'audio', same_dir=d)
            second = self.debug('on', 'audio', same_dir=d)
        self.assertEqual(first.stdout, second.stdout)

    def test_script_style_and_safety_text(self):
        t = read(DEBUG)
        self.assertNotIn('\r', t)
        self.assertTrue(t.startswith('#!/bin/sh'))
        self.assertIn('SPDX-License-Identifier: GPL-2.0-or-later', t)
        self.assertIn('FZ_DEBUG_DRY', t)
        self.assertIn('logger -t fz-debug', t)
        self.assertIn('/sys/kernel/debug/dynamic_debug/control', t)
        for hazard in ('regmap', 'simulate_fw_crash', 'gpiochip9', 'kexec'):
            self.assertIn(hazard, t)


class SleepHook(unittest.TestCase):
    def run_sleep(self, state, cmdline, *extra):
        return run_sh(SLEEP, state, *(extra or ('suspend',)),
                      env={'FZ_CMDLINE': cmdline, 'FZ_RECORD_ON': str(REC_ON),
                           'FZ_RECORD_SLEEP_DRY': '1'})

    def test_noop_without_the_switch(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        r = self.run_sleep('pre', 'quiet')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '')

    def test_records_pre_and_post_when_on(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        pre = self.run_sleep('pre', 'fz_record=full')
        self.assertEqual(pre.returncode, 0, pre.stdout + pre.stderr)
        self.assertIn('sleep pre (suspend)', pre.stdout)
        self.assertIn('suspend_stats', pre.stdout)
        self.assertIn('dry-run: would write /sys/power/pm_debug_messages <- 1', pre.stdout)
        self.assertIn('dry-run: would write /sys/power/pm_print_times <- 1', pre.stdout)
        post = self.run_sleep('post', 'fz_record=full')
        self.assertEqual(post.returncode, 0, post.stdout + post.stderr)
        self.assertIn('sleep post (suspend)', post.stdout)
        self.assertIn('dry-run: would write /sys/power/pm_debug_messages <- 0', post.stdout)

    def test_style_and_no_hazardous_reads(self):
        t = read(SLEEP)
        self.assertNotIn('\r', t)
        self.assertTrue(t.startswith('#!/bin/sh'))
        self.assertIn('SPDX-License-Identifier: GPL-2.0-or-later', t)
        self.assertIn('logger -t fz-record-sleep', t)
        code = '\n'.join(line for line in t.splitlines() if not line.lstrip().startswith('#'))
        for hazard in ('/sys/kernel/debug/gpio', 'regmap', 'pinctrl'):
            self.assertNotIn(hazard, code)


class UnitsAndDocs(unittest.TestCase):
    UNITS = (JOURNALD_UNIT, KERNEL_UNIT, DEBUG_UNIT)

    def test_unit_files_are_plain_ini_and_not_empty(self):
        for path in self.UNITS:
            with self.subTest(unit=path.name):
                t = read(path)
                self.assertNotIn('\r', t)
                self.assertTrue(t.strip())
                section = None
                seen = set()
                for lineno, line in enumerate(t.splitlines(), 1):
                    s = line.strip()
                    if not s or s.startswith('#') or s.startswith(';'):
                        continue
                    if s.startswith('[') and s.endswith(']'):
                        section = s[1:-1]
                        seen.add(section)
                        continue
                    self.assertIsNotNone(section, '%s:%d outside a section' % (path.name, lineno))
                    self.assertIn('=', s, '%s:%d is not key=value' % (path.name, lineno))
                    key = s.split('=', 1)[0]
                    self.assertTrue(key and ' ' not in key, '%s:%d bad key' % (path.name, lineno))
                self.assertTrue({'Unit', 'Service', 'Install'} <= seen, path.name)

    def test_debug_boot_unit_is_ordered_before_network_manager(self):
        t = read(DEBUG_UNIT)
        self.assertIn('ConditionKernelCommandLine=fz_debug', t)
        self.assertIn('Before=NetworkManager.service', t)
        self.assertIn('ExecStart=/usr/local/sbin/fz-debug --from-cmdline', t)
        self.assertIn('WantedBy=multi-user.target', t)

    def test_docs_contain_the_ready_to_paste_sets(self):
        t = read(DOC)
        self.assertNotIn('\r', t)
        for token in ('log_buf_len=16M', 'printk.devkmsg=on', 'loglevel=8', 'printk.time=1',
                      'rd.log=kmsg', 'systemd.log_level=debug', 'fz_record=full',
                      'initcall_debug', 'rd.debug',
                      'dyndbg="file drivers/usb/dwc3/* +p',
                      'panic=10', 'pstore.backend=ramoops',
                      'printk.always_kmsg_dump=1', 'efi_pstore.pstore_disable=1',
                      'fz_debug=wifi,audio', 'fz-debug on wifi'):
            self.assertIn(token, t)

    def test_docs_warn_about_the_dangerous_words(self):
        t = read(DOC)
        for token in ('ignore_loglevel', 'tp_printk', 'pci=earlydump', 'fw_devlink=permissive',
                      'pm_async=off', 'pcie_ports=native', 'dyndbg=+p',
                      '/sys/kernel/debug/regmap/*/registers', 'gpioinfo gpiochip9',
                      'kexec', 'log_buf_len'):
            self.assertIn(token, t)


class ShellSyntax(unittest.TestCase):
    def test_sh_n_for_every_script(self):
        if not POSIX:
            self.skipTest('needs POSIX sh')
        for path in (REC_ON, JOURNALD_HELPER, DEBUG, SLEEP):
            with self.subTest(script=path.name):
                r = subprocess.run([SH, '-n', str(path)], capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
