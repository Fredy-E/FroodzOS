# dt25b native text and CPU-temperature observation

## Current result

The owner booted then-numbered physical GRUB **#10** and typed `kestrel-proof`, without deliberately waiting for completion. The command nevertheless saved a complete typed-proof file. This is real Lenovo hardware evidence, not a VM fixture. After the separately authorized menu cleanup, this same dt25b image/cmdline is **#1**, with genuine dt24-image text recovery at **#2**. See [current tasks and menu](TASKS.md).

- Boot ID: `6a63f6cc-bab8-4140-a699-cabc59050514`.
- Physical target reidentified: Kingston DataTraveler 3.0 USB, `PHYSICALDRIVE2`, `E:`, `KESTREL_A64`, FAT32, volume serial `USB_VOLUME_SERIAL`, 17179869184-byte partition at offset 1048576. Disk numbering is an observation, not a future identifier.
- Systemd PID 1, writable live overlay, Bash on `/dev/tty1`, multi-user target active, USB logger active: recovered `07-typed-command.txt:1-11`.
- Boot cmdline explicitly has `kestrel_graphics=0`, textboot enabled, `efi-pstore.pstore_disable=1`, and no firmware-logger opt-in.
- All **20 required CPU/cpuss thermal types** reported valid values in **62 consecutive complete samples**, totaling **1240 CPU readings**.
- Observed CPU range: **30.2–36.5 C**, within the diagnostic 5000 <= T < 80000 mC policy.
- Sample uptime: **17.80–115.66 s**, spanning **97.86 s**. System-state samples: 16 initializing, 46 running.
- Native startup journal reports **43.020 s** (15.240 kernel + 27.779 userspace).
- No panic/Oops/BUG/lockup signatures were found by the parent scan of the captured kernel stream. This does not prove behavior after capture ended.

The numeric samples establish native temperature visibility. They do **not** validate fan/cooling control, platform trips, thermal throttling, or the full live graphics guard's sysfs ancestry checks. Graphics was disabled: no Plasma, compositor, PAM or native GUI-lifetime acceptance is claimed.

## Immutable local evidence

Archive:

`testing/boot-failure/native-dt25b-6a63f6cc-bab8-4140-a699-cabc59050514-20261018T141554648665Z/`

The archive contains all **11 files / 428663 bytes** from this USB boot directory. Source-before/source-after/archive SHA256 checks matched for every file. `archive-manifest.json` lists the hashes; `thermal-samples.json` preserves parsed samples; `native-summary.json` contains the collector's nine true checks and per-sensor ranges. A separately implemented line-by-line parser independently confirmed the counts, all sensor identities, every value bound, and min/max. No previous evidence was overwritten.

Firmware readback is in `firmware-readback/report.json`: all four owned slots remain valid and byte-identical to the previous export, belonging to old dt24 boot `9c31cdbb-5aad-4802-9ea7-8101066b591e`. The reader performed zero firmware writes. New native `checkpoint-status.log` reports `firmware=0`, attempts `0x0`.

## On-device artifact readback during native-log review (before menu cleanup)

| File | Bytes | SHA256 |
|---|---:|---|
| `E:/EFI/Linux/kestrel-live.efi` | 244424704 | `b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753` |
| `E:/boot/grub/grub.cfg` | 6720 | `a4bec7016a798e82f7d6f2c546b8829d072075d36e8b61f61ed88e48035740de` |
| `E:/arch/aarch64/airootfs.sfs` | 1748525056 | `5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c` |

All match the expected dt25b menu/UKI and unchanged SFS. No USB files were modified during this inspection.

Read-only `chkdsk.exe E:` exited 0: Windows found no filesystem problems. `fsutil.exe dirty query E:` still reports Dirty, including after the scan. No filesystem repair or dirty-flag clearing was performed. Do not describe this as a clean-volume/repair result.

## Corrections to the previous handoff

1. **Retracted: '#8 is an untouched dt24 fallback.'** #8 and #10 both reference `/EFI/Linux/kestrel-live.efi`; the shared path now contains dt25b. Retained menu text is not retained artifact identity. The real old dt24 UKI is verified locally at `testing/boot-failure/usb-before-dt25b-20261018T110101253Z/kestrel-live-dt24.efi`, 244503552 bytes, SHA256 `4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02`. At that inspection it was not a separately selectable USB image. The subsequent authorized cleanup restored these exact dt24 bytes to `E:/EFI/Linux/kestrel-live-dt24.efi` and made them selectable as **#2**; the new path is hash-verified, not yet newly native-booted.
2. **Retracted: 'kestrel-proof displays thermal-zone/temperature lines.'** `builder/diagnostics/kestrel-text-proof.sh` saves the typed state/modules/input evidence and prints its saved-file marker, not temperatures. CPU readings are collected separately in `04-userspace-status.txt`.
3. `revision=v2-dt24` in the typed proof identifies the inherited text helper, not the UKI/DTB revision. Use actual on-device hashes and boot cmdline/provenance instead.
4. No firmware clearing/rearming was performed in the preparation; capture remains explicitly off. Do not describe the prior four-step preparation as a completed firmware rearm.

## Independent review complete / remaining retest gates

Both read-only reviews (`deleg_1364f870`) are complete. No captured boot/service failure blocks repeating the text test. Parent acceptance and scope are recorded in `parent-review-verdict.json` inside the archive. The complete typed-proof file proves command execution and persistence; lack of the final console message in the journal does not negate that. The caller returning to the prompt was not separately captured. Deferred suppliers remain actual peripheral-support gaps, not validated hardware.

- The 120-sample logger-finished marker is absent; only 62 samples are recovered. Sleep plus USB sync/collection makes sample count different from elapsed seconds. Partial capture is not automatically a crash.
- The journal records two successful tty1 getty exits/restarts; no exit cause is established yet. Do not label them a kernel crash or proven spontaneous shell failure.
- No final poweroff/power-down observation is captured. Clean hardware shutdown remains open.
- Full native guard provenance and software-Plasma pixels/input remain open; continue text-only, not graphics, for the repeat.
- Native boots remain owner-executed. No USB/firmware/Windows-boot setting changes were part of the read-only native-log inspection.

## Subsequent authorized menu cleanup

The owner then requested menu cleanup and task-list updates. The current menu has four entries: **#1 dt25b text + CPU logging (default)**, **#2 distinct dt24 text recovery**, **#3 unchanged Ubuntu control test**, **#4 firmware exit**. The old #8/#10 instructions are historical. Firmware capture and graphics remain off in both FroodzOS entries.

Canonical source `builder/live-grub.cfg` and physical `E:/boot/grub/grub.cfg` match: 2682 bytes, SHA256 `9c99836e41896defc99b3104eb3a65bf9c9d5d886c73a84cb7d58615078b4406`. Only the USB menu was replaced and the distinct dt24 recovery image added. Main dt25b UKI, SFS, GRUB loader/control boot files and all 48 previous USB logs were preserved. File data was flushed and `Write-VolumeCache` exited 0. A separate process independently rehashed both images/menu/SFS and checked every referenced boot file. Actual GRUB syntax and 11 menu contract checks pass.

Evidence/backups: `testing/boot-failure/dt25b-menu-cleanup-20261018T142458148359Z/`. No formatting, filesystem repair, firmware-variable or Windows-boot changes occurred. The dirty flag remains set. New menu arrangement still requires the owner-executed native retest: use **#1**, wait for the saved marker and prompt, then 90 seconds, then normal `poweroff` and observe completion.
