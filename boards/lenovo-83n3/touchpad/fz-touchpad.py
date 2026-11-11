#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 FroodzOS contributors
"""FroodzOS touchpad polling driver (beta).

The built-in touchpad (ACPI FTCS0038, FocalTech HID-over-I2C device 2808:0106) answers at I2C address 0x38 on the
bus of platform device 88c000.i2c, but its interrupt line is not mapped yet, so the kernel's i2c-hid driver cannot
bind it. This daemon polls the device from user space and presents it as a normal pointer device through uinput:

  * finds /dev/i2c-N for 88c000.i2c, powers the touchpad on and resets it (standard HID-over-I2C commands)
  * reads input reports with plain I2C reads; the device powers up in mouse mode, report ID 1:
        [len lo][len hi][1][buttons][dx int8][dy int8][wheel int8]
  * creates a uinput device (REL_X, REL_Y, REL_WHEEL, BTN_LEFT/RIGHT/MIDDLE) and forwards the motion

No interrupt, no kernel patch. Idle polling is slow (about 50 Hz) and speeds up while you touch the pad.
Exits quietly if the touchpad bus does not exist (for example in the menu entries that do not use the
interrupt-free device tree). Run `fz-touchpad.py --selftest` to test the uinput path without the touchpad.
"""
import fcntl, glob, os, signal, struct, sys, time

ADDR = 0x38
I2C_SLAVE = 0x0703          # normal slave select: fails with EBUSY if a kernel driver ever binds 0x38 (no silent double driver)
STALE_LIMIT = 6             # identical non-zero motion reports in a row beyond this are treated as a replayed (stale) report
DEV_NAME = 'FroodzOS I2C touchpad (polled mouse mode)'
# Descriptor fields read from the real device (probe 2026-11-10): command register 0x0005, max input length 0x20.
CMD_REG = (0x05, 0x00)
MAX_INPUT = 32
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405c5503, 0x5501, 0x5502
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
STOP = False


def log(*a):
    print('fz-touchpad:', *a, flush=True)


def s8(v):
    return v - 256 if v > 127 else v


def find_i2c_node(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline and not STOP:
        for p in sorted(glob.glob('/sys/bus/i2c/devices/i2c-*')):
            if '88c000.i2c' in os.path.realpath(p) and os.path.exists('/dev/' + os.path.basename(p)):
                return '/dev/' + os.path.basename(p)
        time.sleep(1)
    return None


def emit(fd, etype, code, value):
    os.write(fd, struct.pack('llHHi', 0, 0, etype, code, value))


def create_uinput():
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_REL)
    for b in (BTN_LEFT, BTN_RIGHT):                      # the descriptor has two button bits
        fcntl.ioctl(fd, UI_SET_KEYBIT, b)
    for r in (REL_X, REL_Y, REL_WHEEL):
        fcntl.ioctl(fd, UI_SET_RELBIT, r)
    name = DEV_NAME.encode()[:79]
    setup = struct.pack('HHHH80sI', 0x18, 0x2808, 0x0106, 1, name, 0)   # BUS_I2C, FocalTech ids, version 1
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd


class Forwarder:
    """Turns raw input reports into uinput events (also used by the self-test with synthetic reports)."""

    def __init__(self, ufd):
        self.ufd, self.buttons, self.seen_other = ufd, 0, set()
        self.last, self.same, self.warned = None, 0, False

    def idle(self):
        """Called after an empty read: a real new report may follow, so the repeat counter starts over."""
        self.last, self.same = None, 0

    def feed(self, payload):
        """payload = report bytes after the 2-byte length. Returns True if it was a mouse report."""
        if not payload:
            return False
        rid = payload[0]
        if rid != 1 or len(payload) < 5:
            if rid not in self.seen_other:
                self.seen_other.add(rid)
                log('ignoring report id %d (%d bytes): %s' % (rid, len(payload), payload[:12].hex()))
            return False
        buttons, dx, dy, wheel = payload[1] & 0x03, s8(payload[2]), s8(payload[3]), s8(payload[4])
        key = (buttons, dx, dy, wheel)
        if key == self.last and (dx or dy or wheel):
            self.same += 1
            if self.same >= STALE_LIMIT:                  # drift guard: a replayed report must not move the pointer forever
                if not self.warned:
                    self.warned = True
                    log('suppressing repeated identical motion reports (possible stale replay): %s' % payload[:8].hex())
                return True
        else:
            self.same = 0
        self.last = key
        if dx:
            emit(self.ufd, EV_REL, REL_X, dx)
        if dy:
            emit(self.ufd, EV_REL, REL_Y, dy)
        if wheel:
            emit(self.ufd, EV_REL, REL_WHEEL, wheel)
        changed = buttons ^ self.buttons
        for bit, code in ((1, BTN_LEFT), (2, BTN_RIGHT)):
            if changed & bit:
                emit(self.ufd, EV_KEY, code, 1 if buttons & bit else 0)
        self.buttons = buttons
        emit(self.ufd, EV_SYN, 0, 0)
        return True


