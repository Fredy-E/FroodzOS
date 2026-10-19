# FroodzOS on Lenovo ARM64: dt21 through the dt26 native desktop milestone

Public-ready chronological history. Covers the USB/I2C repair (dt21),
PID1 handoff diagnosis (dt22), post-switch proof (dt23), keyboard/systemd
text repair (dt24), the rejected dt25 graphics candidate and dt25b thermal
work, and the dt26 bounded-graphics diagnostic through native desktop
observation plus current networking/Hermes prerequisites.

Scope discipline for the whole span: approved file-only USB updates, no internal-disk writes, formatting, partition-table, boot-order or security-setting changes. Earlier separately authorized runs rearmed only the four project-owned checkpoint slots after verified backups and identity/byte checks; those scoped firmware changes are documented below. Later dt26 capture remained off and old records were preserved. No unscoped firmware change is implied. Native boots are owner-executed; VM results validate tooling and boot chain, not hardware. Vendor-firmware-bearing artifacts stay local-only.

 assumed final location: `docs/history/` — all doc links below are
relative to that directory (`../<page>.md`).

## 0. Where things stood before dt21

dt20 and earlier established the live USB boot chain (kernel, initramfs,
Kestrel logger hooks, GRUB menu) but never enumerated the boot stick on
real hardware. The failure was a silent DT supplier chain, not a missing
kernel module alone. Native I2C5, GPI DMA, and the four board PTN3222 USB
repeaters never probed. dt21 was authorized as a targeted repair of that
chain.

## 1. dt21 — USB repeater / I2C5 dependency repair

Doc: [dt21 repeater fix](../dt21-usb-repeater-fix.md) ·
Result: [dt21 native USB success](../dt21-native-usb-success.md)

### What was wrong

The active device-tree source showed I2C5 (`i2c@b94000`) requesting ICC
paths whose config route names the disabled `gem_noc`; the DDR route was
severed by the same disable. GENI I2C probe (`qcom-geni-se`) mandates
successful ICC acquisition, so packaging the `i2c-qcom-geni` module alone
(dt20) could never create the adapter. The four board repeaters
(0x43/0x47/0x4b/0x4f, children of I2C5, feeding `usb_2`, `usb_mp`,
`usb_1_ss1` through their HS PHYs) therefore never probed. I2C5's `dmas`
property named the disabled `gpi_dma0` channel 5; the modular `gpi`
driver was not packed. Generic interconnect code returns NULL for absent
paths and GENI tolerates NULL, which made a local diagnostic no-vote path
possible without re-enabling the reset-associated GEM NoC.

### The repair (patch `0018`, three properties only)

1. Board `&i2c5`: delete only `interconnects`/`interconnect-names`.
2. Board `&gpi_dma0`: enable the existing provider with unchanged channel
   mask, interrupts, and IOMMU mapping.
3. Initramfs `MODULES`: pack and early-load `gpi` ahead of the already
   included GENI I2C / PTN3222 / QRTR modules.

Decompiled-DT comparison proved nothing else changed: GEM, GPU, GMU, MDSS
stayed disabled; kernel Image, boot stub, HWIDs, cmdline base, checkpoint
binary, and logger hooks byte-identical to dt20. No-vote operation is a
diagnostic local bring-up, not a production power/performance claim. PHY
mode, regulator behavior, and port-to-controller mapping remained
hardware-acceptance questions.

### Rejected alternative, preserved

A second review suggested USB2-only fallback but had not read the live
kernel tree and inferred a working I2C adapter from module presence. It
was not stacked onto dt21. Its `input_errno=0` statement was explicitly
rejected as HID evidence: the field tracks `/dev/kmsg` input errors, not
key presses.

### Harness failure preserved

The first patch dry run failed on malformed EOF framing from a
line-numbered readback. No source was changed. The patch was regenerated
from actual file bytes and passed forward/reverse checks. Both the failed
`dt21-board-build` snapshot and the successful `dt21-board-build-v2` are
retained as distinct runs.

### Validation

- `dt20-board-dependency-red` / `dt20-gpi-module-red`: old DT/initramfs
  fail the ICC/GPI gates (RED proof).
- `dt21-board-dependency-green` / `dt21-dtb-build-result`: new gates pass;
  only the three allowed compiled properties differ; Image unchanged.
- 5 platform-gate unit methods pass, including per-provider removal.
- `dt21-artifact-audit`: exact PE inputs, module closure, local firmware,
  correct PID1, logger present.
- QEMU shell (104.96 s / 360 s budget) and systemd (330.34 s / 600 s):
  PASS with real module/overlay/capture/poweroff evidence.
- Logger VM suite: flag-OFF zero records, virtual-USB removal/timeout/
  abrupt-stop/new-process recovery, existing-record disarm preserving
  bytes. Zero physical firmware writes.
- Physical install: Kingston/KESTREL_A64 FAT32 association re-resolved
  (not drive-letter matching), readback of changed UKI/menu plus
  unchanged loader/rootfs, staging and alternate menus synchronized. Four
  owned checkpoint slots rearmed empty and independently verified after
  archiving prior evidence.

Candidate UKI: 244,480,512 bytes,
`a1ced156e198be71a586aa6283a86edc2de51faa…` (full hash in the dt21 doc).
DTB 207,916 bytes; menu 6,195 bytes.

### Native result

Native boot `5fe82fa8-…` (plus a second dt21 boot `9b11354b-…`, archived
separately): GPI probes, I2C5 probes, all four PTN3222 clients probe,
`a200000`/`a400000`/`a600000` USB bind (`a800000` still defers). The
Kingston stick enumerates as `/dev/sda`, `KESTREL_A64` mounts,
cowspace/loop mount, logger late/cleanup hooks run, `KESTREL_OVERLAY_
READY` (guarded by `mountpoint -q /sysroot`) and `KESTREL_SWITCH_ROOT_
PENDING` recorded. All four firmware slots valid under the new boot ID.
Six USB logs hash-verified on copy; every timestamped owner-supplied
screen line matched the kernel log exactly, including the final
`sync_state() pending … b9c000.i2c` line. `sync_state pending` is not a
panic/mount-failure/freeze proof. Camera + 2.4 GHz receiver enumerate
(HID interfaces registered); no key press proven. `external_usb=3`
counts non-root-hub USB devices including the camera, not three external
peripherals.

Still open after dt21: no responsive Bash prompt, no typed input, no
systemd/Plasma — the selected `init=/usr/bin/bash` left zero trace either
way.

## 2. dt22 — PID1 handoff markers (diagnose the silent switch_root gap)

Doc: [dt22 handoff fix](../dt22-pid1-handoff-fix.md)

Two native dt21 boots stopped at the same silent point (overlay ready,
switch-root pending, kmsg ending ~20.6 s, no panic, no shell). dt22 added
markers on both sides of the handoff instead of changing hardware paths:

