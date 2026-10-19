# Firmware capture v2 repair (dt19)

> Current USB candidate: [dt20 USB dependencies and live-root shell](dt20-usb-shell.md).
> dt20 retains this logger and the dt19 kernel/DT; approved firmware rearming
> is complete and independently verified. Installed-image and next-boot
> sections below describe dt19; use the linked dt20 instructions.

## Current scope

This fixes diagnostic capture in **#8 and #9**, not USB enumeration or desktop
boot. Their shared UKI retains the dt17 kernel and device tree. No port, PHY,
interconnect or kernel configuration changes are made by this repair.

## Corrections to earlier reports

- The `936771c0-9fce-4257-878c-5d22542d61a7` records are a real second native
  capture, distinct from the earlier `c28598ee-...` boot. Re-reading them later
  does **not** prove another successful capture. The host reader now reports
  boot IDs and whether the bytes match the previous export.
- A missing final slot does **not** prove the kernel died, a power-off occurred
  before 60 seconds, or USB teardown occurred. A firmware-write/readback failure,
  logger exit or disarmed logger can also explain missing evidence. Previous
  claims naming power-off as the cause are retracted.
- The three old records stop at the first `invalid path=-517`. They do not
  contain the following `continuing without it` warnings. Treat the usb-ddr
  explanation as source-based inference, not a complete native trace.
- The owner's later emergency-shell transcript proves continued kernel/initramfs
  activity, but does not by itself prove every USB controller stayed bound.
- Earlier claims that exporting records rearms capture were wrong. Export is
  read-only. Existing project records must be separately cleared to rearm.
- EFI pstore can load from the squashfs after switch_root even when absent in
  initramfs. Both embedded default cmdline and GRUB platform parameters now
  explicitly carry `efi-pstore.pstore_disable=1`.

## Capture changes

The former writer spent slot 1 on root-hub registration and slot 2 on the FIRST
error, before the informative continuation lines. Raw kmsg metadata occupied
much of each 944-byte payload. It could also exit on an input error without
reporting useful later state.

The v2 writer keeps the **same project GUID, four one-shot variables, at most
1024 bytes per record, no overwrites/deletes, and 60-second lifetime**:

| Slot | Trigger (relative to early capture start) | Evidence |
|---|---|---|
| 0 | Start | Capture version, kernel build, boot ID, current state |
| 1 | 1.2 seconds after first relevant error, or 6 seconds | Follow-up USB/ICC/PHY messages, not just the first failing line |
| 2 | 12 seconds | Later binding/enumeration state plus filtered messages |
| 3 | 55 seconds, or normal cleanup if earlier | Boot-device-timeout observation and USB state |

Each record includes root-hub count **separate from external devices**, label
presence and binding status for the four named platform USB controllers.
`sync_state()` chatter and auxiliary `SUBSYSTEM`/`DEVICE` metadata are omitted
from firmware payloads; the 64 KiB RAM ring retains raw kmsg for USB flushing
if storage becomes available. Input errors no longer cancel timed state capture.

#8 and #9 use `rd.log=console rd.log=file`, verified against the installed
mkinitcpio parser. This records initramfs userspace mount errors in RAM as well
as keeping them visible; `/dev/kmsg` alone cannot see those errors. The attempted
`rd.log=console,file` syntax was rejected by an EFI test, so the dt18 candidate
was retained as failed evidence and **never installed on the USB**.

Console reports successful slots (`KESTREL_FW_SAVED slot=N`) and explicit
`KESTREL_FW_DISARMED` / `KESTREL_FW_STOP` conditions. A slot is marked saved only
after byte-exact readback. A rejected firmware write stops further attempts.

## Host recovery and rearming

`Read-KestrelCheckpoint.ps1` remains read-only, checks CRC, saves raw bytes and
checks their readback, reports boot IDs and unchanged exports. CRC-valid does
not mean complete or fresh.

`Clear-KestrelCheckpoint.ps1` now requires **both `-Yes` and the exact exported
`-ExpectedBootId`**. It launches the reader in a separate process, rejects
invalid/mixed/mismatched records, verifies raw backups and all current bytes
before the first deletion, deletes only the four named project variables, checks
all four absent afterward, and restores its token privilege. It never clears
legacy/global, boot, security or vendor variables.

User explicitly approved export + clear of only these slots in this repair.
Native records were archived in `testing/boot-failure/firmware-clear-20261017T075503933Z/`,
then the three saved slots were deleted and independent readback confirmed all
four `KestrelBoot00..03` missing. The previous exports remain intact.

## Verification evidence (results recorded beside this document's build)

- `testing/boot-failure/checkpoint-timeline-v2-result.json`: synthetic delayed
  warnings, quiet-input later checkpoint, noise filtering, four-write limit,
  independent Python CRC check.
- `checkpoint-unit-result.json`: filesystem gate, existing-record refusal,
  record bounds and stop-on-write-error (ordinary-directory backend only).
- `checkpoint-reader-test-result.json`: Windows accepts valid records and
  rejects corrupt/truncated synthetic records; no firmware writes.
