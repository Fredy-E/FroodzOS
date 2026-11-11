# Touchpad polling driver (Lenovo 83N3)

`fz-touchpad.py` reads the FocalTech HID-over-I2C touchpad at address 0x38 by polling (the interrupt line is not known)
and presents it as a pointer through uinput. `fz-touchpad.service` starts it when the kernel command line has
`fz_touchpad=1`. Python 3, root and `/dev/i2c-*` plus `/dev/uinput` are required; it exits quietly on machines without the bus.
`python3 fz-touchpad.py --selftest` checks the uinput path without hardware (Linux only).

Status, evidence and limits: [docs/touchpad.md](../../../docs/touchpad.md). Licence: GPL-2.0-or-later.