def hid_init(i2c):
    """Standard HID-over-I2C bring-up: SET_POWER(on), RESET, then read the 2-byte reset acknowledge."""
    os.write(i2c, bytes([CMD_REG[0], CMD_REG[1], 0x00, 0x08]))
    time.sleep(0.1)
    os.write(i2c, bytes([CMD_REG[0], CMD_REG[1], 0x00, 0x01]))
    time.sleep(0.15)
    for _ in range(10):
        try:
            ack = os.read(i2c, 2)
            if len(ack) == 2 and ack == b'\x00\x00':
                return True
        except OSError:
            pass
        time.sleep(0.05)
    return False


def run_driver():
    node = find_i2c_node(60)
    if node is None:
        log('no I2C bus for 88c000.i2c (this entry does not expose the touchpad bus); nothing to do')
        return 0
    log('touchpad bus node', node)
    i2c = os.open(node, os.O_RDWR)
    try:
        fcntl.ioctl(i2c, I2C_SLAVE, ADDR)
    except OSError as e:
        log('cannot select I2C address 0x%02x (is a kernel driver bound to it?): %s' % (ADDR, e))
        return 1
    ufd = None
    for attempt in range(30):                               # /dev/uinput may appear a moment after the unit starts
        try:
            ufd = create_uinput()
            break
        except OSError as e:
            if attempt in (0, 10, 29):
                log('cannot create the uinput device yet (%s)' % e)
            time.sleep(1)
    if ufd is None:
        return 1
    reads = reports = empty = errors = consecutive = 0
    try:
        fwd = Forwarder(ufd)
        log('uinput device created:', DEV_NAME)
        try:
            ok = hid_init(i2c)
        except OSError as e:
            ok = False
            log('HID init write failed:', e)
        log('HID power-on and reset', 'acknowledged' if ok else 'sent or failed (no acknowledge read; continuing)')
        last_activity = time.time()
        last_stats = time.time()
        while not STOP:
            try:
                data = os.read(i2c, MAX_INPUT)
                consecutive = 0
                reads += 1
                L = (data[0] | (data[1] << 8)) if len(data) >= 2 else 0
                if L > 2 and L <= len(data):
                    reports += 1
                    last_activity = time.time()
                    fwd.feed(bytes(data[2:L]))
                else:
                    empty += 1
                    fwd.idle()
            except OSError as e:
                errors += 1
                consecutive += 1
                if consecutive in (1, 50, 500):
                    log('read error #%d: %s' % (errors, e))
                if consecutive >= 50:
                    time.sleep(1.0)
                    try:
                        hid_init(i2c)
                    except OSError:
                        pass
                    consecutive = 0
            idle = time.time() - last_activity
            time.sleep(0.008 if idle < 0.5 else 0.02)       # about 125 Hz while touched, 50 Hz idle
            if time.time() - last_stats > 60:
                last_stats = time.time()
                log('stats: reads=%d reports=%d empty=%d errors=%d' % (reads, reports, empty, errors))
    finally:
        try:
            fcntl.ioctl(ufd, UI_DEV_DESTROY)
        except OSError:
            pass
        log('stopped: reads=%d reports=%d empty=%d errors=%d' % (reads, reports, empty, errors))
    return 0


def selftest():
    """Create the uinput device, inject synthetic reports and read the events back from the evdev node."""
    ufd = create_uinput()
    node = None
    for _ in range(40):
        txt = open('/proc/bus/input/devices').read()
        for block in txt.split('\n\n'):
            if DEV_NAME in block:
                for tok in block.split():
                    if tok.startswith('event'):
                        node = '/dev/input/' + tok
        if node and os.path.exists(node):
            break
        time.sleep(0.1)
    if not node:
        log('SELFTEST FAIL: evdev node not found')
        return 1
    rd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
    fwd = Forwarder(ufd)
    fwd.feed(bytes([1, 0x01, 5, 0xFD, 0x00]))    # left button down, dx=+5, dy=-3
    fwd.feed(bytes([1, 0x00, 0, 0, 0xFF]))       # button up, wheel -1
    fwd.idle()
    for _ in range(10):                          # stale-replay guard: 10 identical reports -> only STALE_LIMIT are forwarded
        fwd.feed(bytes([1, 0x00, 2, 0, 0x00]))
    time.sleep(0.2)
    got = []
    while True:
        try:
            raw = os.read(rd, 24 * 32)
        except BlockingIOError:
            break
        for i in range(0, len(raw) - 23, 24):
            _, _, t, c, v = struct.unpack('llHHi', raw[i:i + 24])
            if t != EV_SYN or c != 0:
                got.append((t, c, v))
    # motion is emitted before button changes within one report: report 2 gives the wheel first, then the button release
    want = [(EV_REL, REL_X, 5), (EV_REL, REL_Y, -3), (EV_KEY, BTN_LEFT, 1), (EV_REL, REL_WHEEL, -1), (EV_KEY, BTN_LEFT, 0)] + \
           [(EV_REL, REL_X, 2)] * STALE_LIMIT
    fcntl.ioctl(ufd, UI_DEV_DESTROY)
    log('SELFTEST', 'PASS' if got == want else 'FAIL', 'events:', got)
    return 0 if got == want else 1


def on_term(sig, frm):
    global STOP
    STOP = True


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        sys.exit(selftest() if '--selftest' in sys.argv else run_driver())
    except Exception as e:
        log('fatal:', repr(e))
        sys.exit(1)
