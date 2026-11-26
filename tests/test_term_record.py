#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""fz-term-record: renderer, redaction, caps and the no-op/recursion guards of the terminal session recorder."""
import base64
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:
    import pty
    HAVE_PTY = True
except ImportError:
    pty = None
    HAVE_PTY = False

ROOT = Path(__file__).resolve().parents[1]
OVL = ROOT / 'builder/public-image/rootfs-overlay'
WRAPPER = OVL / 'usr/local/sbin/fz-term-record'
LIB = OVL / 'usr/local/lib/fz-term-record'
RENDER = LIB / 'render.py'
REDACT = LIB / 'fz_term_redact.py'
HOOK = OVL / 'etc/fz-term-record.bash'
PROFILE_D = OVL / 'etc/profile.d/99-fz-term-record.sh'
KONSOLE = OVL / 'usr/share/konsole/FroodzOS.profile'
KONSOLERC = OVL / 'etc/xdg/konsolerc'
TMPFILES = OVL / 'etc/tmpfiles.d/fz-term-record.conf'
FIX = ROOT / 'tests/fixtures/terminal'
POSIX = sys.platform != 'win32' and shutil.which('bash') and shutil.which('sh')
SCRIPT = shutil.which('script')
SECRETS = [
    'ghp_' + 'A' * 36,
    'abcdefghijklmnopqrstuvwxyz0123456789',
    'correct horse battery staple',
    'FAKE-PASSPHRASE-01',
    'FAKE-PASSWORD-01',
    'FAKEKEYMATERIAL',
]


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith('FZ_')}
    env.pop('PYTHONPATH', None)
    env.update(extra)
    return env


