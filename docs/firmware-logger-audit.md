# Firmware logger audit: dt13 (historical)

For the bounded replacement and current test evidence, see
[logger-v2-repair.md](logger-v2-repair.md). The dt13 infinite writer audited
below is retired; its historical HOLD is not a verdict on newer revisions.

## Verdict

**HOLD native FW LOG testing. Harden and validate the logger first.**

This audit supersedes the earlier statements that the FW LOG entry was ready,
that it survives any crash, and that no photos are needed. Those statements
were not supported by an active logger/persistence test. Generic EFI boot and
logger persistence are separate gates.

No USB files, EFI variables, BIOS settings, Windows boot settings or kernel
artifacts were changed during this audit. The Windows check parsed the reader
without executing it or calling firmware APIs.

## Verified present state

Read-back of the attached E: media:

- UKI SHA256: `0f319c9847b3dcbb31701b707c557d78fab62fd7bbaf9823174ac63c2e4410a2`
- Menu SHA256: `9bbf0d682159a9ac5d5856b8c58efa20ec0d6bec0a3f721a50593f7f912e5200`
- `E:/Logs` exists and has zero files.
- Entry 8: `Kestrel v2 - NO dispcc (display-clock suspect)`; USB capture flag only.
- Entry 9: `Kestrel v2 - NO dispcc + FW LOG (streams boot text to firmware)`; enables `kestrel_efilog=1`.
- Entry 10: slow print. Entry 11: return to firmware.

## Actual validation coverage

`testing/boot-failure/qemu-v2-dt13-shell-result.json` reports `passed: true`,
`stop_reason: poweroff`, root shell/overlay/identity success, and
`hardware_validated: false`. This is a valid generic boot result.

However, the actual kernel command line in `qemu-v2-dt13-shell.log` lacks
`kestrel_efilog=1`. The early hook therefore returns without starting the
writer. `prepare-partitioned-validation.py` uses `builder/live-grub.cfg`, not
the FW LOG menu. `run-efi-validation.py` supplies `-bios` and no explicitly
persistent writable variable-store image. Neither its markers nor its result
assert a variable was written, retained across a new VM process, or recovered.

**Consequently: inclusion and flag-off boot are verified; firmware logging,
persistence and Windows recovery are not.**

## Findings

1. **Unbounded firmware calls.** `builder/diagnostics/kestrel-efilog-loop.sh`
   lines 13-24 loops forever, rewriting a tail and sequence variable every
   five seconds. Four slots bound retained payload, not total writes or flash
   garbage collection. No deadline, write budget, change detection or
   free-space policy is implemented.
2. **Failure handling is missing.** Mount and write errors are suppressed.
   An existing directory is accepted without verifying that it is a writable
   efivarfs mount. Sequence advances regardless of write success. Custom
   variables can be immutable after remount/reboot; this path is unhandled.
3. **Coverage is weak.** Only the last 512 bytes are sampled, at five-second
   intervals, with no per-record boot ID, kernel sequence range, entry/revision
   identity or checksum. A freeze between samples loses the intervening text.
   An initramfs shell cannot capture a failure before it runs, and cannot keep
   logging after the kernel stops scheduling or firmware calls stop working.
4. **Cleanup is not implemented.** The hook's cleanup function is a no-op;
   the comment that switch_root necessarily kills the loop is not a lifecycle
   guarantee. No PID/stop handshake is provided.
5. **Reader has a real PowerShell binding bug.** The script assigns
   `$ErrorActionPreference` before `param([switch]$Delete)`. A read-only AST
   audit returned `reader_param_block_present: false` and a command named
   `param` on line 4. A zero parser-error count does not validate this script:
   the intended parameter declaration is parsed as an ordinary command.
6. **Reader privilege and preservation handling is incomplete.** It does not
   enable/check `SeSystemEnvironmentPrivilege`, labels every failed read as
   ABSENT, and in delete mode removes variables before saving its output.
   A save failure could therefore discard the only copy. Never run its
   `-Delete` mode as currently written.
7. **Namespace needs explicit ownership.** The literal GUID currently shared
   by writer and reader is `8be4df61-93ca-11d2-aa0d-00e098032b2c`. Preserve it
   exactly for any read-only recovery of existing records; do not silently
   normalize it to a similar standard GUID. A future format should use a
   documented project-owned UUID and a separate legacy read path.

## Safer development path (requirements, not implemented)

- Prefer RAM-first capture and flush through the live system's existing USB
  mount as soon as it is available. Never race archiso with a second mount.
  RAM alone cannot survive a forced power-off.
- If firmware persistence is retained, use an explicit opt-in, a strict total
  write budget and deadline, compact milestone/error records, no unchanged
  writes, and stop immediately on errors. Avoid treating NVRAM as a continuous
  log disk. Budget limits reduce risk; they cannot eliminate firmware bugs or
  make a blocked runtime call safely interruptible.
- Use a versioned record with boot ID, revision/entry ID, sequence, payload
  length and checksum. Save whole records in one checked operation, validate
  read-back, and never touch boot/security/vendor variables.
- Implement actual process shutdown. Keep firmware failure out of the boot
  critical path, while acknowledging a firmware runtime fault may still affect
  the machine regardless of backgrounding.
- Repair the Windows reader; distinguish missing data, denied privilege and
  unsupported firmware. Export and verify raw records before any separately
  authorized deletion. Keep default recovery read-only.
- Test absent/read-only/full/rejected storage and malformed records locally.
  Then boot the exact new UKI with its flag ON against a disposable persistent
  QEMU/EDK2 variable store, terminate the VM abruptly, start a new process with
  the same store, and verify recovered bytes/checksums. Also verify flag OFF
  performs no logging writes. Preserve evidence with fresh test tags.
- Only after these gates, obtain approval for the remaining firmware-write
  risk and run one controlled native attempt. QEMU is not Lenovo firmware.
  The user should retain photo/video fallback until native recovery succeeds.

## Other corrections to the conversation

- A completed probe line names a probe that returned, not necessarily the
  cause of the next hang. A last visible framebuffer line can lag execution.
- xHCI root hubs (`1d6b:0002/0003`) are not the Kingston device. Their creation
  does not prove that removable storage enumerated or mounted.
- The supplied `invalid path=-517` followed by host removal is concrete
  interconnect/deferred-probe evidence, not evidence of firmware randomness.
- Empty USB logs prove no file was recovered, not by themselves why boot
  failed. Logger timing, USB enumeration and mount state must be distinguished.
- The dt12 driver workaround was built, but its effect on native teardown is
  unverified without a later hardware trace. Do not state that USB now STAYS.
- Commands after `;`, pipes or `&&` outside `wsl.exe ... -- <command>` run in
  the Windows host shell. Host failures to access `/mnt/d` do not prove a WSL
  reboot or dropped mount. Prior mount/reboot diagnoses were not established
  by those probes.

## Primary references

- Linux efivarfs documentation (custom-variable immutability and firmware
  POST-failure warning): https://docs.kernel.org/filesystems/efivarfs.html
- Microsoft firmware-read API (privilege requirement and error reporting):
  https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfirmwareenvironmentvariablew
- UEFI runtime variable services and QueryVariableInfo:
  https://uefi.org/specs/UEFI/2.10/08_Services_Runtime_Services.html