- New `builder/diagnostics/kestrel-pid1.sh` (`/bin/sh`, not ash): prints
  `KESTREL_PID1_ENTER`, cmdline, `ls -l /usr/bin/bash`,
  `KESTREL_PID1_EXEC_BASH` to console + kmsg, then execs
  `/usr/bin/bash -i` on `/dev/console`.
- Initramfs `install/kestrel_log` ships it as `/usr/bin/kestrel-pid1`.
- `run_latehook` stages it into the live overlay at
  `/sysroot/usr/local/sbin/kestrel-pid1` (upperdir write, works with
  `init=` bypassing systemd), printing `KESTREL_PID1_STAGED`.
- `run_cleanuphook` writes `03-preswitch.log` to the USB log dir before
  handoff (cmdline, `/sysroot` state, both target binaries, mounts).
- Menu #8/#9 `init=` changed to the wrapper (titles dt22). Kernel, DTB,
  stub, base cmdline, firmware limits unchanged.

### Wrong-interpreter failure preserved: the bad-interpreter build

The first dt22 build used `#!/usr/bin/ash`. QEMU caught it:
`switch_root: failed to execute … No such file or directory` → kernel
panic, because the live root has no initramfs busybox ash. Evidence kept
as `dt22-artifact-audit-badinterp.json`, `dt22-candidate-badinterp.efi`,
QEMU bad-interp config/log/result, and the blocked `-badinterp.fat`.
The `-x` audit outputs were recreated for the fixed candidate; nothing
installed came from the bad-interp build.

### Fixed-candidate proof and install

Fixed UKI 244,482,560 bytes (`483078d8…`), menu 6,211 bytes. QEMU shell
(88.84 s) showed STAGED → ENTER → cmdline echo → EXEC_BASH → prompt →
`overlay` fstype → all five platform modules → clean poweroff. Systemd
and logger suites passed. Audit: kernel/DT/stub/cmdline byte-identical
to dt21, DTB still dt21-green, wrapper present + executable, checkpoint/
efilog unchanged, 5 module deps resolve. Physical USB holds dt22 with
independent verification; dt21 rollback archived; stuck-boot firmware
`9b11354b-…` preserved, slots rearmed empty and verified.

### Native result (feeds dt23)