- `test-recovery-safety.ps1`: PowerShell parsing, C# compilation, refusal without
  confirmation and malformed boot ID; no firmware calls.
- `dt19-artifact-audit.json`: PE sections equal the exact kernel, DTB and
  initramfs inputs; pstore disable present; candidate SHA256.
- `dt19-logger-v2-v1-result.json`: **PASS** on the exact candidate hash below.
  Flag OFF produced zero project records. Hot-unplugging the virtual stick
  after earlyhook reached the real boot-device timeout and emergency prompt.
  After an abrupt VM stop, a new VM process recovered **four** CRC-valid
  records. The final payload contains `external_usb=0`, `label=missing`, and
  `initramfs_boot_device_timeout=seen`. A later flag-ON boot refused existing
  records and retained every recovered byte.
- `qemu-dt19-menu8-fw-off-v1-result.json`: **PASS**, actual #8 parameters with
  firmware flag removed solely for this file-logging regression; serial
  console and one-second fixture menu timeout. EFI -> overlay -> systemd
  multi-user in 322.99 seconds under TCG (declared 480-second test budget),
  USB kmsg/journal/RAM captures and STOPPED marker all verified. No panic.
- `dt19-windows-vm-decode/report.json`: Windows reader accepted the actual
  recovered VM timeout record, independently checking its CRC and payload.

## Installed USB and next native attempt

`Update-Dt19Logger.ps1` passed its dry run, preserved dt17 rollback files,
then updated only the UKI and GRUB menu. `Verify-Dt19Logger.ps1` independently
re-resolved Kingston PhysicalDrive2 / FAT32 KESTREL_A64 E:, matched both
changed files plus the untouched loader and squashfs against staging, checked
11 menu entries and #8/#9 flags, and read all four firmware slots as Missing.

- UKI: **244392448 bytes**, SHA256
  `fae9defe9b49c2fd45269450da966dfeec1d89bd25b364a2a1c1ce0dcd7f3ec9`.
- Menu: **5789 bytes**, SHA256
  `1e02ed0abf31f27c619d04c830a31f7edfa79d0305373f039390617b473fc73d`.
- Evidence: `usb-dt19-result.json`, `usb-dt19-independent.json`,
  `dt19-update-manifest.json`; existing staging menus now match the stick.
- #8: `Kestrel dt19 - NO dispcc + FW LOG v2 (default)`.
- #9: same v2 capture with an additional GRUB confirmation prompt.

Boot **#8 once**. At the emergency prompt, do not try to type: no USB keyboard
is required for capture. Leave it running until `KESTREL_FW_SAVED slot=3` and
`KESTREL_RAM_CAPTURE_STOPPED v2` (allow about 90 seconds after kernel start).
If it instead reports DISARMED or FW_STOP, retain that screen as evidence.
Return to Windows for a read-only export before another test; exporting alone
does not rearm. Photos remain a useful fallback. No desktop success is claimed.

## Native dt19 capture recovered

Read-only recovery is archived at
`testing/boot-failure/firmware-recovery-20261017T084552888Z/`.
Boot ID: `c0fede4e-027f-44a3-a71e-3d6814f9b9bd`.
All four records were recovered with valid CRCs; independent Python checks
confirmed their raw SHA256 values and CRCs. The preceding pre-boot export
`firmware-recovery-20261017T075523019Z/report.json` had all four slots Missing,
so these are new native evidence rather than another export of the old boot.
Recovery made zero firmware writes and did not clear any slots.

- Checkpoint kernel uptimes: 9.030, 10.795, 21.087 and 64.128 seconds.
- At the three later checkpoints: `usb_roots=2 external_usb=0 label=missing`.
  Root hubs are not external devices or evidence that the stick enumerated.
- `a600000.usb` remained bound at those snapshots. Both optional interconnect
  paths reported `-517`, then explicitly `continuing without it`; its parent
  probe returned 0. These records do not show the former immediate teardown.
- `a200000.usb`, `a400000.usb` and `a800000.usb` were unbound at the snapshots
  with deferred probes in the retained messages. `pmic-glink` reported
  `failed to initialize pdr`. This is a concrete investigation lead, not yet
  proof of the cause of all missing external USB devices.
- Slots 2 and 3 contain `initramfs_boot_device_timeout=seen`. Native live-root
  and desktop boot remain unresolved. The logger was still executing at
  approximately 64 seconds; this does not prove indefinite kernel health.
- `E:/Logs` still contains zero files. The installed UKI and menu hashes still
  match the dt19 manifest. Persistent evidence was in firmware, now also in
  the local recovery directory; the RAM ring alone does not survive reboot.
- The owner reported continually flashing dashes. Their meaning is not
  established by these records; do not infer a crash or successful boot from
  that animation alone.

Native bounded checkpoint capture is now demonstrated for this boot, including
late timeout evidence. Existing slots remain occupied and will disarm another
capture until separately authorized backup/clear/absence verification.
Firmware runtime calls can still hang on broken firmware; the bounded budget
reduces risk but cannot guarantee safety or survival across every failure.
