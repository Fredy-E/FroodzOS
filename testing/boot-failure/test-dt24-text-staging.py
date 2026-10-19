#!/usr/bin/env python3
"""Exercise the packed hook in disposable chroots; never mount/write real roots."""
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
T = P / 'testing/boot-failure'
image = Path('/home/builder/uki-v2-dt24/live-initramfs.img')
results = []
for flag, console, expected in [('0', 'tty1', None), ('1', 'tty1', 'getty@tty1.service'),
                                ('1', 'ttyAMA0', 'serial-getty@ttyAMA0.service'), ('1', '../../evil', None)]:
    with tempfile.TemporaryDirectory(prefix='dt24-hook-', dir='/home/builder/boot-failure-tests') as temp:
        root = Path(temp)
        subprocess.run(['lsinitcpio', '-x', str(image)], cwd=root, check=True, capture_output=True)
        fake = root / 'sysroot'
        units = fake / 'etc/systemd/system'
        vendor = fake / 'usr/lib/systemd/system'
        units.mkdir(parents=True)
        vendor.mkdir(parents=True)
        for name in ['getty@.service', 'serial-getty@.service', 'sshd.service', 'sddm.service']:
            (vendor / name).touch()
        # Explicit unit-test mocks: no real mount and no kernel cmdline access.
        script = '''#!/usr/bin/ash
getarg() {
    case "$1" in
        kestrel_textboot) printf '%s\\n' FLAG ;;
        kestrel_console) printf '%s\\n' CONSOLE ;;
    esac
}
mountpoint() { return 0; }
. /hooks/kestrel_text
run_latehook
'''.replace('FLAG', shlex.quote(flag)).replace('CONSOLE', shlex.quote(console))
        (root / 'hook-test.sh').write_text(script)
        run = subprocess.run(['chroot', str(root), '/usr/bin/ash', '/hook-test.sh'], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        if expected:
            assert (units / (expected + '.d/90-kestrel-live.conf')).read_bytes() == (P / 'builder/diagnostics/kestrel-text-getty.conf').read_bytes()
            assert (units / ('getty.target.wants/' + expected)).is_symlink()
            assert (units / 'default.target').readlink() == Path('/usr/lib/systemd/system/multi-user.target')
            assert (units / 'sshd.service').readlink() == Path('/dev/null')
            assert (units / 'sddm.service').readlink() == Path('/dev/null')
            assert (fake / 'usr/local/sbin/kestrel-text-login').read_bytes() == (P / 'builder/diagnostics/kestrel-text-login.sh').read_bytes()
        else:
            assert not (fake / 'usr/local').exists()
            assert not (units / 'default.target').exists()
        results.append({'flag': flag, 'console': console, 'expected_unit': expected, 'passed': True})
report = {'passed': True, 'cases': results, 'fixture_only': True, 'real_mounts_performed': False,
          'native_hardware_validated': False}
with (T / 'dt24-text-hook-unit-result.json').open('x') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