Both dt22 native boots (#8 `512cba9d-…`, #9 `c246283a-…`; the second
archive records firmware disarm preserving the first boot's IDs) reached
the new state: preswitch log (`root_dev_mounted=yes`, both Bash and
wrapper present + executable, correct overlay mounts) and native kmsg
`KESTREL_PID1_ENTER` (~14.5 s) + `KESTREL_PID1_EXEC_BASH` (~14.75 s).
**switch_root works and the wrapper reaches its pre-exec marker.** An
earlier claim that Bash was proven exec'd was corrected: the marker is
printed before `exec`. After it, the kernel continued to ~20.6 s
`sync_state pending`, then quiet — no Bash output, no panic. The open
question became purely post-switch: silent-but-alive vs dying-silently.

## 3. dt23 — post-switch proof (writable userspace, LEDs, fstype)

Doc: [dt23 post-switch proof](../dt23-postswitch-proof.md)

Post-exec markers only; kernel/DT/stub/menu-shape unchanged. The wrapper
now prints `KESTREL_POSTSWITCH_ALIVE`, `FSTYPE: $(findmnt -n -o FSTYPE /)`,
`PID1: $(cat /proc/1/comm)`, writes `04-postswitch-alive.txt` into the
current boot's own USB log dir (survives frozen display/dead keyboard),
blinks every `*::capslock/*::numlock/*::scrolllock` LED twice with
per-LED FOUND plus START/DONE markers, then execs Bash on `/dev/console`.

QEMU (fixed `03ad7ddab04c…`): shell PASS (88 s, POSTSWITCH_ALIVE,
`FSTYPE: overlay`, PID1, FILE_WRITTEN, LED START/DONE trivially on QEMU,
EXEC_BASH, prompt, modules, poweroff; 22-byte alive file off virtual
USB), systemd PASS, logger PASS. Audit: kernel/DT/stub/cmdline
byte-identical to dt22; only the wrapper changed. Physical dt23 installed
and verified (244,486,656 bytes); dt22 rollback archived; stuck-boot
firmware preserved, slots rearmed.

Classification correction preserved in the doc: dt23 is a diagnostic boot
test, not a repair of the console/input problem; earlier wording calling
it a fix or claiming the three checks exactly locate the fault was
retracted. Blinking proves the LED output path for the identified device,
not key input or an interactive shell; the alive file proves writable
live userspace regardless of screen/keyboard.

## 4. dt24 — keyboard dependency repair + true systemd text boot

Doc: [repair](../dt24-systemd-text-repair.md) ·
Result: [native text success](../dt24-native-text-success.md)

### Repair

- Numbered patch `0019-diagnostic-keyboard-i2c9-dependencies`: restores
  the configured keyboard's existing fixed 3.3 V rail and GPI1 DMA
  provider, removes only I2C9's dead ICC properties. Bus voting skipped
  diagnostically; local bring-up, not upstream ICC solution.
- Compiled DT limited to four properties. GEM/display/PCIe/NVMe disables,
  voltages, GPIO/IRQ, DMA channels/mask, IOMMU, and the dt21 USB repair
  unchanged.
- I2C-HID core + OF frontend + generic HID packed and early-loaded, with
  a new independently tested module gate.
- New `kestrel_text` hook, inert unless `kestrel_textboot=1`: stages a
  local getty-based diagnostic login into the RAM overlay, selects
  multi-user target, masks SSH/SDDM. Squashfs and account/password files
  untouched. The shell is intentionally unauthenticated like the earlier
  PID1 recovery shell but now a child of normal systemd/getty, not PID1 —
  not a production login configuration.
- Real interactive Bash startup writes `06-text-startup.txt`; entering
  `kestrel-proof` writes `07-typed-command.txt`, both gated on validated
  USB mount + exact boot ID + ancestry + marker. No arbitrary keystroke
  capture.
- Menu: 11 entries, default #8. Entries 8/9 use normal init, systemd
  multi-user, explicit VT. #8 quiets flooding; #9 verbose + confirmation.
- Logger/checkpoint binaries and PID1 wrapper byte-identical to dt23.
  Firmware capture still bounded and separately enabled.

### CRLF menu-line-ending failure caught at handoff (not shipped)

The first independent readback rejected CRLF menu line endings produced
by host Python. Evidence preserved; only that menu normalized to LF.
Equivalence to the native source proven against the QEMU-passing config;
the generator now explicitly emits LF; fresh verification passed every
critical file and menu assertion. Receipt:
`dt24-menu-newline-audit.json` (6,059 → 5,955 bytes, CRLF→LF only,
UKI unchanged).

### Validation

New board gate: dt23 RED (rail/ICC/DMA) → dt24 green; old USB gate still
green. New input archive gate: dt23 initramfs RED → dt24 green. Packed
hook chroot fixtures (inert flag-off, native VT, virtual serial,
invalid-console rejection) pass — fixtures mock the mountpoint, not
native evidence. Forward/reverse patch + DT whitelist pass. Live UKI
+ provenance audit pass; logger code unchanged.

Virtual acceptance (corrected default-entry EFI/systemd/getty, v2 run with
anchored prompt predicate after the first run matched a menu line as a
prompt and sent too early — retained as failed harness evidence): actual
serial input, recovered startup/typed-proof files, active multi-user,
required runtime modules, userspace journal, normal shutdown. The initial
`ttyAMA0` wait resolved during device coldplug, not a candidate failure.
Disposable EFI regression (flag-off / no-USB timeout / persistence in a
new VM process / refusal to overwrite) made zero physical firmware
writes. Read-only reviews and packed-hook/predicate fixtures pass.

Installed UKI 244,503,552 bytes
`4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02`;
menu 5,955 bytes `261ca611…`; 11 entries, default #8. Physical target
re-resolved as Kingston DataTraveler FAT32 KESTREL_A64; only UKI + menu
updated, bootloader/squashfs rehashed unchanged. Four owned slots read
empty; no firmware clear/write from Windows. Rollback
`usb-before-dt24-20261017T142607086Z` retained (dry-run only).

### Native milestone

Native boot `9c31cbbd-…` (2026-10-18, hash-verified archive
`native-dt24-9c31cdbb-…`): **normal systemd, interactive Bash on
`/dev/tty1`, working command-input path.**

- `06-text-startup.txt`: `KESTREL_BASH_STARTED`, PID1 `systemd`, root
  `overlay`, child `bash`, TTY `/dev/tty1`, multi-user + USB logger.
- `07-typed-command.txt`: `KESTREL_TYPED_COMMAND_OK`, same boot ID.
- Kernel: `hid-over-i2c 048D:83DB Keyboard` at `0x3a` on `a84000.i2c`
  (~9.43 s). Internal I2C keyboard positively bound (earlier boots had
  only gpio-keys + receiver). Per-device keypress origin is *not* logged;
  attribution to the built-in keyboard specifically rests on owner
  observation, not captured device events. No keylogging added.
- Journal: getty started, multi-user reached,
  `15.274 s (kernel) + 25.511 s (userspace) = 40.786 s`. Status
  initializing → running → stopping during poweroff.
  `systemd-logind: Powering off…` + `systemd-shutdown: Syncing…`
  captured; final kernel power-down line absent — full poweroff not
  independently established.
- All four owned firmware records belong to this boot ID; exported and
  preserved, not cleared/rearmed.

FAT housekeeping preserved honestly: kernel reported an
improperly-unmounted volume; read-only `chkdsk E:` exited 0 with no
problems; `fsutil dirty query` still reported Dirty. No `/f`/`/r`,
repair, format, or boot-file change. Early journal/FAT timestamps use a
fallback epoch corrected at PMIC RTC registration — boot ID + monotonic
kernel timestamps + systemd duration establish chronology, not file
dates. This closed native bootloader/live-USB/overlay, real switch_root
into systemd, Bash startup + typed command, I2C-HID binding (combined
repair, not per-change attribution), and bounded persistent evidence. It
did not close graphics, thermal safety, touchpad, networking/audio,
USB completeness, or distribution work (ranked list in the native doc).

## 5. dt25 — software-graphics candidate: rejected image, lifetime fix, true dt24 recovery, dt25b thermal text

Doc: [in-progress candidate](../dt25-software-graphics.md) ·
Thermal: [dt25b check](../dt25b-native-thermal-check.md)

Strategy from accepted dt24 text: keep dt24 as fallback; first
investigate the already-proven `simpledrm` firmware-framebuffer path with
software rendering rather than enabling the reset-associated
GEM/GPU/GMU/MDSS graph. Establish SoC-temperature observation before
any graphical attempt (dt24 captured only a battery thermal zone, not CPU
safety).

### Gates and baseline

Frozen dt24 source/DT/UKI/initramfs/input/USB closure and unchanged
logger contracts (`dt25-baseline.json`; frozen sources under the build
baseline). Fail-closed `simpledrm` + temperature preflight with synthetic
fixtures: 17 policy checks green after an observed missing-module RED.
No trip/fan/clock/voltage changes, no firmware writes. Conservative
experiment stop 80 °C; missing/invalid temperature data must prevent
graphics, never normal boot. TSENS + KWin 6.7.5 / Plasma 6.7.5 / Mesa
26.2.4 / SDDM requirements reviewed against pinned sources and rootfs.

### Review counterexample chronology (all preserved, none deleted)

- Predecessor batch (`deleg_e70b62e2`): corroborated two-TSENS + normal
  SDDM/logind software-render route; its stale `slim3-keep.dts`
  disabled-rail claims explicitly rejected for the dt24 baseline; its
  90 °C / few-sensor suggestion did not replace the conservative
  80 °C / derived-CPU-cpuss policy.
- Parent reruns exposed the first graphics GREEN as invalid: thermal
  board's 52 clauses reproduced, but valid kernel-shaped thermal/DRM
  class symlinks were rejected; under the actual WSL command, 10
  attempts → 1 failure + 2 errors + 6 skips, supervisor OK with 8
  skipped on Windows-only root paths. Receipt
  `dt25-parent-20261018T071355462077Z-receipt.json` (parser error
  corrected from actual checker stdout, no rerun/overwrite).
- Spec review `deleg_7e5a0933`: REQUEST_CHANGES from both reviewers at
  spec; quality not attempted. Counts reconciled (52 board clauses, 22
  mutations, 11 policy checks); evidence-reuse and graphics-safety gaps
  recorded (`dt25-review-wave1-verdicts.json`).
- Fix wave `deleg_b4595d51` (immutable tagged evidence helpers, real
  sysfs-link compatibility without weakening identity, genuine
  Linux staging/tests, gate ordering, owned bounded cleanup): parent
  reran **71 guard + 14 staging + 16 supervisor = 101, zero skips**.
  Receipt `…073038735715Z`; failed receipts intact.
- Renewed staged review `deleg_33e1ed91`: thermal spec+quality PASS;
  graphics REQUEST_CHANGES at spec (preserved-state rollback, strict
  overlay-FSTYPE proof with explicitly packed helper deps).
  `dt25-review-wave2-verdicts.json`.
- Parent reproduced the blocking rollback path: forcing the first
  graphics-copy failure with existing text stage + SSH/GUI masks deleted
  all three text helpers and four inherited masks while returning
  success (`dt25-parent-20261018T073250139286Z-ordering-rollback.json`).
  Minimal `systemd-analyze --root … verify` did **not** reproduce a
  suspected multi-user ordering cycle — not labeled a defect.
- Focused wave `deleg_277a9e45`: parent reran
  **71 + 19 + 16 = 106, zero skips**; the unchanged rollback reproducer
  now records no lost helpers/masks. Receipt `…074415894485Z`. Final
  graphics review `deleg_37cb82f3` spec+quality PASS
  (`dt25-final-component-review.json`). Thermal component PASS.
- Sole integration/build worker `deleg_c0d07a2` / `sa-0-e3835966`:
  first wrapper attempt ran `bash -n` on a Python file (failed record
  preserved; language/exit-status checks corrected before the build).

### Rejected dt25 image (do not boot)

Real private UKI built at `/home/builder/uki-v2-dt25`
(`testing/boot-failure/dt25-candidate.efi`): **244,421,120 bytes**,
`9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f2aa413599fb56b36d2a413499fb`.
Parent verified 13/13 provenance (PE kernel/stub/HWIDs/base-cmdline/
uname, exact dt25 DTB, new initramfs, source hashes, unchanged dt24
UKI/SFS). 106-test zero-skip component run; 66 validation clauses
(32 graphics), 52 board + 11 policy checks (counts parsed from the real
audit); true-chroot packed findmnt/mountpoint; staged
multi-user/default/graphics unit check exit 0 with docs checks disabled
(first exit 1 was missing man tooling, not an ordering cycle).
**Not accepted for native/media.** Independent reruns (24 platform-gate
+ 10 packed = 34, zero skips, real chroot closure, flag-on/off latehooks;
`dt25-fix-parent-20261018-084409-packing-preservation.json`) left all
seven archived JSON hashes and the candidate hash unchanged.

EFI text case A passed with typed proof and observed VM poweroff.
Recovered case B genuinely passes: Python executes/imports, the real
guard reports missing CPU sensors/DRM and refuses GUI, preserving text
and masks — absent-hardware refusal proof, not native thermal/pixel
acceptance.

**Confirmed blocker, case C:** in raw serial
`dt25-efi-graphics-fw-off-v2.log:555-586`, both owned fake-payload units
were active (parent PID 1147, child PID 1169). SIGKILL delivery returned
0; the parent went failed/PID 0 but the child stayed active/PID 1169.
`PartOf=` alone did not enforce death cleanup. The recovered JSON stays
failed; no inactive-child shortcut accepted.
`dt25-efi-parent-verdict.json` records the independent decision.

### Lifetime-binding fix and focused contract tests

Wave `deleg_87a89a3f` changed only the two diagnostic units: the private
child gained `BindsTo=` (keeping `After=`/`PartOf=`); the parent removes
only the owned launch marker in `ExecStartPre`/`ExecStopPost`. Parent
reran the **16 focused contract/cleanup tests, zero skips**
(`dt25-lifecycle-parent-contract.json`) — static/private-fixture checks,
**not** actual SIGKILL proof. Read-only unit review `deleg_03f10f91`
returned spec+quality PASS; its one minor note (dead no-op in the test)
deferred as non-blocking.

### Rebuild as dt25b, exact-image tests

Fresh build/prep wave `deleg_869808bc` produced `/home/builder/uki-v2-dt25b`
(244,424,704 bytes, `b535444f8a3560b602d2a8549a35389d3914a8b8b8b8b8b8
b40a11753`) + `dt25b-candidate.efi` / `dt25b-artifact-audit.json`; parent
verified PE sections, source hashes, old-artifact preservation. The
prepared EFI harness needed three parent-found repairs (missing Enter on
sends, `;try:` one-liner, MainPID string-vs-int) — each proven from guest
output, fixed minimally, re-validated (`bash -n` + payload compile).
Final v5 run (`dt25b-efi-fw-off-v5`) fully green: case A 36/36 with typed
proof and observed VM poweroff; case B+C 50/50 with real Python guard
refusal on missing CPU sensors/DRM, private SDDM never started, and
proven SIGKILL auto-cleanup (parent failed/PID 0, child auto-
inactive/PID 0/gone, launch marker absent, 09 USB evidence valid). The
old failed `9c1abc4f…` image stays archived and rejected for native
handoff. No physical USB or firmware changes in this span.

### Handoff correction: the true dt24 recovery

Read-only inspection during native-log review exposed that then-#8 was
**not** an untouched dt24 fallback: #8 and #10 both referenced
`/EFI/Linux/kestrel-live.efi`, which then contained dt25b. Menu text
retention is not artifact identity. The real archived dt24 UKI
(`usb-before-dt25b-20261018T110101253Z/kestrel-live-dt24.efi`,
244,503,552 bytes, `4fca3315…`) was restored as a separate hash-verified
file `E:/EFI/Linux/kestrel-live-dt24.efi` and a selectable **#2 text
recovery** entry. The cleaned menu defaulted to **#1 dt25b text** (same
native-tested image/cmdline); #3 Ubuntu control; #4 firmware exit.
Actual GRUB syntax, 11 menu contract tests, cache flush, independent
device rehashes passed; prior logs and unchanged payloads preserved
(`dt25b-menu-cleanup-20261018T142458148359Z/`). Also retracted:
`kestrel-proof` does not print temperatures (separate status samples do);
its `revision=v2-dt24` names the inherited helper, not the UKI; no
firmware clearing/rearm occurred in preparation.

