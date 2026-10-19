# FroodzOS — project progress

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


Public name selected by the user: **FroodzOS**. Kestrel remains the legacy implementation name; working boot/logger/USB identifiers have not been renamed. Publication remains separately approval-gated.

Updated 2026-10-18 from the native dt25b boot and verified four-entry USB menu cleanup. Current checklist: [TASKS.md](TASKS.md). Evidence: [dt25b native thermal check](dt25b-native-thermal-check.md) and [dt24 native text success](dt24-native-text-success.md).

## Latest #1 retest and active repair

New native boot `7f84303a-7adb-4ada-a3ef-eb8cec4a722f` saved typed proof and **100 complete live samples of all 20 CPU/cpuss types, 37.7–47.9 C**. Shutdown reached filesystem sync; the final partial sample is stopping-state evidence, not an out-of-bounds CPU temperature. Final hardware poweroff remains unproven. The current entry explicitly has `kestrel_graphics=0`; no amount of waiting launches a desktop in this text-only entry.

The owner authorized forward fixes. [dt26 native graphics repair](dt26-native-graphics-repair.md) records the active disjoint session-contract/observability implementation, review/build/EFI/media gates and no further blind unchanged text retries. No new graphical image is installed yet. The existing rubric still calculates **about 65% first usable Lenovo desktop / 35% maintained general-ARM64 release**; unverified GUI work has not been counted as native success.

## Executive status

**Native interactive text boot and real CPU-temperature visibility are achieved on the Lenovo IdeaPad Slim 3 15Q8X10 / 83N3.** All 20 required CPU/cpuss sensor types produced 1240 valid readings in 62 complete samples (30.2–36.5 C). This does not validate cooling/throttling or a desktop. Plasma and the full original M1 acceptance remain open.

| Workstream | Current status |
|---|---|
| Isolated ARM64 builder, source pins and boot artifacts | Established; earlier ARMv8-A virtual baseline and local signing/package rehearsals documented. |
| Native bootloader, kernel, USB boot source and live overlay | Verified on this Lenovo. |
| Native systemd, multi-user target, Bash on tty1 and typed command | Verified on dt24 and dt25b. The latest typed-proof file was saved despite the owner not waiting deliberately. |
| Internal keyboard | Actual I2C-HID device 048D:83DB binds; typed console input works. Per-device origin of the entered command is not logged. |
| CPU-temperature observation | Native dt25b readout passes the required names/count/numeric bounds. The actual graphics guard's canonical sysfs/device checks and thermal-control behavior remain unvalidated. |
| Boot logging and recovery | Latest native USB evidence archived; four old dt24 firmware records preserved unchanged. Clean menu now has a genuinely separate, hash-verified dt24 recovery image. |
| Software graphics / Plasma | Implemented diagnostic path and disposable EFI refusal/lifetime regression recorded; native guard, pixels/input and real session cleanup still pending. No GUI entry is exposed in the current menu. |
| Power, touchpad, networking, audio and other peripherals | Incomplete or unvalidated; deferred suppliers remain. |
| Full M1: desktop, input, wired network, USB, safe shutdown | Partial, not closed. Latest capture ends while running; final hardware power-down is not recorded. |
| General ARM64 distro / public release | Not complete. Additional boards, reproducible final packaging, portable updates, installer/recovery and per-artifact publication approval still needed. Vendor firmware stays local-only. |

## Next technical milestone

Owner retest: **#1 dt25b text**, wait for `KESTREL_PROOF_SAVED` and the prompt, allow 90 seconds of background logging, then normal `poweroff` and observe shutdown. **#2 is the actual dt24-image text recovery**, not the old misleading #8 label. The new menu paths are hash/syntax verified but not yet native-booted in this arrangement. Both FroodzOS entries keep graphics and firmware capture off.

After this shutdown/recovery frontier, validate the actual simpledrm/CPU preflight on hardware before a separately prepared bounded software-Plasma test. Do not blanket-enable the reset-associated accelerated GPU graph.

## Earlier rough progress estimate — not re-scored after TSENS

At the user's earlier request, the subjective engineering estimate was **about 65% toward the first usable native Lenovo live desktop (full M1)** and **about 35% toward the full maintainable public general-ARM64 distribution goal**. These are milestone-weighted judgments, not measured code/work-hours/time remaining; this update does not silently recalculate them. A reviewed source-only preview may precede a complete OS image.

See [FroodzOS publication path](froodzos-publication.md) and the explicit judgment-based [weighting rubric](research/evidence/froodzos-publication-20261018/progress-estimate.json).

## Evidence and safety

Latest native boot ID: `6a63f6cc-bab8-4140-a699-cabc59050514`; journal startup 43.020 seconds. Previous dt24 boot: `9c31cdbb-5aad-4802-9ea7-8101066b591e`, 40.786 seconds. Follow the detailed reports for timestamp, input-attribution and shutdown limits.

Authorized menu cleanup changed only the USB menu and added `EFI/Linux/kestrel-live-dt24.efi`; current dt25b UKI, SFS, GRUB loader/control boot files and all 48 old USB log files remained unchanged. Sources and both USB images were fully hashed, the volume cache flushed, and a separate process verified device readback. Eleven menu contract tests and actual GRUB syntax checks passed. No formatting, firmware-variable clearing/rearm, Windows/internal-storage/boot-security/Kali changes occurred. The dirty flag remains set; read-only CHKDSK found no problems, and no repair was performed.

Older phase reports and the original plan are historical; [TASKS.md](TASKS.md), this page and the latest native report own current status.

