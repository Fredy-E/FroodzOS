# dt23: post-switch proof (writable userspace + keyboard LEDs + fstype)

## What dt22 native proved

Both dt22 boots (#8 = 512cba9d, #9 = c246283a — firmware kept the first
boot's records while the second disarmed and preserved them) reached the
same new state:

- Preswitch log: `root_dev_mounted=yes`, `/sysroot/usr/bin/bash` and
  `/sysroot/usr/local/sbin/kestrel-pid1` both present and executable,
  correct overlay mounts.
- Native kmsg: `KESTREL_PID1_ENTER` @~14.5s, `KESTREL_PID1_EXEC_BASH` @~14.75s.
  **switch_root works natively and the wrapper reaches its pre-exec marker.**
  This marker is printed before `exec`; successful Bash execution and startup
  are not verified by it. The previous claim that Bash was proven exec'd was
  incorrect.
- After the pre-exec marker: kernel continues to ~20.6s `sync_state pending`, then quiet.
  No Bash output, no panic. The remaining question is purely post-switch:
  is Bash alive but silent (display/input), or dying silently?

Archives: `native-dt22-512cba9d-.../`, `native-dt22-c246283a-.../`
(identical preswitch/kmsg shape; c246 archive records firmware disarm
preserving the first boot's IDs).

## dt23 delta (PID1 wrapper only; kernel/DT/stub/menu-shape unchanged)

After the pre-switch markers, the wrapper now:

1. Prints `KESTREL_POSTSWITCH_ALIVE`, `FSTYPE: $(findmnt -n -o FSTYPE /)`
   and `PID1: $(cat /proc/1/comm)` to console + kmsg.
2. Writes `04-postswitch-alive.txt` into the current boot's own USB log dir
   (`boot-$(cat /proc/sys/kernel/random/boot_id)/`). This survives a frozen
   display and a dead keyboard — it is readable back in Windows.
3. Blinks every `*::capslock/*::numlock/*::scrolllock` LED twice, with
   `KESTREL_LED_FOUND` per LED and START/DONE markers. The owner watches the
   physical keyboard, not the screen. Observed blinking confirms the LED output
   path for that identified device, not working key input or an interactive shell.
4. Execs `bash -i` on `/dev/console` as before.

## QEMU proof (fixed candidate 03ad7ddab04c)

- Shell: PASS, 88s. Serial shows POSTSWITCH_ALIVE, `FSTYPE: overlay`,
  PID1 `kestrel-pid1`, FILE_WRITTEN, LED START/DONE (no LEDs on QEMU;
  block completes trivially), EXEC_BASH, prompt, modules, poweroff.
  `04-postswitch-alive.txt` (22 B) captured off the virtual USB.
- Systemd: PASS, multi-user, journal read back.
- Logger: PASS, zero physical firmware writes.
- Audit: kernel/DT/stub/cmdline byte-identical to dt22; only the wrapper
  file changed; hooks and all other initramfs files identical; 5 module deps
  resolve.

## Installed state

- Physical USB holds dt23 (UKI 244486656 B `03ad7ddab04c...`, menu 6223 B
  `c9eeef91...`), independently verified; dt22 rollback in
  `usb-before-dt23-*/`.
- Stuck-boot firmware `512cba9d-...` preserved in
  `firmware-clear-20261017T121513710Z/`; all four slots rearmed empty and
  verified (`dt23-preboot-20261017T121526173Z/`).
- Two prior USB log dirs retained; the next boot creates a fresh
  `E:/Logs/boot-<new-id>/` containing `03-preswitch.log` and, if userspace
  lives, `04-postswitch-alive.txt`.

## What the next native boot must show (in order)

1. Screen: `KESTREL_PID1_STAGED`, `KESTREL_PRESWITCH_RECORDED`, `ENTER`.
2. `04-postswitch-alive.txt` with `KESTREL_POSTSWITCH_OK` in the new USB
   log dir — proves writable live userspace regardless of screen/keyboard.
3. Keyboard LEDs blinking twice — confirms only the identified LED output path.
4. A visible, responsive Bash prompt and actual key input still need separate
   verification. A written alive file plus blinking LEDs does not isolate a
   display-only fault.

## Classification correction

dt23 is a diagnostic boot test, not a repair of the remaining console/input
problem. It adds evidence before attempting the same Bash handoff; it does not
advance the selected entry into systemd or Plasma. Earlier wording calling this
a fix or claiming the three checks locate the fault exactly was too strong.