### dt25b native text + CPU readings (real hardware, graphics off)

Owner booted then-#10, typed `kestrel-proof` without deliberately
waiting; the command still saved complete typed proof. Boot
`6a63f6cc-…`: systemd PID1, writable overlay, Bash/`/dev/tty1`,
multi-user, USB logger; cmdline `kestrel_graphics=0`, textboot on,
`efi-pstore.pstore_disable=1`, no firmware-logger opt-in.

**62 complete samples × all 20 required CPU/cpuss sensor types = 1,240
CPU readings, 30.2–36.5 °C**, uptime 17.80–115.66 s, 16 initializing +
46 running state samples. Native journal startup 43.020 s (15.240 +
27.779). No panic/Oops/BUG/lockup in the parent-scanned kernel stream
(does not cover post-capture). Line-by-line independent parsing confirmed
counts/identities/bounds/min/max. Archive
`native-dt25b-6a63f6cc-…-20261018T141554648Z` (11 files, 428,663 bytes,
source-before/source-after/archive SHA256 per file). Firmware reader:
all four owned slots unchanged from old dt24 boot `9c31cdbb-…`, zero
writes. Read-only CHKDSK exit 0; dirty flag still set; no repair. Both
read-only reviews (`deleg_1364f870`) complete; no captured boot/service
failure blocks another text-only test. 120-sample logger-finished marker
absent (62 recovered); partial capture is not automatically a crash.
Two successful tty1 getty exits/restarts observed, cause unestablished —
not labeled crash or proven shell failure. Clean hardware poweroff and
full native guard provenance / software-Plasma pixels still open;
repeat text-only, not graphics.

## 6. dt26 — native graphics repair, exact-image proof, file-only handoff, desktop