class Renderer(unittest.TestCase):
    def session(self, fixture, meta=None, commands=True):
        tmp = Path(tempfile.mkdtemp(prefix='fz-term-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        s = tmp / 'session'
        s.mkdir()
        (s / 'session.raw').write_bytes(base64.b64decode((FIX / (fixture + '.raw.b64')).read_text().strip()))
        if commands:
            shutil.copyfile(FIX / (fixture + '.commands.tsv'), s / 'commands.raw.tsv')
        data = {'session': 'test-' + fixture, 'user': 'live', 'uid': '1000', 'tty': '/dev/pts/9',
                'term': 'xterm-256color', 'shell': '/bin/bash', 'boot_id': 'fake-boot',
                'start_utc': '2026-11-25T10:00:00Z', 'mode': 'interactive'}
        data.update(meta or {})
        (s / 'meta').write_text(''.join('%s=%s\n' % kv for kv in data.items()), encoding='utf-8')
        return s, tmp

    def render(self, s, **env):
        logdir = Path(tempfile.mkdtemp(prefix='fz-log-'))
        self.addCleanup(shutil.rmtree, logdir, True)
        e = clean_env(FZ_LOG_DIR=str(logdir), **env)
        p = subprocess.run([sys.executable, '-B', str(RENDER), str(s)], capture_output=True, text=True, env=e)
        return p, logdir

    def records(self, logdir):
        files = sorted(logdir.rglob('*.jsonl'))
        self.assertTrue(files, 'no JSONL emitted')
        out = []
        for f in files:
            for line in f.read_text(encoding='utf-8').splitlines():
                obj = json.loads(line)
                if 'cmd' in obj and '_fz' not in obj:
                    out.append(obj)
        return out

    def test_ansi_cr_progress_utf8_and_records(self):
        s, _ = self.session('basic')
        p, logdir = self.render(s)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        text = (s / 'transcript-test-basic.txt').read_text(encoding='utf-8')
        self.assertNotIn('\x1b', text)
        for want in ('echo hi', 'hi', 'red', 'seq progress', '100%'):
            self.assertIn(want, text)
        self.assertNotIn('20%', text)
        recs = self.records(logdir)
        self.assertEqual([r['cmd'] for r in recs], ['echo hi', "printf '\\033[31mred\\033[0m\\n'", 'seq progress'])
        self.assertTrue(all(r['exit'] == 0 for r in recs))
        self.assertTrue(all(r['session'] == 'test-basic' and r['tty'] == '/dev/pts/9' for r in recs))
        self.assertTrue(recs[0]['out_head'].startswith('FroodzOS test shell'))
        self.assertGreater(recs[0]['out_bytes'], 0)
        self.assertGreater(recs[0]['out_lines'], 0)
        self.assertTrue(recs[0]['ts'].endswith('Z') and isinstance(recs[0]['mono'], (int, float)))
        self.assertTrue((s / 'commands.tsv').exists())
        self.assertFalse((s / 'session.raw').exists())

    def test_synthetic_secrets_are_redacted_everywhere(self):
        s, _ = self.session('secrets')
        p, logdir = self.render(s)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        text = (s / 'transcript-test-secrets.txt').read_text(encoding='utf-8')
        self.assertIn('<redacted:', text)
        for secret in SECRETS:
            self.assertNotIn(secret, text)
        self.assertNotIn('alice:secret', text)
        raw_jsonl = '\n'.join(f.read_text(encoding='utf-8') for f in sorted(logdir.rglob('*.jsonl')))
        for secret in SECRETS:
            self.assertNotIn(secret, raw_jsonl)
        self.assertNotIn('alice:secret', raw_jsonl)

    def test_echo_off_password_prompt_keeps_prompt_and_next_command(self):
        s, _ = self.session('noecho')
        p, logdir = self.render(s)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        text = (s / 'transcript-test-noecho.txt').read_text(encoding='utf-8')
        self.assertIn('[sudo] password for live:', text)
        self.assertIn('echo ok', text)
        self.assertIn('yes', text)
        self.assertNotIn('typed-secret', text)
        self.assertEqual([r['cmd'] for r in self.records(logdir)], ['sudo -v', 'echo ok'])

    def test_transcript_cap_truncates_at_a_line_but_keeps_records(self):
        s, _ = self.session('basic')
        (s / 'session.raw').write_bytes((b'$ big\n' + (b'x' * 100 + b'\n') * 200 +
                                         b'\x1b]6973;FZ;E;1;0;100.500\x07'))
        (s / 'commands.raw.tsv').write_text('1\t100.100\t100.500\t0\t/home/live\tbig\n', encoding='utf-8')
        p, logdir = self.render(s, FZ_TERM_TEXT_BYTES='2000')
        self.assertEqual(p.returncode, 1, p.stderr)
        blob = (s / 'transcript-test-basic.txt').read_bytes()
        self.assertLessEqual(len(blob), 2200)
        self.assertIn(b'[truncated]', blob)
        self.assertEqual(len(self.records(logdir)), 1)

    def test_utf8_is_preserved(self):
        s, _ = self.session('basic')
        (s / 'session.raw').write_bytes('$ echo café\r\ncafé ✓ 日本語\r\n'.encode('utf-8') +
                                         b'\x1b]6973;FZ;E;1;0;100.500\x07')
        (s / 'commands.raw.tsv').write_text('1\t100.100\t100.500\t0\t/home/live\techo café\n', encoding='utf-8')
        p, _ = self.render(s)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        text = (s / 'transcript-test-basic.txt').read_text(encoding='utf-8')
        self.assertIn('café ✓ 日本語', text)

    def test_binary_junk_does_not_crash(self):
        s, _ = self.session('basic')
        (s / 'session.raw').write_bytes(b'$ echo hi\r\nhi \xff\xfe\x00 there\r\n\x1b]6973;FZ;E;1;2;100.500\x07')
        (s / 'commands.raw.tsv').write_text('1\t100.100\t100.500\t2\t/home/live\techo hi\n', encoding='utf-8')
        p, logdir = self.render(s)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        text = (s / 'transcript-test-basic.txt').read_text(encoding='utf-8')
        self.assertIn('hi', text)
        self.assertEqual(self.records(logdir)[0]['exit'], 2)

    def test_bundled_redactor_is_idempotent(self):
        sys.path.insert(0, str(LIB))
        try:
            import fz_term_redact
        finally:
            sys.path.remove(str(LIB))
        once = fz_term_redact.redact('password=FAKE-PASSWORD-01\n')
        twice = fz_term_redact.redact(once)
        self.assertNotIn('FAKE-PASSWORD-01', once)
        self.assertEqual(once, twice)

    def test_assets_are_output_only_and_wired(self):
        w = WRAPPER.read_text(encoding='utf-8')
        self.assertNotIn('\r', w)
        self.assertIn('--log-out', w)
        self.assertIn('--log-timing', w)
        self.assertIn('--output-limit', w)
        self.assertNotIn('--log-in', w)
        self.assertNotIn('--log-io', w)
        self.assertIn('exec "$REAL"', w)
        self.assertIn('FZ_TERM_ACTIVE=1', w)
        for path in (WRAPPER, RENDER, REDACT, HOOK, PROFILE_D):
            self.assertIn('SPDX-License-Identifier: GPL-2.0-or-later', path.read_text(encoding='utf-8'))
        profile = KONSOLE.read_text(encoding='utf-8')
        self.assertIn('Command=/usr/local/sbin/fz-term-record interactive', profile)
        self.assertIn('HistoryMode=2', profile)
        self.assertIn('HistorySize=100000', profile)
        self.assertIn('DefaultProfile=FroodzOS.profile', KONSOLERC.read_text(encoding='utf-8'))
        self.assertIn('d /run/fz-term 0770 root live -', TMPFILES.read_text(encoding='utf-8'))


class ShellParts(unittest.TestCase):
    def test_shell_syntax(self):
        if not POSIX:
            self.skipTest('POSIX shell not available')
        self.assertEqual(subprocess.run(['sh', '-n', str(WRAPPER)]).returncode, 0)
        self.assertEqual(subprocess.run(['sh', '-n', str(PROFILE_D)]).returncode, 0)
        self.assertEqual(subprocess.run(['bash', '-n', str(HOOK)]).returncode, 0)

    def test_hook_installs_the_sidecar_without_reexec(self):
        if not POSIX:
            self.skipTest('bash not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-hook-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        fake_proc = tmp / 'proc' / str(os.getpid())
        fake_proc.mkdir(parents=True)
        (fake_proc / 'comm').write_text('script\n', encoding='utf-8')
        cmd = ('FZ_TERM_ACTIVE=1 FZ_TERM_PROC=%s FZ_TERM_DIR=%s FZ_TERM_CMDS=%s FZ_TERM_RECORD=/bin/false; '
               'PROMPT_COMMAND="printf old"; . %s; '
               'case "$PROMPT_COMMAND" in *fz_term_log_cmd*) echo hooked;; esac; '
               'case "$PROMPT_COMMAND" in *"printf old"*) echo kept;; esac; '
               'case "$PS0" in *FZ_TERM_T0*) echo ps0;; esac') % (
                   tmp / 'proc', tmp, tmp / 'commands.raw.tsv', HOOK)
        p = subprocess.run(['bash', '--noprofile', '--norc', '-i', '-c', cmd], capture_output=True, text=True,
                           env=clean_env(), stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stderr)
        for want in ('hooked', 'kept', 'ps0'):
            self.assertIn(want, p.stdout)


class Wrapper(unittest.TestCase):
    def wrapper_env(self, tmp, cmdline='quiet fz_record=full', **extra):
        cmd = tmp / 'cmdline'
        cmd.write_text(cmdline + '\n', encoding='utf-8')
        env = clean_env(FZ_CMDLINE=str(cmd), FZ_RECORD_ON=str(tmp / 'missing-record-on'),
                        FZ_TERM_BASE=str(tmp / 'spool'), FZ_REAL_SHELL='/bin/true',
                        FZ_TERM_RENDER=str(RENDER), FZ_LOG_DIR=str(tmp / 'logs'),
                        HOME=str(tmp / 'home'))
        env.update(extra)
        return env

    def sessions(self, tmp):
        return [p for p in (tmp / 'spool').rglob('*/session.raw')] if (tmp / 'spool').exists() else []

    def test_shell_syntax(self):
        if not POSIX:
            self.skipTest('POSIX shell not available')
        self.assertEqual(subprocess.run(['sh', '-n', str(WRAPPER)]).returncode, 0)

    def test_off_is_a_noop(self):
        if not (POSIX and SCRIPT):
            self.skipTest('pty/script not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-off-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / 'home').mkdir()
        env = self.wrapper_env(tmp, cmdline='quiet')
        p = subprocess.run([SCRIPT, '-q', '-e', '-c', 'sh %s interactive' % WRAPPER, '/dev/null'],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.sessions(tmp), [])

    def test_environment_guard_fails_open(self):
        if not (POSIX and SCRIPT):
            self.skipTest('pty/script not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-env-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        env = self.wrapper_env(tmp, FZ_TERM_ACTIVE='1')
        p = subprocess.run([SCRIPT, '-q', '-e', '-c', 'sh %s interactive' % WRAPPER, '/dev/null'],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.sessions(tmp), [])

    def test_boot_cap_fails_open(self):
        if not (POSIX and SCRIPT):
            self.skipTest('pty/script not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-cap-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / 'spool').mkdir()
        (tmp / 'spool' / 'fill.bin').write_bytes(b'x' * (1024 * 1024))
        env = self.wrapper_env(tmp, FZ_TERM_BOOT_KB='1')
        p = subprocess.run([SCRIPT, '-q', '-e', '-c', 'sh %s interactive' % WRAPPER, '/dev/null'],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.sessions(tmp), [])

    def test_recursion_guard_sees_the_outer_script(self):
        if not (POSIX and SCRIPT):
            self.skipTest('pty/script not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-rec-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        env = self.wrapper_env(tmp)
        p = subprocess.run([SCRIPT, '-q', '-e', '-c', 'sh %s interactive' % WRAPPER, '/dev/null'],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.sessions(tmp), [])


class LogEnvLoading(unittest.TestCase):
    """A user shell has no FZ_LOG_DIR; the renderer must adopt /run/fz-smartlog/env so the terminal stream lands in the boot folder."""

    def run_loader(self, env_text, extra_env):
        tmp = Path(tempfile.mkdtemp(prefix='fz-env-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        envfile = tmp / 'env'
        envfile.write_text(env_text, encoding='utf-8')
        code = ('import sys, os; sys.path.insert(0, %r); import render; render.load_log_env(); '
                'print(os.environ.get("FZ_LOG_DIR", "")); print(os.environ.get("FZ_LOG_PRIVACY", ""))' % str(LIB))
        env = clean_env(FZ_RENDER_ENV_FILE=str(envfile), **extra_env)
        out = subprocess.run([sys.executable, '-B', '-c', code], env=env, capture_output=True, text=True, check=True)
        return out.stdout.splitlines()

    def test_loads_quoted_values_from_the_env_file(self):
        text = "\n".join(["FZ_LOG_DIR='/run/x/streams'", "FZ_LOG_PRIVACY='owner'", "OTHER='no'", ""])
        got = self.run_loader(text, {})
        self.assertEqual(got, ['/run/x/streams', 'owner'])

    def test_an_inherited_value_wins(self):
        got = self.run_loader("FZ_LOG_DIR='/run/x/streams'\n", {'FZ_LOG_DIR': '/inherited'})
        self.assertEqual(got[0], '/inherited')


class EndToEnd(unittest.TestCase):
    def test_pty_records_command_exit_and_output(self):
        if not POSIX:
            self.skipTest('pty not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-e2e-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        home = tmp / 'home'
        home.mkdir()
        (home / '.bashrc').write_text('. "%s"\nPS1="fz$ "\n' % HOOK, encoding='utf-8')
        cmdline = tmp / 'cmdline'
        cmdline.write_text('quiet fz_record=full\n', encoding='utf-8')
        env = clean_env(FZ_CMDLINE=str(cmdline), FZ_RECORD_ON=str(tmp / 'missing-record-on'),
                        FZ_TERM_BASE=str(tmp / 'spool'), FZ_REAL_SHELL='/bin/bash',
                        FZ_TERM_RENDER=str(RENDER), FZ_LOG_DIR=str(tmp / 'logs'),
                        HOME=str(home), TERM='xterm', PS1='fz$ ')
        master, slave = pty.openpty()
        proc = subprocess.Popen(['sh', str(WRAPPER), 'interactive'], stdin=slave, stdout=slave, stderr=slave,
                                env=env, close_fds=True)
        os.close(slave)
        out = b''
        sent = False
        deadline = time.time() + 25
        try:
            while time.time() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    out += chunk
                    if not sent and b'fz$' in out:
                        os.write(master, b'echo hi; exit 3\n')
                        sent = True
                elif proc.poll() is not None:
                    break
            if not sent:
                os.write(master, b'echo hi; exit 3\n')
            proc.wait(timeout=15)
        finally:
            os.close(master)
        self.assertEqual(proc.returncode, 3, out.decode('utf-8', 'replace'))
        files = sorted((tmp / 'logs').rglob('*.jsonl'))
        self.assertTrue(files, 'no JSONL records written')
        records = []
        for f in files:
            records += [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines()]
        cmds = [r for r in records if r.get('cmd')]
        self.assertTrue(cmds, records)
        self.assertTrue(any('echo hi' in r['cmd'] and r['exit'] == 3 and 'hi' in r['out_head'] for r in cmds), cmds)
        transcript = next((tmp / 'spool').rglob('transcript-*.txt'))
        body = transcript.read_text(encoding='utf-8')
        self.assertIn('echo hi', body)
        self.assertIn('hi', body)

    def test_nested_bash_does_not_start_a_second_sidecar(self):
        if not POSIX:
            self.skipTest('pty not available')
        tmp = Path(tempfile.mkdtemp(prefix='fz-nest-'))
        self.addCleanup(shutil.rmtree, tmp, True)
        home = tmp / 'home'
        home.mkdir()
        (home / '.bashrc').write_text('. "%s"\nPS1="fz$ "\n' % HOOK, encoding='utf-8')
        cmdline = tmp / 'cmdline'
        cmdline.write_text('quiet fz_record=full\n', encoding='utf-8')
        env = clean_env(FZ_CMDLINE=str(cmdline), FZ_RECORD_ON=str(tmp / 'missing-record-on'),
                        FZ_TERM_BASE=str(tmp / 'spool'), FZ_REAL_SHELL='/bin/bash',
                        FZ_TERM_RENDER=str(RENDER), FZ_LOG_DIR=str(tmp / 'logs'),
                        HOME=str(home), TERM='xterm', PS1='fz$ ')
        master, slave = pty.openpty()
        proc = subprocess.Popen(['sh', str(WRAPPER), 'interactive'], stdin=slave, stdout=slave, stderr=slave,
                                env=env, close_fds=True)
        os.close(slave)
        out = b''
        sent = False
        deadline = time.time() + 25
        try:
            while time.time() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    out += chunk
                    if not sent and b'fz$' in out:
                        os.write(master, b'echo one\nbash\necho two\nexit\necho three\nexit 4\n')
                        sent = True
                elif proc.poll() is not None:
                    break
            proc.wait(timeout=15)
        finally:
            os.close(master)
        self.assertEqual(proc.returncode, 4, out.decode('utf-8', 'replace'))
        self.assertEqual(len(list((tmp / 'spool').rglob('meta'))), 1)
        records = []
        for f in sorted((tmp / 'logs').rglob('*.jsonl')):
            records += [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines()]
        cmds = [r for r in records if r.get('cmd')]
        seqs = [r['seq'] for r in cmds]
        self.assertEqual(len(seqs), len(set(seqs)))
        self.assertTrue(any('echo one' in r['cmd'] for r in cmds), cmds)
        self.assertTrue(any('echo three' in r['cmd'] for r in cmds), cmds)
        self.assertFalse(any('echo two' in r['cmd'] for r in cmds), cmds)
        body = next((tmp / 'spool').rglob('transcript-*.txt')).read_text(encoding='utf-8')
        self.assertIn('echo two', body)


if __name__ == '__main__':
    unittest.main()
