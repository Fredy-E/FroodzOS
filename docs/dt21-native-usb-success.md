# dt21 native result: USB enumeration and live-root mount succeed

## Evidence identity

- Native boot ID: `5fe82fa8-ffea-4bae-a4c2-9400feaa93ca`.
- Recovered on 2026-10-17; this is real Lenovo evidence, not a QEMU result.
- Physical UKI and menu were freshly hashed and match the dt21 update manifest.
- Firmware export: `testing/boot-failure/firmware-recovery-20261017T110047368Z/`.
  All four records are valid, share the new boot ID and differ from dt20.
- Six USB log files were copied without changing their source, with source and
  destination SHA256 equality and a second source check:
  `testing/boot-failure/native-dt21-5fe82fa8-ffea-4bae-a4c2-9400feaa93ca/`.
  `archive-manifest.json` records the individual file hashes, artifact hashes,
  source paths and acceptance limits.
- Both owner-supplied screen transcripts were archived. Every timestamped line
  in each matches the USB kernel log exactly, including the final
  `20.600965 ... sync_state() pending due to b9c000.i2c` line. This compares the
  supplied text, not unseen screenshot pixels.

## Verified native improvements

`usb-logs/01-kernel-kmsg.log` in the archive records:

- Line 3118: GPI at `b00000.dma-controller` probes successfully.
- Line 3149: I2C5 `b94000.i2c` probes successfully.
- Lines 3416/3418/3420/3422: all four PTN3222 clients at
  `0-0043`, `0-0047`, `0-004b`, `0-004f` probe successfully.
- Lines 3498/3582/3667: `a200000.usb`, `a400000.usb`, `a600000.usb`
  bind successfully. `a800000.usb` still defers.
- USB enumeration includes the integrated Chicony camera, a `2.4G Mouse`
  receiver and the Kingston DataTraveler 3.0. The receiver registers mouse
  and keyboard-class HID interfaces; that is not proof a key was typed.
- Lines 3785/3789/3825/3832/3845: USB mass storage, SCSI and `/dev/sda`
  are created for the Kingston stick.

The checkpoint counter `external_usb=3` counts non-root-hub USB devices,
including the integrated camera. It does not establish three physically
external peripherals. `input_errno=0` remains a logger input-read status,
not a keyboard test.

`usb-logs/02-initramfs-console.log` confirms:

- `KESTREL_A64` is found and mounted successfully at `/run/archiso/bootmnt`.
- The RAM cowspace and `/dev/loop0` live filesystem mount successfully.
- Execution reaches the logger late hook and cleanup hook.

`usb-logs/00-status.txt` records `/dev/sda1`, the matching boot ID,
`KESTREL_OVERLAY_ROOT_READY`, `KESTREL_SWITCH_ROOT_PENDING` and
`INITRAMFS_SNAPSHOT_LOOP_STOPPED`. The overlay-ready marker is guarded by
`mountpoint -q /sysroot` in `builder/diagnostics/kestrel-init-log.sh`.
This proves the native live-root mount stage; it is not a post-switch-root
`findmnt /` result.

Firmware slot 2 has `label=present` and slot 3 has `reason=stop`, not the old
boot-device timeout. Slot 3 is at uptime_ms=14128. The helper is deliberately
stopped by the cleanup hook; that stop record is not a kernel-death marker.
The kernel streamer continues through the exact final supplied screen line.

## Interpretation and remaining acceptance

The dt20 failure to enumerate the boot stick and mount the live filesystem
is no longer present in this dt21 attempt. The repaired I2C/repeater supplier
chain now binds on real hardware. This validates the combined dt21 delta,
not independent attribution of success to its ICC or conditional GPI pieces.

`sync_state() pending` is not, by itself, a panic, a root-mount failure or
proof the kernel is frozen. Other supplier chains remain unresolved, including
`a800000.usb`; do not disable more nodes merely to remove these messages.
The screenshot no longer lists I2C5 `b94000` among its pending I2C consumers,
consistent with its successful probe in the full log.

The selected command line still specifies `init=/usr/bin/bash` and blacklists
`dispcc_x1e80100`. It deliberately bypasses systemd/SDDM. These logs end the
initramfs capture at **switch-root pending**; neither a responsive native Bash
prompt nor actual keyboard input nor native systemd/Plasma is yet verified.
There is no new visible explicit failure in the supplied screen excerpt.
Late kernel output may obscure a prompt, but the logs do not prove that is
what happened.

The discriminating observation is an external USB keyboard response, followed
by `findmnt -n -o FSTYPE /` reporting `overlay` and `cat /proc/1/comm`
reporting `bash`. Do not exit PID 1 Bash. A desktop acceptance claim still
requires a separate native systemd/graphics test.

## Preservation and scope

This recovery changed no USB files, firmware variables, kernel, menu or boot
settings. Only host-local evidence and documentation were written. The four
new firmware records remain occupied and preserved; exporting did not rearm
them. Any later rearm remains a separate checked, authorized operation.
All vendor-firmware-bearing artifacts remain local-only.