Doc: [repair state](../dt26-native-graphics-repair.md) ·
Result: [desktop milestone](../dt26-native-desktop-success.md)

### Trigger

Owner booted cleaned-menu #1, entered `kestrel-proof`, waited 90+ s, saw
no further progress, authorized fixes, and requested a progress estimate.
Waiting is not a desktop-launch trigger. New native boot `7f84303a-…`
saved complete typed proof (systemd PID1, overlay, Bash/tty1, multi-user,
USB logger) with actual cmdline `kestrel_graphics=0`. All 100
initializing/running thermal samples held all 20 required CPU/cpuss
readings (37.7–47.9 °C); the final `stopping`-state fragment missed four
readings with no out-of-bounds value — raw collector's all-samples
failure/exit 1 preserved, not silently weakened
(`parent-retest-verdict.json` distinguishes accepted live samples from
the shutdown fragment). Orderly shutdown + sync at monotonic 177.655 s;
final hardware power-down unproven. The earlier collector attempt
(`…150439253494Z`) with an obsolete fixed-#8 menu audit raising IndexError
after raw archival is preserved: host collector defect, not native crash.

The milestone rubric was recalculated without inflating for an unbooted
GUI: ~65% for the first usable Lenovo live desktop (63.0 weighted
points), ~35% for a maintained general-ARM64 release (35.05 points).
Subjective milestone weights, not code/time completion or daily-driver
readiness
(`research/evidence/froodzos-publication-20261018/progress-estimate-dt26-preparation.json`).

### Implementation wave `deleg_58c7d332` (disjoint ownership)

- `sa-0-f4d83615`: read-only native-log / integration scout. No edits,
  builds, or VM while writers active.
- `sa-1-19ca1857`: session contract writer — graphics supervisor +
  focused tests/evidence only. Verify actual systemd/logind properties
  before fixing suspected numeric-User / Name / absent-UID / empty-
  Wayland-Display handling. Query/list/detail errors must refuse GUI,
  never vacuous empty baseline. Strict ownership, thermal bounds, 180 s
  runtime, 25 s cleanup, foreign-session safety.
- `sa-2-e5a4b363`: observability writer — root USB logger, text
  proof/bashrc, parent graphics-unit output directives, focused tests.
  Explicit text-only vs requested-GUI messages, real CPU readout,
  exact bounded preflight/cleanup persistence through the validated USB
  logger; supervisor stays `/run`-only. Atomic last-good writes,
  byte/time budgets, startup/typed markers, normal boot on logging
  errors; extend logging for GUI opt-in only long enough to cover bounded
  cleanup.
- Parent owns shared docs/ledger/review/integration/media handoff. No
  writer may alter kernel/DTB/SFS/accounts/USB/firmware or publish.
  No secrets/private-keys/shadow. Dedicated CachyOSBuilder only; Kali
  untouched.

### Storage gate and compaction

After the first dt26a1 EFI A run exposed the missing harness markers, the
next fixture attempt was refused by the physical D: reserve gate. Free space
was 11,831,713,792 bytes. Removing 36 superseded in-guest `uki-v2-*` build
directories (retaining dt24, dt25b and the current dt26a1), vacuuming the
journal, guest trim, full WSL shutdown and offline `Optimize-VHD -Mode Full`
raised physical D: free space to 27,464,921,088 bytes. These are about
11.8 → 27.5 **decimal GB**, not GiB. The separate 10 GiB post-incremental
reserve was not reduced. Guest `fstrim` alone did not return space to D:.

This cleanup was not proof that every historical build directory survived:
the later audit discovered the old rejected dt25 golden path was missing.
It was restored byte-identically from the retained host archive, as recorded
in the rebuild chronology below. Failed-run receipts and the protected native
evidence/rollback contracts were not silently replaced to allow a rerun.

### Counterexample-driven review chronology (all preserved)

Initial session/observability sources + reported green tests were
**not** accepted for build/media. Formal reviews `deleg_f2aba956`
returned **REQUEST_CHANGES for both at Stage1**; quality not run
(`dt26-review-wave1-verdicts.json`).

Parent production probes then reproduced concrete failures
(`dt26-review-wave1-parent-findings.json`,
`dt26-parent-probe-20261018T151812044665Z.json`,
`dt26-parent-session-probe-20261018T152006240116Z.json`):

- Session: empty/partial successful session queries fail open; missing
  `Remote` treated as local; structured pre-GUI atomic pass preflight
  capture missing; real systemctl comma-property vs loginctl repeated-
  flag grammar conflated.
- Observability: partial/nonempty JSON overwrites valid last-good;
  fixture symlink outside whitelisted source followed/copied (no real
  secret read); size-check/copy race (32-byte cap → 130-byte dest);
  260 samples with no monotonic wall-clock mechanism (not a 260-s
  bound); Bash octal/malformed sensor strings abort/misreport
  (`08000`, `-`, `--1`, `1-2` probes); test entrypoint overwrites fixed
  evidence.
- Real-schema justification accepted: frozen SFS loginctl/systemctl
  client bytes equal builder clients used for genuine API probes;
  `chvt`, `timeout`, SDDM/KWin/Plasma, dbus-run-session, SDDM PAM/session
  paths present in frozen SFS (presence/client-byte evidence, not runtime
  closure or rendering). Prior reviewers' nominal PASS/APPROVED verdicts
  explicitly **not** accepted where they waived monotonic/bounded-call
  and IO-failure requirements despite reproducible counterexamples.

Harness preparer (87 reported parser checks) went parent Stage1 RED
(`dt26-parent-harness-probe-20261018T154758731647Z.json`): wrong-
filesystem/post-allocation reserve bug, `graphics0→1` patch never
changing the token, echoed-marker acceptance, trailing-newline identifier
acceptance, late collision check; shared-extraction and standalone-lock
gaps by source review. Corrective writer `deleg_f7d944ec` owned only
harness/parser/fixture/test files. Parent reran corrected
parser/harness: **163 passed, zero failures/skips** — still not enough
for a VM. Exact-code probes then showed: foreign lock contention falsely
called inherited ownership; BC disk gate subtracting an already
allocated FAT again; injected log-open failure leaving an already created
fake QEMU process uncleaned
(`dt26-parent-harness-fix-verification-20261018T161701680316Z/result.json`;
in-memory mock, not a real orphaned VM). `deleg_1f97c818` owned the
focused lock/incremental-capacity/process-lifetime correction.

Corrective wave `deleg_05bd294e` (narrow IO/bounds, private mount-
namespace E2E fixture safety) answered the isolated production probes:
supervisor treating file-fsync EIO as success; observer accepting
`detail:null` over last-good and reading its old destination without a
byte limit; a requested 2-s loop taking 4.1009 s (stale per-call timing),
4.1049 s (TERM-resistant ordinary command), 3.1119 s (missing timeout);
unwrapped startup/final and intermediate filesystem commands; namespace
setup not failing fast on required mounts. Parent reran all three
session suites: **49 run, 49 passed, zero skipped**
(`dt26-parent-fix-verification-20261018T160145495817Z/`) — fixture
verification, not native graphics.

