# dt24 native success: interactive systemd text boot

Verified from the real Lenovo 83N3 USB logs on 2026-10-18. Native boot ID: `9c31cdbb-5aad-4802-9ea7-8101066b591e`. Current boot payload hashes match the installed dt24 manifest; this is not a QEMU result.

## Milestone reached

**Kestrel now boots on this laptop into normal systemd, an interactive Bash session on `/dev/tty1`, and a working command-input path.** The earlier frontier stopped at pre-exec wrapper markers; this boot provides actual post-exec and typed-command proof.

### Direct evidence

| Evidence | Recorded result |
|---|---|
| `06-text-startup.txt:1-11` | `KESTREL_BASH_STARTED`; PID1 `systemd`; root `overlay`; child shell `bash`; TTY `/dev/tty1`; multi-user target and USB logger active. |
| `07-typed-command.txt:1-11` | `KESTREL_TYPED_COMMAND_OK` with the same boot ID, shell PID 1028, native TTY and active services. |
| Kernel input registration | `hid-over-i2c 048D:83DB Keyboard` at I2C address `0x3a` on `a84000.i2c`, registered at 9.432744 seconds. |
| Userspace journal | Getty started; multi-user target reached; startup reported `15.274s (kernel) + 25.511s (userspace) = 40.786s.` |
| Userspace status samples | State advances from `initializing` to `running`, remains running, then becomes `stopping` during poweroff. |
| Shutdown | `systemd-logind: Powering off...` and `systemd-shutdown: Syncing filesystems and block devices.` The final kernel power-down line was not captured, so full power-off completion is not independently established by the saved logs. |
| Persistence | USB proof/journal files and all four valid owned firmware records belong to this same native boot ID. |

The internal I2C keyboard is now positively identified and bound, unlike earlier boots containing only gpio-keys and the USB receiver. A successful typed console command is independently proven. The logs do not record per-device keypress origin: attribution of that command specifically to the built-in keyboard rather than the receiver requires the owner's observation. No arbitrary keylogging was introduced.

## What this closes

- Native bootloader/kernel/live USB/overlay path: demonstrated.
- Real switch_root into normal systemd: demonstrated.
- Actual Bash startup and a command entered through the native text console: demonstrated.
- Internal I2C-HID keyboard driver binding and the repaired supplier chain: demonstrated as a combined repair; the evidence does not isolate which individual change was sufficient.
- Userspace journal and bounded persistent boot evidence: recovered successfully.

This is a **usable native text-system milestone**, not completion of the original full-desktop M1 gate.

## Remaining work, ranked

1. **Native graphics/panel/Plasma.** GPU/GMU/MDSS, eDP PHY/rail and the display-clock blacklist are still in their diagnostic state. Restore their complete supplier/firmware paths deliberately; do not globally re-enable reset-associated GEM or lose this working fallback.
2. **Thermal and power observation before sustained load.** TSENS remains disabled in the current diagnostic tree. A battery thermal-zone name is present but the captured status contains no usable temperature numbers; do not call thermal safety validated.
3. **Touchpad.** `88c000.i2c` still defers on `qup-config`; hardware variant/address/IRQ must be matched before claiming touchpad support.
4. **Networking and audio.** NetworkManager starts, but the captured network activity establishes loopback only. WCN power/regulator and audio/DSP/interconnect dependencies remain unresolved. Modules loading does not prove Wi-Fi, speakers, microphone or camera function.
5. **USB completeness and hardening.** The boot stick and receiver work; `a800000.usb` remains deferred. All ports/Type-C, suspend/resume and battery behavior still need separate tests. Diagnostic no-vote paths, ignored unused resources and local root console are not production defaults.
6. **Distribution completion.** Keep general ARM64 as the goal, but only this Lenovo has current native text evidence. Reproducible packaging of the final repaired stack, portable signed updates/repository, installer/recovery, additional-board testing and redistribution/licensing gates remain. Earlier local signing/repository rehearsals are not a public release.

## Filesystem housekeeping

The kernel reported an improperly-unmounted FAT volume, and a read-only Windows dirty-flag query still reported Dirty. A read-only `chkdsk E:` then returned exit 0: “Windows has scanned the file system and found no problems. No further action is required.” No `/f`, `/r`, filesystem repair, formatting or boot-file change was performed for this review. All critical payload hashes matched. Preserve normal shutdown/eject practices and do not infer corruption solely from the dirty flag.

## Timestamp interpretation

Early journal/FAT timestamps are not a reliable ordering source: the clock starts from a fallback epoch and is corrected when the PMIC RTC registers. The boot ID, monotonic kernel timestamps and systemd startup duration establish chronology. Do not confuse the old 1979/September file dates with a different boot or infer Internet time synchronization from the clock correction.

## Evidence preserved

Hash-verified archive: `testing/boot-failure/native-dt24-9c31cdbb-5aad-4802-9ea7-8101066b591e/`.

- `usb-logs/`: the native log set, including Bash-startup and typed-command proof.
- `firmware/`: the read-only recovery export; owned records preserved, not cleared.
- `manifest.json`: per-file and boot-payload hashes.
- `native-result.json`: current structured acceptance and its limits.

No kernel, source/build configuration, USB boot file, firmware variable or Windows boot setting was modified during this log review. The preboot handoff is retained as historical evidence rather than silently rewritten to claim it knew this result in advance.
