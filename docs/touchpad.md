# Built-in touchpad on the Lenovo IdeaPad Slim 3 15Q8X10 (83N3)

Status (2026-11-11): **works in basic mouse mode** in the private `0.1.0-dev` Maverick development candidate, owner-tested
on the laptop. Tap-to-click, gestures and natural scrolling are not available yet.

## What was wrong

- The touchpad is an ACPI device `FTCS0038`: a FocalTech HID-over-I2C device (USB-style IDs 2808:0106) at I2C address `0x38`
  on the bus of platform device `88c000.i2c`.
- The upstream-derived device tree instantiates a different touchpad (`GXTP5100` at `0x5d`) with no interrupt. The kernel
  `i2c_hid_of` driver therefore failed with `-22`, and the real device at `0x38` was never probed.
- The bus itself only probed after removing two interconnect properties from the `i2c@88c000` node (a diagnostic device
  tree, kept out of the default tree). The touchpad's interrupt line could not be identified: ACPI pin 960 is not a
  Linux TLMM GPIO number, and a GPIO-level sweep found no candidate.

## What works now

A small user-space daemon, [`boards/lenovo-83n3/touchpad/fz-touchpad.py`](../boards/lenovo-83n3/touchpad/fz-touchpad.py),
polls the device over `/dev/i2c-N` (no interrupt needed), sends the standard HID-over-I2C power-on and reset commands,
reads input reports (report id 1: buttons, dx, dy, wheel) and re-emits them through `uinput` as a normal pointer.
Idle polling is about 50 Hz and rises to about 125 Hz while touched. A drift guard drops long runs of identical motion
reports. `fz-touchpad.py --selftest` checks the uinput path without hardware.

It is started by [`fz-touchpad.service`](../boards/lenovo-83n3/touchpad/fz-touchpad.service) when the kernel command line
carries `fz_touchpad=1`, and exits quietly when the touchpad bus does not exist.

## Evidence

- Probe on 2026-11-10: valid HID descriptor, 556-byte report descriptor, reset acknowledged, 1,610 mouse-mode reports in
  20 s, 0 errors.
- Owner tests on 2026-11-11 (two boots): pointer works; logs show `errors=0` over the whole boot.
- Limits: basic mouse mode only; one laptop; the interrupt pin is still unknown.

## Next

Precision Touchpad mode (multitouch, tap, gestures) would need the device switched out of mouse mode and a HID multitouch
path through `uhid`. A proper kernel fix needs the interrupt line identified and a correct device tree node.