Build/auditor tooling also **unaccepted** despite 28/28 gate checks:
parent reproduced acceptance of LF-suffixed literals/wrong source
identifiers and a premature `passed:true` after a copy failure; source
review found a different lock from the shared pipeline and an SFS path
the actual EFI schema rejects
(`dt26-parent-artifact-gates-parent-20261018T163419914719Z.json`).
`deleg_fe998055` corrected only those tooling files, explicit
environment/provenance, storage accounting. No reviewed source manifest
or build authorized yet.

Frozen-runtime work: first a 16,209,062-byte subset proving
chvt/timeout, but other clients still on builder-library fallback, Qt/KDE
transitives unstaged, Python without encodings. `deleg_ad4fb199`
completed hermetic recursive closure in a new subset; no compositor may
run. The newer subset: **18/18 parent-reexecuted core/PAM ELF loader
checks with no host fallback**, isolated frozen Python stdlib + Bash
5.3.20 clock-feature checks; SFS byte matches for SDDM/KWin/loader
(`dt26-parent-runtime-verification-20261018T162447162091Z.json`). Frozen
Bash really provides `BASH_MONOSECONDS`; wall-clock fallback not
required. Snapshot supervisor imports were of the older source hash and
do not approve pending IO changes.

Qt5 generic `sddm-greeter` broken, but the source image also contains
`sddm-greeter-qt6` — treating the generic path as the required target
would be premature. `deleg_defd0ac0` resolved shipped defaults and the
Qt6 candidate without launching a display. Parent re-executed five
SDDM/Qt6-greeter/helper loader checks + documented config-only
`--example-config`, all exit 0, Qt6 greeter bytes match SFS
(`95664832…`; `dt26-parent-sddm-verification-20261018T164002546367Z.json`).
No package/config repair needed. Greeter-suffix selection unproved:
static availability is not a login claim. Scope clarified: Plasma's
selectable session is Wayland-only; stock SDDM display-server default is
`x11`; separate layers, no X11 Plasma fallback added. Frozen autologin:
`User=live`, `Session=plasma`, desktop Exec
`/usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland`.
Actual display/PAM/QML/DRI behavior still required the bounded native
trial.

### Final green reruns before build (fixtures, not native proof)

- Supervisor final: parent reran the corrected supervisor's four suites,
  **55 run, 55 passed, zero skipped**, source SHA256
  `7ece0b64b70df38402d4858d84ed28274c739ba85b9ec281ff1573036ea31fa9`
  (`dt26-parent-session-final-20261018T164807600438Z/result.json`;
  includes file-fsync EIO + full session-path no-start regressions).
  Formal review `deleg_bdc3212c` pending at that point; native graphics
  still not accepted. The observer's 27 green tests with monotonic/
  per-call fixes were insufficient on parent source inspection
  (unwrapped startup/final + intermediate commands, namespace setup not
  failing fast); `deleg_69e0622b` applied one bounded whole-graphics
  watchdog + checked fixture setup. Whole-logger bound vs per-journal
  timeouts and watchdog-expiry vs normal-loop-completion distinctions
  preserved. No new image/media yet.
- Logger final: parent reran all four logger suites against the watchdog
  source (`9ebf9922…`): **33 passed, zero failures/skips**, sources
  byte-identical before/after
  (`dt26-parent-logger-final-20261018T180504139204Z/result.json`).
  Lesson recorded: running with `TMPDIR` on a root-owned dir breaks
  `unshare -rm` kmsg bind (exit 45); default `/tmp` required. Formal
  review `deleg_863677f4` running. No VM/FAT/media ran.
- Harness final: parent reran completed parser/harness/lock-lifecycle
  suites: **228 checks passed, zero failures/skips**, source hashes
  unchanged, plus re-executed concrete counterexamples — a real
  unrelated lock-holder now refused, BC budgets zero new FAT allocation
  (while the same free space still refuses pre-allocation), injected
  log-open failure creates zero fake QEMU processes
  (`dt26-parent-harness-fix-verification-20261018T165133307907Z/result.json`).
  Formal review `deleg_be649d99` pending. Unit/private-fixture checks;
  no real FAT or VM ran.
- Supervisor final (post-review source): **55 run, 55 passed, zero
  skipped**, SHA256
  `2ea4ae312dde6ee316a526fc7e6c08f276f0aa70884f056966cc20209a9ebf05`
  (`dt26-parent-session-final-20261018T190138483352Z/result.json`).
  Verified from the file; this is the exact hash named in the task.
  Fixture-only; `native_graphics_validated:false`,
  `supervisor_main_executed:false`.
- Artifact gates final: 48/48 preflight checks green on the corrected
  tooling (LF-literal, wrong-path, shared-lock-only, canonical-SFS-guard,
  finalization-commit-order, storage-future-bytes-only,
  explicit-env-compression among them).

### Rebuild / audit chronology: dt26a1 → dt26a2 → dt26a3

Parent-approved 31-source manifest
(`dt26-source-manifest-v2-dt26.json`, all hashes live-verified; reviewed
source manifest with spec+quality PASS from parent reviews
supervisor + logger + harness + build-tools; independent reruns
55+33+228+48 green, zero skips).

- **dt26a1**: canonical build, UKI 244,398,592 bytes `b81479e5…`,
  initramfs 191,544,368 bytes `09062da5…`, kernel/DTB/SFS frozen. Audit
  passed-true, host copy `dt26a1-candidate.efi` readback-verified, old
  artifacts preserved. Gate suite 48/48. VM case A
  (`dt26-efi-dt26a1-a`, 258 s, orderly poweroff) booted healthy but the
  harness reported false: two harness-side drops, both present in dt25b
  and lost in the dt26 rewrite — (A) the guest command never echoed the
  boot ID to serial (`bid` stayed `unknown`, so every content check read
  empty), (B) both menu templates lost the machine-readable
  `KESTREL_EFI_MENU_REACHED` echo. Parent restored both (2 template
  lines + 1 send line mirroring BC); a patch-tool escape corruption on
  the adjacent send line was caught and repaired, od-verified
  byte-identical to the proven pattern. New hashes ledgered; prior
  harness approval basis marked superseded by this delta. Rerun
  (`dt26a2` prefix) ready but blocked on D: space (above).
- **dt26a2**: rebuilt prefix after the two-line + one-line harness
  restoration. Fixture UKI `b81479e5348afc62369bc443ae35041380f393f9de6a0fe9ff251d2523716b83` (fixture record; do not confuse with the final
  dt26a3 hash). Case A passed-true (278.5 s, orderly poweroff, 40/40
  checks, QEMU exit 0). The BC leg for this prefix has only a serial log
  (`dt26-efi-dt26a2-bc.log`) with no result JSON — not quoted as a pass.
