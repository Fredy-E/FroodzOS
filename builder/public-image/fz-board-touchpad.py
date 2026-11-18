#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""FroodzOS board fix for the Lenovo IdeaPad Slim 3 15Q8X10 (83N3): make the touchpad a native HID-over-I2C device.

The board DTS declares a Goodix GXTP5100 at I2C address 0x5d without an interrupt, so the kernel driver fails with "HID over i2c has
not been provided an Int IRQ". The unit's real touchpad is a FocalTech FTCS0038 at 0x38 (ACPI \\_SB.TCPD, TPTY low byte 0x05; the
2026-11-10 probe read its HID descriptor at 0x38), and its interrupt line is TLMM GPIO 19 (level, active low: measured with
find-touchpad-irq.py on 2026-11-16, 344 and 349 level changes while touching and none idle; ACPI GpioInt flags 0x12).

    fz-board-touchpad.py <in.dtb> <out.dtb> [--addr 0x38] [--gpio 19] [--dry-run]

Works on the compiled .dtb with dtc/fdtget/fdtput; the input is never modified. It only acts on a node that is `hid-over-i2c` under
the I2C controller 88c000, has no interrupt, and sits at an address other than --addr.
"""
import re, shutil, subprocess, sys
from pathlib import Path

I2C = '/soc@0/geniqup@8c0000/i2c@88c000'
TLMM = '/soc@0/pinctrl@f100000'


def get(dtb, node, prop, typ=None):
    cmd = ['fdtget'] + (['-t', typ] if typ else []) + [str(dtb), node, prop]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def put(dtb, node, prop, typ, *vals):
    subprocess.run(['fdtput', '-t', typ, str(dtb), node, prop] + [str(v) for v in vals], check=True)


def main(argv):
    flags = {a for a in argv if a.startswith('--') and '=' not in a}
    opts = {}
    it = iter([a for a in argv if not a.startswith('--') or a in ('--addr', '--gpio')])
    pos = []
    for a in it:
        if a in ('--addr', '--gpio'): opts[a] = next(it)
        else: pos.append(a)
    if len(pos) != 2: print(__doc__); return 2
    src, out = Path(pos[0]), Path(pos[1])
    addr, gpio = int(opts.get('--addr', '0x38'), 0), int(opts.get('--gpio', '19'), 0)
    dts = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', str(src)], capture_output=True, text=True, check=True).stdout
    node = None
    sub =subprocess.run(['fdtget', '-l', str(src), I2C], capture_output=True, text=True)
    for child in sub.stdout.split():
        p = '%s/%s' % (I2C, child)
        if get(src, p, 'compatible') == 'hid-over-i2c' and get(src, p, 'interrupts-extended') is None and get(src, p, 'interrupts') is None:
            reg = int(get(src, p, 'reg', 'x') or '0', 16)
            if reg != addr: node = p; oldreg = reg; break
    if node is None: print('fz-board-touchpad: nothing to change (no interrupt-less hid-over-i2c node under %s at another address)' % I2C); shutil.copyfile(src, out); return 0
    tlmm = int(get(src, TLMM, 'phandle', 'i'))
    used = [int(x, 16) for x in re.findall(r'phandle = <(0x[0-9a-fA-F]+)>', dts)]
    ph = max(used) + 1
    print('fz-board-touchpad: %s reg 0x%x -> 0x%x, interrupt TLMM gpio%d level-low, pin state phandle 0x%x' % (node, oldreg, addr, gpio, ph))
    if '--dry-run' in flags: return 0
    shutil.copyfile(src, out)
    st = '%s/tp-int-default-state' % TLMM
    subprocess.run(['fdtput', '-c', str(out), st], check=True)
    put(out, st, 'pins', 's', 'gpio%d' % gpio)
    put(out, st, 'function', 's', 'gpio')
    subprocess.run(['fdtput', str(out), st, 'bias-pull-up'], check=True)      # boolean property: no value
    put(out, st, 'drive-strength', 'i', 2)
    subprocess.run(['fdtput', str(out), st, 'input-enable'], check=True)
    put(out, st, 'phandle', 'i', ph)
    put(out, node, 'reg', 'i', addr)
    put(out, node, 'interrupts-extended', 'i', tlmm, gpio, 8)       # 8 = IRQ_TYPE_LEVEL_LOW
    put(out, node, 'pinctrl-0', 'i', ph)
    put(out, node, 'pinctrl-names', 's', 'default')
    print('fz-board-touchpad: done')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
