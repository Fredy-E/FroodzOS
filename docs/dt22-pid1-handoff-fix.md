# dt22: PID1-marked live shell (diagnose the silent switch_root handoff)

## Why dt22 exists

Two native dt21 boots (5fe82fa8, 9b11354b) both reached the same point and
stopped with no error:

- USB enumerates (Kingston sda, camera, 2.4G receiver), label mounts,
  squashfs mounts, `KESTREL_OVERLAY_ROOT_READY`, `KESTREL_SWITCH_ROOT_PENDING`.
- Kernel log ends at `sync_state() pending` (~20.6s). No panic, no emergency
  shell, no Bash prompt, no post-switch output of any kind.

`switch_root` either never execs the new init or the new init dies silently:
the old `init=/usr/bin/bash` leaves zero trace either way, so the fault
cannot be located from dt21 evidence. dt22 adds markers on both sides of
the handoff instead of changing any hardware path.

## Delta (initramfs + menu only; kernel/DT/stub/cmdline base unchanged)

- New `builder/diagnostics/kestrel-pid1.sh` (`/bin/sh`, NOT `/usr/bin/ash`):
  prints `KESTREL_PID1_ENTER`, the cmdline, `ls -l /usr/bin/bash` and
  `KESTREL_PID1_EXEC_BASH` to both `/dev/console` and `/dev/kmsg`, then
  execs `/usr/bin/bash -i` with stdio on `/dev/console`.
- `install/kestrel_log` ships it as `/usr/bin/kestrel-pid1` (mode 755).
- `run_latehook` stages it into the live overlay at
  `/sysroot/usr/local/sbin/kestrel-pid1` (upperdir write, works with
  `init=` bypassing systemd) and prints `KESTREL_PID1_STAGED`.
- `run_cleanuphook` writes `03-preswitch.log` to the USB log dir before the
  handoff: cmdline, `/sysroot` mount state, `ls -l` of both the target Bash
  and the staged wrapper, archiso/overlay mounts, `KESTREL_PRESWITCH_RECORDED`.
- Menu #8/#9 `init=` changed to `/usr/local/sbin/kestrel-pid1` (titles dt22).
  Kernel, DTB, stub, base cmdline, firmware limits unchanged from dt21.

## Failure retained (not silently overwritten)

The first dt22 build used `#!/usr/bin/ash` in the wrapper. QEMU caught it:
`switch_root: failed to execute /usr/local/sbin/kestrel-pid1: No such file
or directory` -> kernel panic (bad interpreter: the live root has no
initramfs busybox ash; `/bin/sh` -> bash there). Evidence kept as
`dt22-artifact-audit-badinterp.json`, `dt22-candidate-badinterp.efi` and
`qemu-dt22-menu8-shell-fw-off-v1-{grub-badinterp.cfg,badinterp.log,
result-badinterp.json}` plus the blocked `-badinterp.fat`. The `-x` audit
outputs were recreated for the fixed candidate; nothing installed came from
the bad-interp build.

## QEMU proof (fixed candidate 483078d8...)

- Shell: PASS, 88.84s. Serial shows `KESTREL_PID1_STAGED`,
  `KESTREL_PID1_ENTER`, cmdline echo, `KESTREL_PID1_EXEC_BASH`,
  `[root@(none) /]#`, `overlay` fstype, all five platform modules in
  `/proc/modules`, clean poweroff. (`01-kernel-kmsg.log` in QEMU holds only
  the first 0.8s: the streamer never drains the 56s initcall_debug backlog
  on emulated USB. Natively the streamer provably keeps up — dt21 native
  logs captured live through 20.6s — so native markers will land.)
- Systemd: PASS, 309.2s, multi-user, userspace journal read back.
- Logger: PASS (flag-off / no-USB timeout / recovery / disarm preservation,
  zero physical firmware writes).
- Audit: kernel/DT/stub/cmdline byte-identical to dt21; DTB still dt21-green;
  wrapper present + executable; checkpoint/efilog unchanged; 5 module deps
  resolve.

## Installed state

- Physical USB holds dt22 (UKI 244482560 B `483078d8...`, menu 6211 B
  `6f755b6d...`), independently verified; dt21 rollback in
  `usb-before-dt22-20261017T*/`.
- Stuck-boot firmware `9b11354b-...` preserved in
  `firmware-clear-20261017T114416612Z/`; all four slots rearmed empty and
  verified (`dt22-preboot-20261017T114428699Z/`).
- Two prior native USB log dirs retained on the stick; the next boot creates
  a fresh `E:/Logs/boot-<new-id>/` with `03-preswitch.log` inside.

## What the next native boot must show

1. `KESTREL_PID1_STAGED` then `KESTREL_PRESWITCH_RECORDED` on screen.
2. Either `KESTREL_PID1_ENTER` (handoff works; then Bash/keyboard is the
   question) or its absence with a present `03-preswitch.log` (handoff
   itself fails; the log names the missing piece).
3. Photo the screen; back in Windows recover firmware + USB logs.
   No typing required; if a prompt appears, `findmnt -n -o FSTYPE /`
   should say `overlay`. Do not exit PID 1 Bash.