- **dt26a3 (final exact image)**: UKI **244,398,080 bytes**,
  SHA256 **`5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26`** — verified by direct file hash of
  `dt26a3-candidate.efi` and matching the fixture record plus both EFI
  result JSONs. Initramfs
  `1e26d5fcf6be34e32eea8d44b1751ada71b905ae2da6d36b82528568d0a00316`;
  SFS unchanged `5041e7d0…` (1,748,525,056 bytes). Final supervisor
  source inside is the `2ea4ae31…` hash above.

### Execution-only CRLF failure and preserved audit retries

The A-passed `dt26-efi-dt26a2` prefix still used the dt26a1 image. Its BC
serial log exposed the supervisor's CRLF shebang: the kernel/env could not
execute `python3` followed by a carriage return. Python import tests had
passed and did not exercise that interpreter lookup. A scan of all 31
manifest sources found CR bytes only in that supervisor. Removing CR changed
43,712 → 42,725 bytes and the source hash to
`2ea4ae312dde6ee316a526fc7e6c08f276f0aa70884f056966cc20209a9ebf05`.
The manifest was updated; the final LF bytes later passed all 55 session/IO
fixture cases with zero skips. This is distinct from the earlier dt24 menu
line-ending problem and the dt22 wrong-interpreter path.

A real dt26a2 rebuild followed the LF correction, but its audit required the
old rejected dt25 golden EFI path removed by cleanup. The retained host copy
was restored and independently hash/size verified (244,421,120 bytes,
`9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb`).
The failed audit directory then correctly refused reuse. It was preserved;
a fresh dt26a3 build/audit was created instead. The final dt26a3, not the
A-passed dt26a2 *harness prefix*, is the accepted image used in both final
EFI tests and the later file-only USB handoff.

### Final exact-image disposable EFI tests (same bytes later installed)

- Case A text-fallback (`dt26-efi-dt26a3-a`, 270.12 s / 600 s deadline,
  QEMU exit 0, orderly poweroff): **passed-true**. Systemd, overlay,
  multi-user, typed proof (`KESTREL_TYPED_COMMAND_OK`, helper v2-dt26),
  all platform + HID runtime modules, userspace journal, graphics unit
  never staged, no SDDM process, `kestrel_graphics=0` in cmdline, 09
  evidence valid.
- Case B graphics-refusal + C unitgraph
  (`dt26-efi-dt26a3-bc`, 362.17 s / 800 s, QEMU exit 0, orderly
  poweroff): **passed-true**. Text preserved under graphics request;
  B markers done; Python exec OK; real guard refuses closed (missing
  CPU sensors/DRM, no fake temps, private SDDM never started, stock
  masks preserved, no GUI launched); C fake parent active before,
  fake child active before, SIGKILL sent, parent failed/PID 0, child
  auto-inactive/gone, stale marker setup → pre-cleared → absent after,
  owned fake cleanup done, no host services. `c_detail:
  child-inactive-gone-marker-absent`.

### File-only handoff (physical USB, read-only before/after)

Tooling `update-dt26-usb-handoff.py`: dry-run then apply, both
receipted. Scope strictly `EFI/Linux/kestrel-live-dt26.efi` +
`boot/grub/grub.cfg`; zero firmware writes; no filesystem repair.
Physical identity re-resolved (Kingston DataTraveler 3.0, KESTREL_A64
FAT32) before and after; protected files equal; all 59 prior logs
preserved unchanged; `Write-VolumeCache` exit 0.

- Dry-run (`dt26-usb-handoff-dryrun-20261018T193100Z/`): success-true,
  zero files written.
- Apply (`dt26-usb-handoff-apply-20261018T193000Z/`): success-true, two
  files written.
- Resulting menu (3,424 bytes,
  `1249291c07d42c4b07c456dfe4fb93c4ab8c792ec3b36672bde33be8a27ac935`):
  #1 dt25b text + CPU logging (default), #2 dt24 text recovery
  (previous image), #3 Ubuntu Concept control (Try only), #4 dt26
  BOUNDED graphics diagnostic (opt-in), #5 firmware exit. 8 contract
  tests (valid candidate + 7 negative rejections: crlf, extra-entry,
  firmware-optin, graphics-in-text, missing-pstore-disable,
  wrong-console, wrong-default) plus GRUB script check exit 0.
- Kestrel contracts unchanged: bounded capture, opt-in logger flag,
  checkpoint slots, USB logger behavior, no rearm, no silent repair.

### Native desktop observation (2026-10-19)

Archive `native-dt26-desktop-20261019T051414117233Z` (USB read-only):
**25 original files, 1,015,936 bytes**, every copy hash matched
before/after; no USB writes, firmware access, repair, or deletion.
On-device dt26a3 UKI, dt25b/default fallback, dt24 recovery, menu, and
shared SFS all matched the verified handoff bytes.

Owner message: **"Goal achieved Desktop loaded!"** — accepted as
user-observed desktop pixels. Both native boot IDs archived
independently:

- `54368727-c22b-4b6c-91b6-428b39dd2cbe`: 142/142 complete valid
  20-type CPU samples, 38.5–48.7 °C; deadline reached; private SDDM
  stopped, owned session absent, tty2 getty active. One redundant
  terminate-session call returned 1 after the session was already gone.
- `7f05d7e0-f801-4316-b55c-8daa08d353c5`: 67/67 complete valid 20-type
  samples, 36.9–48.7 °C band per boot table (36.9–46.3 °C in the second
  boot's own record); captured service stopping before the full window;
  no saved 09 cleanup snapshot — do not infer hang or completed cleanup
  from that absence.

Both boots requested graphics and passed the real 20-type CPU/cpuss +
DRM preflight (character device `card0`, driver `simple-framebuffer`,
connected `1920x1200`). Both accepted the real live user's Wayland
session: journal shows SDDM selecting `plasma.desktop`,
`startplasma-wayland`, KWin using DRM; Xwayland reports software
fallback. **No accelerated-GPU claim.** Temperature visibility +
bounded-run monitoring proven, not fan/cooling or sustained-load safety.
KWin framebuffer/EDID and Xwayland warnings remain on record; they do not
erase the user's visible-desktop observation. Final physical poweroff
remains unproven.

Attribution honesty, enforced by `parent-verdict.json`: the initial
collector wrote `user_observed_desktop:true` per boot. That is too
strong — the owner's report was not uniquely correlated to either boot.
The per-boot pixel flags are superseded; raw archives and measured values
unchanged. What two boot IDs corroborate: real preflight and real
session acceptance on hardware. What exactly one owner pixel report
cannot do: assign pixels to a unique boot ID.

Follow-up owner observation (input/network): **keyboard and external
mouse work; built-in touchpad does not; Wi-Fi was not usable.** USB-C
Ethernet adapter and Android USB-tethering option available. These are
owner observations, not newly logged device tests.

## 7. Networking and Hermes prerequisites (current, unproven paths noted)

Doc: [desktop milestone](../dt26-native-desktop-success.md) (prereqs
section); receipt `native-network-prereqs-20261019T052527331246Z.json`.

- Both recovered NetworkManager captures enumerate only loopback `lo`.
  No usable Wi-Fi/Ethernet or Internet proven.
- Read-only kernel/SFS check (exact 7.3.0-rc3, no native network test):
  `r8152`, ASIX (`asix`, `ax88179_178a`), `usbnet`, CDC Ethernet/NCM,
  RNDIS-host (plus CDC MBIM, IPHEth) compiled and present in the frozen
  live SFS; tools `python3`, `nmcli`, `curl`, `ip`, `getent`, `sudo`,
  `timeout` present; **`git` absent**. An earlier receipt misclassified
  the Python symlink by reading its target instead of its path; the
  fresh receipt corrects that without altering the old file. Driver
  presence does not establish adapter-chipset support, link, DHCP, DNS,
  or TLS.
- Two prerequisites before Hermes directly on native Linux (official
  platform docs list Linux/aarch64 source install as supported; links in
  the desktop doc): (1) connectivity — candidate path is the USB-C
  Ethernet adapter cabled to the router before booting existing entry 4,
  with Android tethering as the alternative; no kernel/DTB/image change
  needed to try already-shipped drivers; untested adapter promise made
  to no one. (2) Persistent workspace + suitable session — the current
  image is a volatile 512 MiB live overlay with a hard 180-second
  graphical diagnostic; a source install there may run out of space and
  would not survive reboot. Scope a separately persistent USB work
  environment first; do not write internal storage, format the stick,
  copy Windows credentials, or silently remove thermal/deadline
  safeguards. **No native Hermes installation performed yet**; this
  chat's tools run on Windows, not inside the native boot; installing
  into the WSL builder is not a substitute for a native install.
- Touchpad/Wi-Fi remain not-working per owner; Ethernet/tether options
  exist but are untested. Keep the native-tested dt26 diagnostic and
  both text recoveries intact.

## 8. What was deliberately not changed

Kernel Image / voltages / GPIO-IRQ / DMA channels / IOMMU / GEM /
display-clock blacklist state beyond the named diagnostic deltas; no
GPU/GEM/GMU/MDSS/clock/voltage/fan or internal-storage enablement by
implication. No account/password, SSH/SDDM unmasking, remotely exposed
root autologin, or persistent home. No private keys, shadow, or network
secrets touched. `Kestrel` boot/USB/logger contracts unchanged throughout.

## 9. Unresolved source / evidence gaps

1. Per-boot pixel attribution: one owner desktop report covers two
   recovered graphics boots. Do not assign it to a unique boot ID.
2. Input device proof: typed-command files prove a command entered
   through the native console; per-device keypress origin (built-in vs
   receiver) is owner observation, not logged device events.
3. Touchpad (`88c000.i2c` still defers on `qup-config`) and Wi-Fi: not
   working; variant/address/IRQ matching and WCN power/regulator work
   remain.
4. Networking: loopback only in captures; Ethernet-adapter chipset, link,
   DHCP/DNS/TLS, and tethering all untested. Hermes still not installed
   natively; `git` missing from the live image; 512 MiB volatile
   overlay + 180 s bound unsuited to a source install without a
   separately scoped persistent workspace.
5. Shutdown: orderly request + filesystem sync captured repeatedly;
   final hardware power-down line never captured — do not claim full
   poweroff completion.
6. Thermal: native CPU/cpuss visibility proven across dt25b/dt26 spans;
   fan/cooling control, platform trips, throttling, sustained-load
   safety, and full live-guard sysfs-ancestry validation under graphics
   remain open. Graphics was off for all dt25b temperature evidence.
7. `7f05d7e0…` cleanup snapshot absent: neither hang nor completed
   cleanup inferable.
8. dt26a2 BC leg: serial log only, no result JSON — quoted as log
   presence, not a pass. Final exact-image claim rests on dt26a3 A + BC.
9. Old dt25 `9c1abc4f…` image: archived, provenance-verified, and
   rejected for native handoff (case-C lifetime failure). Do not revive
   it as a candidate.
10. Timestamp discipline: early journal/FAT dates use a fallback epoch
    corrected at PMIC RTC registration. Chronology comes from boot IDs,
    monotonic kernel timestamps, and systemd durations — not file dates
    and not Internet time sync.
11. FAT dirty flag: read-only CHKDSK exit 0 / no problems found, but the
    dirty bit remained set with no repair performed. Preserve normal
    shutdown/eject practice; do not infer corruption from the flag
    alone and do not describe it as a clean-volume/repair result.
12. Formal reviews trailing the final green reruns (supervisor
    `deleg_bdc3212c`, logger `deleg_863677f4`, harness `deleg_be649d99`,
    build-tools gate) were pending at the recorded checkpoints; the
    exact-image VM + native results above are the acceptance basis, not
    review-promise alone.
13. Missing inputs not recovered: raw screenshot pixels behind the
    owner transcripts (transcripts matched the kernel log line-for-line
    instead), the dt26 private redacted conversation export was sampled
    only by targeted search (never copied in full), and several named
    intermediate receipts were read as structured JSON rather than raw
    hardware journals — per the task's source rules.

## 10. Artifact index (pointers, not copies)

- dt21–dt24 docs: `../dt21-usb-repeater-fix.md`,
  `../dt21-native-usb-success.md`, `../dt22-pid1-handoff-fix.md`,
  `../dt23-postswitch-proof.md`, `../dt24-systemd-text-repair.md`,
  `../dt24-native-text-success.md`.
- dt25/dt25b: `../dt25-software-graphics.md`,
  `../dt25b-native-thermal-check.md`.
- dt26: `../dt26-native-graphics-repair.md`,
  `../dt26-native-desktop-success.md`.
- Structured receipts (testing tree, read as JSON, not raw journals):
  `testing/boot-failure/dt26-efi-dt26a3-{a,bc}-result.json`,
  `testing/boot-failure/dt26-parent-session-final-20261018T190138483352Z/result.json`,
  `testing/boot-failure/dt26-parent-logger-final-20261018T180504139204Z/result.json`,
  `testing/boot-failure/native-dt26-desktop-20261019T051414117233Z/parent-verdict.json`,
  plus `dt26-parent-harness-fix-verification-20261018T165133307907Z/`,
  `dt26-parent-session-final-20261018T164807600438Z/`,
  `native-network-prereqs-20261019T052527331246Z.json`, and the USB
  handoff dry-run/apply receipts.
- Final hashes verified from files: supervisor
  `2ea4ae312dde6ee316a526fc7e6c08f276f0aa70884f056966cc20209a9ebf05`;
  final UKI
  `5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26`
  (244,398,080 bytes).
