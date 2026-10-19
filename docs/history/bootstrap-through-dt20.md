# Engineering history: bootstrap through dt20

Public-ready chronological reference. Covers initial research and builder
bootstrap through the dt20 packaging-only candidate and its native result.
Later work (dt21 and beyond) is out of scope for this document.

- Scope end: dt20 native test still fails to enumerate external USB or mount
  the live root. No desktop, systemd userspace, or full-hardware success is
  claimed here.
- General ARM64 ambition is not a hardware proof. QEMU/VM checks are not
  native success. A last visible screen line is not the cause of the next
  hang. A copied hash is not a boot proof.
- Source links below are relative from `docs/history/` in the final repo
  layout. Example: `../phase1-results.md` means the sibling docs file
  `docs/phase1-results.md`; `../../pkgs/...` means the repo `pkgs/...` tree.
  If a referenced build path has no stable public location yet, it is listed
  in the source-path note at the end of its section rather than linked.

## How to read confirmed vs hypothesis

- **Confirmed:** reproduced in a recorded artifact, log, hash read-back, or
  independent verification step named in the linked source.
- **Hypothesis (at the time):** best working explanation, explicitly marked as
  such, with the single-variable test that would confirm or kill it.
- **Retracted:** an earlier statement the records explicitly withdraw. These
  are preserved so the correction stays visible; do not reuse the old claim.
- Exact dates, sizes, hashes, and revision names come only from the records.
  Anything else is labeled as inference or unknown.

Primary phase sources:

- `../phase1-results.md` — builder bootstrap
- `../phase2-results.md` — kernel, Slim 3 DT, stubble UKI
- `../phase4-5-results.md` — image assembly, stick write, G3 failure
- `../decisions.md` — architecture and operational decisions
- `../boot-failure-diagnosis.md` — full native-failure round-by-round log
- `../firmware-logger-audit.md` — dt13 audit and HOLD
- `../logger-v2-repair.md` — dt19 bounded-logger repair and native capture
- `../dt20-usb-shell.md` — dt20 candidate and USB install
- `../dt20-native-log-comparison.md` — dt20 screen vs firmware comparison

---

## 0. Research and design (2026-10-07)

Historical design only. Nothing had been built or boot-tested yet. All gates
except G0 were UNTESTED goals.

### What the design established

The project was defined as an unofficial source-based ARM64 port carrying the
CachyOS experience progressively. Official CachyOS published x86-64 only and
its Arm request was closed `not_planned`; the design therefore never presents
the work as official CachyOS and never embeds, mirrors, or points at CachyOS
binaries. Source licenses were treated separately from the binary repository
policy.

Key constraints carried forward:

- One verified machine only: Lenovo IdeaPad Slim 3 15Q8X10 (referred to as
  83N3 in build records), Snapdragon X1-26-100, with a specific Wi-Fi variant
  that matters for device-tree and firmware validation.
- ARMv8-A generic baseline first; optimized tiers additive later, never
  replacing the baseline.
- Hardware-enablement kernel first; scheduler and optimization work only after
  stable boot.
- Firmware staged locally from the machine's own Windows installation, never
  redistributed and never shipped in a public image.
- No installer in the first milestone; no internal-disk writes, BIOS or boot-
  security changes; control test before project image; thermals monitored in
  every first-contact session.
- Builder envelope: separate native-ARM64 WSL2 distro, project-local storage,
  limited RAM and parallelism; no QEMU emulation for builds.

Architecture choices recorded as provisional or decided (see
`../decisions.md` and the design document): ALARM rootfs plus a signed overlay
repo; stubble HWID-matched UKI; FAT32 ESP plus UKI path; offline master key
plus build key with signed packages and signed databases; neutral working
identity pending a public name pick; Ubuntu Concept live image as control
only, never the project base.

Gates defined at the time: G0 source pins and evidence ledger; G0b ARMv8-A
baseline proof; G1 signed package install; G2 kernel plus DT plus stubble UKI
with QEMU smoke boot; G3 image boots on the Lenovo; G4 milestone checklist;
G5 signed-repo flow and reproducible rebuild; G6 ARM64 guest boot. G0 was
research-only done; the rest were untested.

### Retractions and limits from this era

- Broad Snapdragon or general-ARM64 language is ambition, not a result. Only
  the named Lenovo unit is above the lowest support tier.
- QEMU success proves nothing about the laptop. This distinction is repeated
  in every later gate.
- The phased plan's systemd-boot, formatter/erase, open-name, and early
  authorization assumptions were later superseded. Do not reformat media or
  restart completed bootstrap tasks from the old plan text.

---

## 1. Phase 1 — builder bootstrap (2026-10-08)

Status: all gates **PASS** in the records: preliminary G0b, G1, plus runtime
G0b confirmation deferred to Phase 2 QEMU. Nothing outside the project work
directory plus the new builder WSL distro was modified.

Source: `../phase1-results.md`.

### 1.1 Rootfs fetch and verification — PASS

- Official Arch Linux ARM endpoint served a certificate valid only for the
  apex and www names. The records document this as a SAN gap on the host's
  validation path and used an official regional mirror over valid TLS
  instead. No signature checking was disabled.
- Artifact: `ArchLinuxARM-aarch64-latest.tar.gz`, 829,367,415 bytes.
- SHA256 recorded in the phase file: `42a4eeaa...b319`.
- GPG: good signature from the Arch Linux ARM build-system key, RSA key ending
  `...BDBE6A6` with matching documented fingerprint. Verified in an isolated
  keyring under the project `keys/` tree.

Confirmed: byte count, hash, and good signature. Hypothesis: none; this is a
straight verification gate.

### 1.2 WSL import — PASS

- Imported as a separate WSL2 distro; `uname -m` returned `aarch64`.
- A custom WSL kernel was in use on the host at the time; the records note it
  was not the cause of the later network issue.
- No other installed distro was modified; the pre-existing distro stayed
  stopped.

### 1.3 Configuration — PASS with documented fixes

- Created an unprivileged builder user with passwordless sudo, set as the
  default WSL user.
- Build caps and swap configured per the design envelope.
- Full system upgrade plus `base-devel`, `git`, `debugedit`, and
  `qemu-system-aarch64`. Recorded tool versions: makepkg 7.1.0, git 2.56.0,
  QEMU 11.1.2.

Network forensics (corporate-managed host; details generalized here):

- First boot had no guest NIC after a stuck host service state; a
  shutdown and restart cycle cleared it.
- Host DHCP never issued a guest lease and an unmanaged host component wiped
  manual configuration mid-boot. Fix: `systemd-networkd` made the authoritative
  owner of the guest Ethernet interface with a static address, gateway, and
  DNS resolvers. Fragility noted in the records: if the host ever recreates
  the virtual switch with a different subnet, the one network unit file must
  be edited.
- DNS: the host tunnel stub plus a public fallback, with generated resolver
  and hosts files disabled in WSL config for persistence.
- Mirror list pinned to two working regional HTTPS mirrors plus a geo-redirect
  last, with hosts-file pins as DNS-independent backup.
- Persistence verified by terminate plus cold start: user, swap, IP, route,
  and DNS intact.

This is operational history, not a claim about any other network.

### 1.4 ARMv8-A baseline — preliminary PASS, runtime deferred

- Build flags set the explicit ARMv8-A baseline for everything built locally.
- Compiler default confirmed as ARMv8-A for the toolchain.
- Binaries carried no ARMv8.3-plus mandatory feature bits.
- Final confirmation deferred to a runtime boot under
  `qemu-system-aarch64 -cpu cortex-a53` (Phase 2).

### 1.5 First signed package — G1 PASS

- Generated a local throwaway build key (real offline master key deferred to
  the later phase).
- Built and signed a minimal self-authored `hello` package for aarch64 from
  the repo `pkgs/` tree.
- Imported and locally signed the build key; local package-file signature
  verification was required (`LocalFileSigLevel = Required`). This Phase 1
  check did not establish a signed repository database.
- Install completed with keyring and integrity checks; binary ran.

Deviations documented as gate-equivalent: self-authored minimal package
instead of cloning the full upstream PKGBUILD tree; compiler-default plus
build-flags plus feature-bit probe instead of the planned ELF architecture
tag read; extra hardening (mirror, resolver, and static-network work) forced
by the host network.

Phase state: builder ready for kernel, device tree, and stubble UKI work.

---

## 2. Phase 2 — kernel, Slim 3 DT, stubble UKI (2026-10-08)

Gate status: **G2 PASS** and **G0b runtime PASS**. The same kernel booted to
userspace under `qemu-system-aarch64 -cpu cortex-a53`, proving the ARMv8-A
baseline at runtime. No device claims: QEMU `virt` only.

Source: `../phase2-results.md`.

### 2.1 Pinned sources — SHA256-verified

- Kernel tree from the community hardware-enablement fork, branch head dated
  2026-09-19, recorded full commit `3f0d8691...887719` and tree SHA256.
- Stubble HWID boot stub at the merge containing the Slim 3 HWID entry,
  recorded full commit `9f11278e...12087a` and tree SHA256.
- Note: an earlier research pin was superseded by the branch head above. The
  head was a work-in-progress tree that needed five port patches below.

### 2.2 Port patches — all partial-merge artifacts in the upstream WIP branch

1. Board PMIC include file: add a missing ADC header include. Insufficient
   alone because include guards keep the local function-like macros winning;
   kept as a harmless part of the series.
2. Remote-processor core: drop an unreachable deletion-state check; the token
   exists nowhere else and the enum is complete and consecutive.
3. Platform driver merge conflict in the stop path: keep the branch-side guard
   for logical crashes still needing a stop, which also satisfies the incoming
   upstream intent.
4. Platform DSP driver: unify two stray metadata-release calls to the file's
   own context-matched helper.
5. Board PMIC data: merge duplicate ADC nodes (stale partial copy into the
   complete channel set, dual-labeled, keeping the full channel set) and use
   the local ADC macro for the virtual channel.

Build tooling note: the kernel build script also needed `bc` installed.

### 2.3 Build configuration

- Base: vendorослов(board) defconfig for the Snapdragon X platform, full
  multi-thousand-line in-tree config.
- Verified enabled: 64-bit ARM, Qualcomm platform, ACPI, EFI stub, wireless,
  display, PCIe, soundwire, HID-over-I2C families. No link-time optimization.
  Low-parallelism build per the envelope.

### 2.4 Artifacts — signed package install verified

Installed via signed package `linux-cachyos-arm64-7.3.0rc3-1`:

- Kernel Image, ~52.5 MB, SHA256 `82ec645c...27db`.
- Stubble UKI, ~52.9 MB, SHA256 `e155d12a...83c2`.
- Slim 3 device-tree blob, ~208 KB, SHA256 `656fd217...e2ff`.

UKI contents verified via stub inspector: automatic DTB slot holds the Slim 3
blob, hardware-ID section holds the board HWID JSON, command line carries the
board ignore flags plus a quiet console setting. Package signed with the Phase
1 build key; install verified keyring plus integrity. Module-install path
adjusted for the `/lib` to `usr/lib` convention, with read access to the
tree's build-time module-signing key.

### 2.5 G2 smoke boot — PASS, virt only

Static-init smoke boot under QEMU `virt` on the ARMv8-A core model reached
`Run /init as init process`, printed the expected kernel version and
architecture, and powered down cleanly with exit zero. No laptop claims.

Not yet done at the time: real-hardware boot; later repo flow; neutral OS
identity in the UKI (the builder identity was still embedded, to be
regenerated at packaging time); firmware staging script and its control-test
inputs.

---

## 3. Phase 4–5 — image assembly, stick write, first hardware result

Phase 4 assembly: DONE. Phase 5 stick write: DONE. Boot test G3: FAILED.
G4: NOT REACHED. Source: `../phase4-5-results.md`.

Later native-frontier notes were appended to that file; the early-boot
failures below remain the historical verdict for this era.

### 3.1 Live rootfs, firmware staging, identity, squashfs, UKI

- Live rootfs built in the builder from upstream plus the signed project
  kernel, installed in the target with full signature verification (master
  plus builder keys, locally signed).
- Ten of ten firmware files staged from the machine's own Windows driver
  store into the board firmware path under `usr/lib/firmware/updates/`.
  Local-only; never redistributed.
- Live identity: neutral live OS name, graphical autologin for the live user,
  passwordless sudo for the live session.
- Squashfs root: ~1.61 GiB, xz, low parallelism.
- UKI boot loader: stubble UKI with kernel plus Slim 3 DTB plus hardware IDs
  plus live initramfs, ~228 MB.
- Manifest plus checksums recorded under the project `artifacts/` tree.

### 3.2 Stick write — DONE

- Mid-size USB stick: cleaned partition table, single FAT32 live volume.
- File copy of under 2 GB across five files, success exit; read-back hash
  check passed on both boot artifacts. Stick layout: EFI boot path with the
  UKI, architecture rootfs path with the squashfs, plus a notes directory
  with capture script and checklist.
- Raw sector writes were unavailable on the host; FAT32 file copy was the
  supported method.

### 3.3 First hardware verdict — three identical blank-screen resets

The owner reported three identical attempts: blank screen with a dash, then
restart within seconds, no loader menu or text. File-copy and hash checks
remained valid but did not establish a bootable image.

Retracted at this point: earlier claims of guaranteed graphical autologin,
normal booted-system package management, and a fully closed repo phase.
Firmware presence in the rootfs does not establish its availability to early
initramfs drivers. The original desktop and full-hardware milestone stayed
open.

Original test instructions (historical, not a recommendation to retry
unchanged): one-time firmware boot menu to the USB entry; expect direct stub
loading with Slim 3 DTB selection and a desktop autologin; watch thermals and
power off cleanly; capture logs and per-feature checklist from the notes
directory.

Control-test status: the separate Ubuntu Concept image plus full control
tooling stayed intact; the project-first boot order stood, with an explicit
fallback to rewrite the stick with the control image and boot that for
isolation if the project boot showed an ambiguous failure.

Native-frontier appends (historical context only): by mid-October the owner
reached an initramfs emergency prompt after the live-volume boot-device
timeout, with no external USB devices or working keyboard reported. Firmware
capture exported valid records stopping at the first interconnect error; a
missing final record was explicitly not proof of a kernel hang. Later logger
repair and dt20 comparison work superseded the capture state but did not
change the G3 FAILED verdict for this era.

---

## 4. Repaired v2 image and the move to screen-as-log

Source for this whole era unless noted: `../boot-failure-diagnosis.md`.

### 4.1 Reproduced fatal shipped-image defect — CONFIRMED in QEMU

Booting the original image chain (EDK2 firmware, FAT USB image, loader, the
original stubble UKI and its original embedded initramfs) under QEMU reached
the project kernel, executed `/init`, printed builder-distribution init
errors, and panicked with `Attempted to kill init!` before mounting the live
root.

Root cause, byte-verified: the original initramfs `/init` was byte-for-byte
the builder distro's WSL `/init` ELF binary (SHA256 `18204d25...a33f`), not
the initramfs live-init shell script. The builder's mount helper symlink
caused the stock initramfs filesystem hook to enumerate host mount helpers,
follow the dependency, and overwrite the real init script. The original
archive also contained that helper symlink.

Confirmed: the shipped image defect. Explicit limit: this does not prove the
physical-machine reset got as far as that defect. A firmware or device-tree
failure can occur earlier.

### 4.2 FAT charset defect — CONFIRMED in EFI test

A second EFI test reached the live root logic but could not mount the FAT32
source: `FAT-fs ... IO charset iso8859-1 not found`. The kernel's default FAT
charset is modular and the generic filesystem hook filters those modules out.

Build corrections applied together:

- Project-local filesystem hook excludes the host-only mount helpers; host
  files untouched.
- Extract-and-validate gate requires `/init` to exactly match the live-init
  script, excludes host helpers, and checks live plus board firmware.
- Explicitly pack both FAT charset modules; validation gate checks their
  archive presence; fixtures use a proper partitioned FAT32 layout rather
  than a superfloppy.
- Explicit config arrays and a sanitized environment, with early local
  board and graphics firmware staging.
- Rootfs services: display manager and network manager enabled, graphical
  target set.
- Added the signed upstream wireless GPU-firmware package; the original
  rootfs lacked generic Qualcomm graphics firmware even though its
  board-named DSP firmware was present.
- Removed quiet flags, enabled loader and kernel diagnostics, and set
  no-reboot-on-panic so a panic stays on screen rather than auto-rebooting.
- Preserved the original UKI, squashfs, and staging as evidence; produced
  separate v2 artifacts.

### 4.3 Boot-chain difference noted but untested

The downloaded Ubuntu Concept control image's loader detects Snapdragon
processors and issues a high-memory reservation when loader lockdown is off.
Its comment calls this a Snapdragon X firmware-bug workaround and it also
appends a pointer-authentication disable flag. The original direct-stub
project path skipped this loader step. The diagnostic menu carried the
reference conditional workaround and offered both project and control
entries. Effectiveness on the physical machine remained untested at the time.

### 4.4 Verified v2 QEMU results — PASS, virt only

Both disposable partitioned EFI tests passed on QEMU `virt` with the ARMv8-A
core model, modest RAM, and two virtual CPUs:

- Shell-target test: loader to corrected UKI to live initramfs to USB FAT32
  mount to squashfs to writable overlay to root shell; expected kernel
  version, neutral OS identity, enabled display and network services, clean
  reboot to power-down.
- Systemd test: systemd reached the multi-user target; its serial log showed
  the network manager started. No graphical claim.
- Final initramfs extract-and-validate gate passed all checks including exact
  live PID 1, absent host helpers, FAT charset modules, and local board
  firmware.
- Original failures and first v2 FAT-mount failures preserved as evidence in
  separate logs and images.

Local staging held a few hundred files totaling several gigabytes, including
both project and control payloads, with a per-file hash manifest plus the two
VM test results. The adapted checksum list updated the changed loader and
added the new menu checksum; original payload provenance retained.

### 4.5 v2 USB update and remaining gates

The owner approved the file-only update. It completed against the named USB
disk and FAT32 live volume: all manifest files copied with zero failures and
all hashes matched on read-back. Independent post-update verification
confirmed USB identity, file sizes and manifest total, plus fresh hashes of
the loader, corrected UKI, live squashfs, and menu. Only host metadata files
outside the manifest differed. No formatting, internal-disk, BCD, BIOS, or
Windows boot-setting changes. Real hardware boot, desktop, wired networking,
and thermals still required an owner-executed test. Control boot also
untested. Local driver-store firmware kept the images private and
non-publishable.

USB evidence set: file-only result JSON, timestamped log, independent
verification JSON, read-only USB check script, plus a backup of the original
loader and checksum before the v2 swap.

Next native test at the time: use the existing one-time USB boot selection,
confirm the visible diagnostic menu, try the control entry without installing,
then test the repaired v2 entries; record the last visible text or photo and
whether the machine reaches a desktop, freezes, or restarts; if the desktop
fails, the text-only entry separates graphical-login failure from early boot
failure. No repeated retries of an unchanged early-reset path.

### 4.6 Native v2 attempt (2026-10-09) — menu appears, both entries reset

Owner report: the loader menu appeared. The control entry showed a black
screen for seconds then restarted automatically to firmware. The project
desktop entry showed scrolling kernel messages for seconds then crashed with
an automatic restart. No photo was captured. No logs survived: USB recovery
found zero new files and firmware-variable enumeration found dozens of names
but zero crash records, so there was nothing to reconstruct the lost messages
from.

### 4.7 USB log-capture option (owner-approved, applied 2026-10-09)

A separate log UKI revision plus two menu entries wrote kernel, initramfs,
and userspace logs to a per-boot directory on the same USB before a crash.
Design limits: live-volume label plus marker file plus USB sysfs checks, free-
space gate, capped kernel and userspace samples; writes went through the
live system's own USB mount because an early separate mount blocked the live
mount during testing; the log UKI was inert unless its menu entry was
selected. Cannot capture a reset that happens before Linux reaches the
logger.

File-only delta: log UKI (~245 MB), new multi-entry menu with default
unchanged, volume marker, logs directory. Updater and independent checks both
passed on the delta hashes plus untouched bootloader and UKI hashes. No
formatting, internal-disk, BIOS, or Windows boot-setting changes.

VM proof: shell-target and systemd-target log tests both passed (loader to
log UKI to overlay root to power-off or multi-user; captured kernel,
snapshots, console, and a few hundred kilobytes of userspace journal read
back off the FAT).

Next at the time: boot the USB, select a log-capture entry, let it run or
crash, reboot to Windows, and report new per-boot log files. If the reset
happened before any per-boot directory appeared, the crash was before the
live logger and a photo of the last screen was needed instead.

### 4.8 Log-capture attempt — logger never reached; photo instead

The USB logs directory stayed empty after the owner's log-capture boot: no
per-boot directory, so the USB logger never started. The owner's photo
explained why: the kernel froze very early after kernel entry, during
integrity and module-signature setup (firmware database lists unsupported,
secure-boot mode unknown, no TPM found). USB storage appears only much later
in boot and the logger starts after the live mount, so an early-kernel freeze
leaves nothing behind by design.

Photo proved real hardware progress: ARM64 kernel running on the machine
(arbiter, serial, timer, power-management devices), plausible device tree,
firmware framebuffer handoff to a working text console. No kernel panic was
visible; the screen stopped mid-init with no userspace reached.

Correction: the database-list warnings were normally non-fatal. The actual
hang was at or just after that point; a later photo or video was needed to
place whether output continued, froze, or rebooted, plus which menu entry was
used.

### 4.9 Screen-as-log: initcall-debug entries

No storage logger can run before roughly a minute of kernel time, so the
screen became the only channel for the early reset. Two file-only menu
entries were added using existing UKIs, no rebuild: one printing every driver
initcall with its return status so the last visible line at reset names the
crashing init, plus a second adding a watchdog-disable flag to test the
watchdog-reset hypothesis with one variable changed. The new menu was VM-
booted to multi-user and then copied file-only to the USB with pre-state
check, backup, and read-back hash match. Default entry unchanged.

---

## 5. Stubble alignment: from nondeterministic boot to a later reset

### 5.1 Five-boot photo series (2026-10-11) — three outcomes, one root cause

Five screenshots from the initcall menu showed three different outcomes from
the same binaries: stub prints device-tree found then silence with no kernel
output; EFI stub error `FIRMWARE BUG: kernel image not aligned on 64k
boundary` then hang; healthy kernel driver probing to half a second
(interconnect and power-domain probes, all expected return codes, no panic).
The USB logs directory stayed empty throughout, consistent with never
reaching the logger.

Root cause, confirmed in source: the stub's load path copied the inner kernel
to a firmware-allocated buffer that guarantees only 4 KiB alignment, while
the ARM64 kernel stub requires 64 KiB alignment. Fresh-firmware allocations
are often 64 KiB-aligned by luck, so some boots ran and others failed at the
stub check. Fix: over-allocate and align the base up to 64 KiB (project patch
`0001` for the stub tree, generated from the pristine tarball after verifying
the tree pristine; build exit zero).

Both UKIs rebuilt against the fixed stub (plain and log variants) and
VM-validated shell plus systemd each (one plain systemd run exceeded the
harness budget under load but reached multi-user in its log; rerun passed).
File-only USB refresh applied with pre-state checks, backup, and read-back
hashes.

Next: boot the initcall entry three times, photographing each outcome. If the
alignment error and silent stalls were gone, whatever remained was a second,
separate issue to bisect from the last initcall line.

Source-path note: stub patch lives under `../../pkgs/stubble-arm64/patches/`;
UKI build logs and revision build directories retained as superseded
evidence.

### 5.2 Alignment fix confirmed on hardware — reset moved later

Two post-fix initcall photos both booted cleanly past the stub with no
alignment error and healthy probing to about half a second (shared-memory,
interconnect, power-domain, and cluster probes, all expected codes, no
panic). Both still ended in automatic reset at slightly different points.
The loader bug was fixed; a second, later reset remained, located after half
a second in driver probing. Evidence needed: video or a later photo catching
the last lines at reset, plus the watchdog-disable entry to test whether the
reset itself was watchdog-driven (freeze instead of reboot would name both
the resetter and the hang point).

### 5.3 Both initcall videos reset at the same place

Frame-by-frame review of both videos, with and without the watchdog-disable
flag: the kernel ran to about half a second, last lines were interconnect
probes with success returns, then black screen and reset. No panic or oops in
any frame. The watchdog entry behaved the same, so the kernel watchdog was
ruled out as the resetter. The next device-tree node in address order after
the last success was the south PCIe interconnect node, making its probe (or
the immediately following driver) the prime suspect. Control files verified
intact on the USB. Next: one control boot with photo to separate a
machine-level reset from a project-kernel or project-DTB reset.

### 5.4 USB contents re-verified; 25-second wall-timer clue

The owner challenged whether the stick was actually patched: all boot-
critical hashes re-verified on the USB read-back (plain UKI, log UKI, latest
menu, device-tree blob, bootloader) — the fixes were on the stick. The owner
confirmed the quiet screen was the last line and reset came at exactly 25
seconds wall time. Combined with video resets at roughly 25–30 seconds wall
with kernel progress only a fraction of a second, the reset looked
wall-clock-driven, not progress-driven — a firmware watchdog outside kernel
control fit. Decisive test: time the no-interconnect entry to reset. It had
already lived past the deferred-probe timeout message once; if it ran well
past 25 seconds wall, the timer theory died and the crash was progress-
dependent after all.

### 5.5 Control entry was broken — no DTB passed (fixed 2026-10-11)

The early-October control failure verdict was retracted as evidence: the
project's control entry never passed a device tree, and this is a
device-tree machine (Windows boots via ACPI, so firmware gives Linux no
device tree). An ARM64 kernel without a device tree dies pre-console —
exactly the observed silent reset. Fix: pass the staged board DTB in the
control entry plus stage the DTB file, menu VM-booted and applied file-only
with pre-state, backup, and read-back checks. If the control image then
booted, the machine was fine and its kernel log became the reference; if it
reset at the same place, the reset was firmware or hardware level.

---

## 6. Interconnect bisection: invalid blacklists, void tests, and the tail-NoC wall

### 6.1 Interconnect-blacklist entry (menu only)

New entry booting the plain UKI with all Qualcomm interconnect probing
banned (symbol confirmed in the kernel symbol map). If boot progressed past
half a second, the crash sat in interconnect probing; if it reset
identically, the suspect moved on. Menu VM-booted to multi-user and applied
file-only with pre-state, backup, and read-back checks. No rebuild; default
entry unchanged.

### 6.2 Blacklist boot goes much further — crash site confirmed

Four owner photos of the blacklist boot showed voltage regulators setting
voltages, PCIe, USB, GPU, and display probing, and finally a DMA-engine
deferred-probe timeout with the kernel alive at the end of deferred probing.
No panic, no reset at half a second. Remaining deferrals (display, graphics,
USB physical layers, DMA, wireless) were expected with interconnects off.
Crash site confirmed inside interconnect probing. The first un-probed node
after the last success was the south PCIe interconnect node. Next: check the
kernel fork for newer fixes, else disable that one node as the
single-variable test.

### 6.3 Single-node test dt1 (2026-10-11) — changed nothing by itself

The fork was frozen at the project pin with no upstream fix. Board override
disabling the south PCIe interconnect node recorded as a local-only
diagnostic patch (`0006` series); device-tree blob rebuilt with the exact
per-board target (~208 KB, disable confirmed via device-tree query); plain
UKI `v2-dt1` VM shell PASS. File-only USB swap with pre-state, backup, and
read-back result. Boot the normal initcall entry, not the blacklist one: if
it passed half a second, that node was the reset site; if it reset
identically, the crash was systematic, not node data. It reset identically —
the crasher was a downstream driver released by interconnects, not that
node's data.

UKI `v2-dt1`: ~244 MB, SHA256 `ed8b5c93...09be9`. VM shell PASS evidence
retained; USB delta result retained.

### 6.4 Consumer-bisect entries (menu only)

Since the single-node disable changed nothing, three new entries banned
suspect driver families via initcall blacklist with symbols taken from the
kernel symbol map: display and graphics; USB and PCIe; DSP firmware.
Whichever progressed past half a second would name the family for round two.
Menu VM-booted to multi-user, file-only USB refresh verified. Note recorded
at the time: the USB logs directory can only start after USB plus rootfs at
roughly a minute of kernel time; a half-second reset is two orders of
magnitude too early for any storage logger, so the screen stayed the only
channel until boot got that far.

### 6.5 Bisect round 1 — all three reset within milliseconds

Owner-reported last timestamps clustered within about 13 ms. None of those
families was the crasher. Still needed: the actual last photo lines from
those boots. Remaining early suspects moved to round two (IOMMU and
power-domain controller).

### 6.6 Bisect round 2 — physical layers and IOMMU/power controller

A longer blacklist run (frozen black screen, no reset, no logs) proved the
reset needed interconnect-dependent drivers and the black screen was
display-without-interconnect, not death. Two new entries: no USB and display
physical-layer drivers (five init symbols), and no IOMMU plus power-domain
controller (ARM SMMU plus Qualcomm SMMU plus power-domain symbols). Menu
VM-booted to multi-user and applied file-only with pre-state, backup, and
read-back. One photo of the last screen per entry.

### 6.7 Two void tests found — INVALID blacklist assumptions retracted

Blacklist-name verification against the kernel symbol map showed two names
never matched: the display-register symbol and the DSP-driver symbol. Those
two entries excluded nothing. Worse, the kernel config showed display, DSP,
video, camera, wireless, and storage-host drivers were all modules: none were
even present during early boot. The one PHY family never banned was the UFS
PHY (built-in). Round-three menu entries: no UFS PHY plus no-CPU-idle
(`cpuidle.off=1` — if the kernel reaches the end of probing then dies on
first CPU power collapse, this walks straight past it). Menu VM-booted to
multi-user, USB verified. This explicitly retracts any earlier reading of
the display and DSP blacklist boots as exclusions.

### 6.8 Round-1 photos: crash moved to the next interconnect pair, still no panic

All three boots sailed past the disabled node through roughly ten more
interconnects with expected warnings and benign deferrals, then reset right
after the multimedia-south interconnect node. The single-node disable did let
probing continue — the reset was systematic, and every reset landed at about
half a second kernel time regardless of node count. Caveat recorded at the
time: the initcall flood over a roughly ten-times-slow framebuffer meant the
last painted line lagged the true crash; the crash could sit in the next
initcall after the deferred pass. Decisive low-cost test: boot the quiet
desktop entry with no initcall flood so paint kept up, and photograph the
final screen for true placement.

### 6.9 Quiet desktop photo — caught mid-boot, not at reset

The quiet-boot photo showed only very early boot (display init, keyring,
integrity, first interconnect skips) — far earlier than the initcall boots'
half-second point, so that frame predated the reset and the boot was likely
still running when photographed. No panic. Still needed: seconds from loader
to reset in quiet mode, plus a photo of the final screen before reset.

---

## 7. Tail interconnects, minimal cut, and the SCM hang chain

### 7.1 Bisect round 4 dt2 — boot reaches 9.45 s; tail NoCs were the reset site

Owner booted entry 6 with dt2: last line was a voltage-regulator deferred
probe with success-expected code at 9.458 seconds kernel time. That was about
twenty times further than every prior half-second boot — the tail-NoC disable
worked. One or more of five tail interconnects plus the earlier south node
disable were the only interconnect nodes left after the prior crash point.
That return code itself was a benign deferred probe (supply not ready,
retried later), not the crash — the killer was whatever probed next,
off-screen. Needed: full-screen photo with earlier lines naming the next
suspect, plus outcome after that line and wall-clock seconds.

Five tail nodes plus the earlier south-node disable were the only interconnect
nodes left after the prior crash point. Recorded as local-only patch `0007`,
device-tree blob rebuilt natively (~208 KB — cross-linker was missing, so the
native compiler was used), all disable states verified via device-tree query.
Plain UKI `v2-dt2` VM shell PASS, promoted into staging and applied file-only
to USB with pre-state, backup, and read-back result. Boot the normal
initcall-debug entry: if it walked past the prior crash point, the crasher
was one of the five and a re-enable round followed; if it reset at the same
place, the crash was not a late interconnect probe and the theory redirected.

UKI `v2-dt2`: ~244 MB, prefix `b1ad1b8b...`. VM shell PASS (rootfs, overlay,
power-off). USB delta result retained.

### 7.2 Bisect round 5 dt3 — minimal-boot cut (22 nodes, USB and core stay on)

The owner confirmed the 9.45-second frame was the end from video. Twenty-two
nodes disabled in one cut (patch `0008`, all verified via decompiled
device-tree blob): PCIe controllers and PHYs, wireless and display and NVMe
rails, thermal sensors, display PHYs, and the UFS PHY. USB and core stayed
enabled. Plain UKI `v2-dt3` VM shell PASS, promoted to staging, USB
file-only verified. Boot entry 6: if it walked past 9.45 seconds toward USB
and rootfs, re-enable families one at a time; if it reset at the same place,
the crasher was in the remaining core (USB path, power management,
pin control, or system control) and the emergency-shell capture plan
activated.

UKI `v2-dt3`: ~244 MB, prefix `a3d1f6c2...`. VM shell PASS. USB delta result
retained.

### 7.3 dt2 ending was a black hang, not a reset

After the 9.45-second frame the screen went black, waited minutes, nothing;
forced shutdown. No reset this time — the tail-NoC reset site was eliminated
and the failure mode changed to a hang. The USB logs directory stayed empty,
so the kernel never reached USB plus rootfs (the logger never started): the
machine was stuck in device probing with display dead, or dead. Awaiting the
dt3 minimal-boot result: reset versus black hang plus last frame.

### 7.4 Hang chain found in source; patch 0009 breaks it (2026-10-15)

A 19-second transcription showed the timeout wave forcing drivers through
(DMA, serial, power-management, all success) but pin control, system control,
USB, and IOMMU still deferring, then black. Root chain, all verified in
source plus device tree: the system-control node's interconnect path never
resolved, so system control deferred; the platform power-domain quirk
returned deferred probe when system control was unavailable; the pin-control
node (whose wakeup parent was the power-domain controller) deferred; with no
GPIO, USB physical layers and regulators stayed stuck; with no USB storage,
no rootfs and a black hang. Fix `0009`: delete the interconnect property on
the system-control node — the driver treats an absent property as no bus
vote, so system control probed without bus voting. Device-tree blob ~208 KB,
verified without that property. UKI `v2-dt4` building.

This was inference from source plus device tree at the time, confirmed by
the next boot's behavior rather than asserted as fact before it.

### 7.5 dt4 on USB (2026-10-15) and first pinctrl success

UKI `v2-dt4` (~244 MB, prefix `93019748...`) VM shell PASS, promoted to
staging, USB file-only verified. Boot entry 6: expect system control,
power-domain, and pin-control probing in the first wave instead of deferring
— screenshot both the half-second region and the late region.

dt4 boot (2026-10-16): the half-second wave went green including first-try
pin-control success — the chain-break prediction held. Kernel reached init
above 9 seconds, userspace uevents triggered, then clocks, power, IOMMU, and
power-management all resolving through 9.33 seconds. Awaiting outcome after
that point.

### 7.6 Black screen after 9.33 s — regulator-cleanup suspect, then dead

The owner reported black immediately after 9.33 seconds, then nothing. Prime
suspect was the kernel's own unused-regulator power-off (which ran before the
black point): a firmware-left-on panel or backlight rail with no consumer
would be switched off. The ignore-unused regulator flag was confirmed in
source. A new initcall-debug plus keep-regulators entry was added, menu
VM-booted to multi-user, USB verified with eleven entries. Test: if the
screen survived past the black point, the theory was confirmed and boot would
proceed toward USB and rootfs.

Keep-regulators boot: USB physical layers bound, GPIO alive. The owner frame
ended with combo and USB physical-layer success plus alive GPIO — the full
pin-control chain resolved — with clock controllers all success and host
controllers still deferring but their prerequisites binding. Awaiting outcome
after that point.

Regulator theory then died: the keep-regulators boot also went black at the
same point — cleanup ruled out. The USB logs directory stayed empty (no
rootfs; USB never completed). Clock and power-domain ignores were confirmed
on the USB command line. New prime suspects active exactly at the black
point: display clock-controller init, graphics IOMMU configuration, or a
backlight driver binding to off. Zero-cost physical tests asked:
flashlight-at-angle (backlight versus signal) plus keyboard-lock LED (alive
versus dead). If signal loss, the next round would blacklist the named
display clock-controller inits, confirmed on screen, menu-only.

### 7.7 Full system hang; CPU-idle and IOMMU rounds

The owner reported flashlight showed nothing (signal loss) plus dead
keyboard-lock LED on the text entry: full silent freeze, no reset. Suspects:
CPU power collapse on first idle, or IOMMU enable. Menu gained a no-CPU-idle
entry plus a re-added IOMMU-only ban (the old combined verdict was stale
because the crash point had moved). Menu VM-booted to multi-user, USB
verified. Boot the no-idle entry first, then the IOMMU entry, with a
last-frame photo each.

No-IOMMU result: the IOMMU-ban entry reached live-volume mounting at 9.5
seconds with a USB PHY bound, then a 19.44-second timeout wave forced
graphics success with the graphics microcontroller starting — screen alive
ten seconds past the old death point. IOMMU enable looked like the 9.3-
second killer. Awaiting mount outcome plus the no-idle outcome.

### 7.8 Both hang black; USB needs its disabled interconnect — re-enabling it

Both the no-idle and no-IOMMU entries ended black with no logs (mount timed
out, USB never enumerated). Root cause in device tree plus source: the USB
controller's application-processor path ran through the disabled tail
interconnect node, and that node was the project's own earlier disable — USB
could never come up. Fix `0010` re-enabled that one node alone, leaving the
other tail nodes and the south node off. Next build started. Boot entry 6 on
the stick: reset at half a second would mean that node was the crasher and
USB had to be routed around it; USB binding plus enumeration plus mount would
mean USB was unblocked.

dt5 on USB (2026-10-16): UKI `v2-dt5` (~244 MB, prefix `239b5634...`,
auto-DTB ~208 KB) VM shell PASS, promoted, USB file-only verified. Boot
entry 6 with the same acceptance split: reset meant the node was the crasher;
USB binding and new-device plus mount meant unblocked, then watch display and
rootfs.

dt5 result: boot stopped at 0.54 seconds at the next interconnect node with a
downgrade message — back at the old wall. New detail: two virtual
interconnects both succeeded and the memory interconnect registered now, but
no pin-control line appeared (the prior dt4 build had it). That node's voter
property resolved to a shared-memory node, not a voter — likely a device-tree
quirk yielding deferral, not reset. Awaiting whether the outcome was reset or
hang at that point plus wall-clock seconds.

Reset in 4 seconds wall with that node on, rerouting USB around it: the only
delta versus the 19-second-booting dt4 build was that node, so that node's
presence reset the machine (probe itself or an unlocked consumer; serial
children could not exist yet at half a second). But the USB controller needed
that node for its application-processor path. Fix `0011`: that node back off
plus each USB application-processor pair rerouted onto its own USB-memory
pair (verified no wrong interconnect identifier in any USB path, twelve cells
each). Next build started.

dt6 on USB (2026-10-16): UKI `v2-dt6` (~244 MB, prefix `6b27f7f2...`) VM shell
PASS, promoted, USB file-only verified. Boot entry 6: no half-second reset
expected with that node off; watch USB lines near 9.5 seconds (success means
the reroute worked) then new-device plus mount.

dt6 boot: no half-second reset; at 9.26 seconds the graphics device joined
its IOMMU group with GPIO alive and all clock controllers green — with IOMMU
enabled. The prior death point did not repeat. Awaiting USB and mount outcome
after that point.

---

## 8. Display takeover, USB teardown, and the unified logger

### 8.1 dt7: black with no graphics either; wait for the 19-second wave

The dt7 frame ended in the 9.3-second range on a physical-layer deferral: no
graphics lines because the disable worked, with input and power-management
alive — yet black again. But silence from 9.3 to 19 seconds was normal at
this stage (deferred retries only fired on supplier events plus the roughly
19-second timeout wave; an earlier build proved the kernel could be alive
behind it). The earlier keyboard-LED verdict may have been specific to the
graphics-IOMMU interaction. Asked: keyboard-LED test on the dt7 black screen
plus a 60-second wait for the timeout wave, with a photo of any late text.

Black-with-backlight result: screen alive with backlight on but no image.
Removing graphics and its microcontroller did not stop it because the display
subsystem driver (an initramfs module) bound the still-present display node,
took over the firmware framebuffer, and the panel never lit. Fix `0013`
disabled the display subsystem node; console stayed on the firmware
framebuffer. Next build plus VM test, then USB.

dt8 on USB (2026-10-16): UKI `v2-dt8` (~244 MB, prefix `00b5ffe6...`,
auto-DTB ~208 KB) VM shell PASS, promoted, USB file-only verified. Boot entry
6 and stay on text: if lines kept flowing past the black point toward the
19-second wave, the invisible-boot era was over and the remaining fight was
purely USB and mount.

dt8 result: black near 9.15 seconds with text stopping at voltage-setting
lines; input registered, IOMMU configured, first power-management voltage
sets, then black — the shortest boot yet. Display, graphics, and
microcontroller were all off, yet black persisted. The longest visible boot
ever was the IOMMU ban, so no-IOMMU returned as a menu entry. Boot it, wait
60 seconds, photo any late text.

That entry's frame ended at 9.225 seconds on a regulator deferral with a new
display-connector binding. The earlier IOMMU ban had lived much longer, so
the question was whether the new black screen was death or just the normal
silent gap before the roughly 19-second timeout wave. Asked: wait 60 seconds
on black, photo any late text.

Instant black freeze at that point; display-clock module ban: the owner
reported an instant black freeze right after that timestamp with forced
shutdown. The display clock-controller init symbol was not in the kernel
symbol map (module-local), so the new entry used a module blacklist for that
module. Menu updated and VM-booted to multi-user, USB verified.

### 8.2 Entry 8: xHCI up at 19.47 s then torn down at 19.51 s

With the display-clock module banned, the screen stayed alive past the old
death point; repeater plus regulators bound, mount plus ten-second wait, then
xHCI came up (buses and hubs, with a USB controller bound off-screen), then
both root hubs disconnected with removal state. Role-switch theory dead: the
device-tree host mode was already set. One line at the failure instant (the
actual error) was unreadable in the photo. Awaiting outcome after that point
plus the hidden line.

### 8.3 Stale-phandle bug in the USB reroute; label-based fix (dt9)

The owner read the hidden line: an interconnect-cells error for the command-
processor mailbox. Root cause in the project's own method: hardcoded raw
handle numbers from a stale decompile now resolved to the mailbox, breaking
path parsing and tearing the USB host down. The fork source used labels (one
USB-memory path plus the disabled-node application path per port). Fix
`0014` redid the reroute with labels (compile-time resolved, verified
per-node in the new device-tree blob: only the intended two providers per
port). Rule recorded: never raw numbers. Next build plus VM, then USB.

Duplicate-pair rejection; application path via another interconnect (dt10):
the new blob's invalid-path came from the interconnect core refusing the same
route twice (duplicate pair for both names) — the host tore down tens of
milliseconds after coming up. Fix `0015` pointed the application path at the
configuration interconnect (stock shape, disabled node replaced, all labels;
verified expected providers per port, no wrong node). If the graph lacked
that link, the fallback was an optional-application-path change in the USB
driver (kernel patch). Next build plus VM, then USB.

dt10 on USB (2026-10-16): UKI `v2-dt10` (~244 MB, prefix `e2e1fe93...`) VM
shell PASS, promoted, USB file-only verified. Boot entry 8: if the
application path resolved, no invalid-path line and the host stayed up, then
new-device plus mount; if invalid-path persisted, the kernel driver patch for
an optional path was next.

dt9 on USB (separate step in the records): UKI `v2-dt9` (~244 MB, prefix
`3004ed18...`, auto-DTB ~208 KB) VM shell PASS, promoted, USB file-only
verified. Boot entry 8: the USB controller should have bound without the
mailbox error this time; watch for new-device (the stick) then the mount.

### 8.4 Black after graphics IOMMU attach; graphics cuts (dt7 builds)

A black screen after the graphics device joined its IOMMU group: without
IOMMU the boot lived much longer, so the graphics-IOMMU interaction was the
killer (context setup or firmware load). Fix `0012` disabled the graphics
and microcontroller nodes; console stayed on the firmware framebuffer. Next
build plus VM test, then USB.

dt7 graphics-cut build on USB (2026-10-16): UKI `v2-dt7` (~244 MB, prefix
`ce428160...`, auto-DTB ~208 KB) VM shell PASS, promoted, USB file-only
verified. Boot entry 6: the screen should have survived the prior death
point; watch USB and mount after, plus where if anywhere it stopped next.

### 8.5 Unified capture on USB; capture flag on all entries

Unified UKI `v2-dt11` (~245 MB, prefix `765ddb44...`, hook included) VM shell
PASS without the flag (inert proven) plus menu validation PASS with capture
(multi-user, kernel, journal). Promoted, both log entries repointed at the
shared image plus flag, menu updated, stale log UKI retired to backup. USB
file-only verified. Any entry could then capture by adding the log flag.

Capture flag on all entries (menu ~4.7 KB, 2026-10-16): the owner asked for
the flag on the tested entry and everywhere. All project entries then carried
the log flag; the foreign control initramfs was excluded. The menu test
needed the unified UKI swapped into the fixture (it still carried the
hookless one) then passed with capture. USB menu-only update verified.
Whichever entry went furthest then logged automatically.

### 8.6 xHCI detail and driver fallback (dt10–dt12)

Subsequent owner result: no invalid-path line; the USB host-controller
driver succeeded at 9.495 seconds (ten seconds earlier than ever) with buses
plus hubs up and a USB PHY bound — the configuration-interconnect route
resolved and the controller stayed up with no teardown in that frame. Other
controller ports still retried with deferred-probe codes. Awaiting real
device enumeration (stick or mouse identifiers) plus mount.

Fallback executed because the new blob still showed invalid-path then
teardown in another boot: the graph lacked links to that interconnect as
well. Driver patch `0016` made the application path best-effort (warning
plus null, all use sites guarded; the USB-memory vote still applied).
Applied to the kernel source with assertions, recorded. Kernel Image rebuilt
incrementally, then UKI `v2-dt12` plus VM plus USB. If the controller bound
and stayed, USB enumeration was next.

dt12 built plus patch-in-Image verified (2026-10-16): UKI ~245 MB,
`passed:true LIVE_UKI_DONE`, warning string for the workaround present in
the Image (~52.5 MB). A host reboot mid-session broke a mount listing
through the compatibility command — the records note the corrected query
form — but the build had already finished. VM shell PASS.

dt12 on USB (2026-10-16), boot entry 8 now: UKI `v2-dt12` (~245 MB, prefix
`afb0aa04...`) VM shell PASS, promoted, USB file-only verified. The
workaround in the Image attempted to skip an unavailable application path
with a warning. Native success was not verified: the owner tested dt12
without a photo or recovered trace. The expected warning, continued host
operation, physical USB-device enumeration, and successful mount remained
observations to obtain, not established results.

Historical variable proposal, superseded by the safety audit: provisional
design notes for streaming small rotating log tails into firmware variables
from an early-hook loop, readable from the host OS, never wired into the
build mid-build, flag-gated opt-in per boot, with stated nonzero firmware
risk. See the audit below before acting.

xhci-up-then-black with no devices or logs; slow-print entry: the owner
reported full black after the early USB success with no devices, no mount,
and an empty USB logs directory. Because paint lag made last lines
unreliable, a new entry slowed output to one second per line so the line on
screen at black would identify the killer. Menu updated, VM-booted to
multi-user, USB verified. Boot it and photograph the frozen line.

Current USB content verified 2026-10-16 by read-back from the USB media:
live UKI `v2-dt13` (workaround plus early-log hook, ~245 MB, SHA256
`0f319c98...`), menu (~5.2 KB, SHA256 `9bbf0d68...`, eleven entries with the
firmware-log entry on hold), control device-tree blob unchanged, reference
loader unchanged, repaired rootfs squashfs unchanged, stale log UKI retired
backed up off the stick. Menu: desktop, two control entries, text-only,
log-desktop, log-text, initcall debug, no-IOMMU, no-display-clock,
firmware-log on hold with do-not-boot marking, slow print, return.

---

## 9. Firmware logger: dt13 HOLD, bounded replacement, dt14–dt17

Sources: `../firmware-logger-audit.md` and `../logger-v2-repair.md`.

### 9.1 dt13 on USB — native firmware-log testing ON HOLD (audit correction)

UKI `v2-dt13` (~245 MB, SHA256 `0f319c98...`) and its menu stayed on the USB.
Hook inclusion and generic VM root-shell boot passed, but the VM command line
did not enable the firmware-log flag — firmware capture and persistence were
never tested. The writer had no total write limit and hid failures; the host
reader had a misplaced parameter block and incomplete privilege and error
handling. The earlier claims that firmware logging was ready, that it
survived any crash, and that no photos were needed were retracted. Do not
use the firmware log or the reader's delete mode until hardened and
validated. The audit changed no USB or firmware contents.

Audit findings (bounded replacement resolved these; dt13 writer retired):

- Unbounded firmware calls: endless loop rewriting a tail and sequence
  variable every few seconds. Bounded payload did not bound total writes or
  flash bookkeeping. No deadline, write budget, change detection, or
  free-space policy.
- Missing failure handling: mount and write errors suppressed; an existing
  directory accepted without verifying it was a writable firmware-variable
  mount; sequence advanced regardless of write success; immutable-after-
  remount behavior unhandled.
- Weak coverage: only the last bytes sampled at multi-second intervals, with
  no per-record boot ID, kernel sequence range, entry or revision identity,
  or checksum. A freeze between samples lost the intervening text. An
  initramfs shell could not capture a failure before it ran and could not
  keep logging after the kernel stopped scheduling or firmware calls stopped
  working.
- No cleanup: the hook's cleanup function was a no-op; the comment that the
  later root switch necessarily killed the loop was not a lifecycle
  guarantee. No process shutdown handshake.
- Host reader bug: the script assigned a preference variable before its
  parameter block, so a read-only syntax audit showed the intended parameter
  declaration parsed as an ordinary command. A zero parser-error count did
  not validate the script.
- Reader privilege and preservation gaps: no explicit firmware-privilege
  check, every failed read labeled absent, and delete mode removed variables
  before saving its output — a save failure could discard the only copy.
  Never run its delete mode as then written.
- Namespace ownership: the literal shared identifier used by writer and
  reader had to be preserved exactly for read-only recovery of existing
  records; a future format needed a documented project-owned identifier plus
  a separate legacy read path.

Safer development path required: RAM-first capture flushed through the live
system's own USB mount when available; if firmware persistence retained, an
explicit opt-in with a strict total write budget and deadline, compact
milestone and error records, no unchanged writes, and immediate stop on
errors; versioned records with boot ID, revision and entry identity,
sequence, payload length, and checksum saved in one checked operation with
read-back validation, never touching boot, security, or vendor variables;
real process shutdown; repaired host reader distinguishing missing data from
denied privilege from unsupported firmware; raw-record export and
verification before any separately authorized deletion with default
read-only recovery; local tests for absent, read-only, full, rejected, and
malformed storage, then exact-new-UKI testing with the flag on against a
disposable persistent firmware-variable store, abrupt termination, new-
process recovery with byte and checksum verification, plus flag-off testing
with zero writes; only after those gates, one controlled native attempt with
photo and video fallback retained. QEMU was not the target firmware.

Other corrections carried in the audit: a completed probe line names a probe
that returned, not necessarily the cause of the next hang; a last visible
framebuffer line can lag execution; root hubs are not the external device
(their creation does not prove removable storage enumerated or mounted);
the supplied invalid-path plus host-removal evidence was concrete
interconnect and deferred-probe evidence, not firmware randomness; empty USB
logs proved no file was recovered, not by themselves why boot failed
(logger timing, USB enumeration, and mount state had to be distinguished);
the driver workaround was built but its effect on native teardown was
unverified without a later hardware trace — do not state that USB stayed up;
commands after statement separators outside the builder call ran in the host
shell, so host failures to access the project mount did not prove a builder
reboot or dropped mount — prior mount and reboot diagnoses were not
established by those probes.

### 9.2 dt14/dt15/dt16 logger hardening plus USB ready (2026-10-16)

The old unbounded firmware loop was retired (never shipped past dt13, never
ran natively). Replaced with a bounded static binary: a 64 KiB RAM ring of
kernel messages from the early hook, always on with the USB-log flag; firmware
checkpoints strictly opt-in with the firmware flag, at most four 1 KiB
write-once records under the project identifier, with checksum plus boot-ID
stamping, existing records disarming new writes, a 60-second deadline, no
updates or deletes, and checked errors stopping the logger. Default entries
wrote nothing to firmware (proven in QEMU: flag off created zero records).

QEMU proof with a disposable firmware-variable store and abrupt-kill
recovery: flag off produced none, flag on produced two, kill preserved them,
re-opt-in with evidence present refused. Unit tests plus read-only recovery-
script tests passed on synthetic fixtures with no delete path. Native
firmware safety still not proven: the firmware entry asked for typed
confirmation and stated experimental; the recommended native first boot was
the default entry, which used no firmware writes.

Handover bugs found by full-chain validation and fixed: the backgrounded
observer outlived the root switch into a stale mount view and spammed the
console — the cleanup hook then owned the final USB sync and terminated it;
a stopped marker plus console banners were added; all rotating file writes
made atomic after proving truncate-then-poweroff yielded zero-byte journals.
The next revision proved lifecycle (stopped marker on USB plus console, zero
spam) but its journal sample was cut by power-off timing; the following
revision with the same kernel and device tree and initramfs-only changes
passed the full gate: systemd multi-user in under five minutes virtual time,
kernel log plus journal plus early-kernel boot banner plus stopped marker
present, no panic. The two intermediate revisions were superseded before
touching USB and never staged.

Boot-chain audit (read-only): the application-path workaround was present in
source and the device-tree blob kept both USB paths (the workaround was the
safety net); the display-clock module blacklist was valid (module built as a
module and packed in the initramfs by the kernel-mode-setting hook, so the
tested entry was a real exclusion test); both IOMMU init symbols were in the
kernel symbol map; no firmware backend in the initramfs (only frontends), so
firmware-off also meant no persistent-RAM firmware path.

USB file-only update verified with backup kept: UKI ~244 MB (SHA256
`d85658ae...`), menu ~5.6 KB (SHA256 `c79f5bc5...`), eleven entries with
default no-display-clock and the firmware-checkpoint entry gated behind typed
confirmation; staging hashes matched the builder. Native state unchanged: G3
FAILED, no USB logs yet. Next native: boot the default entry, photograph the
screen plus wall time; firmware entry only after the default was
characterized, and export records before any retest because existing records
disarmed new writes.

### 9.3 Native firmware checkpoints WORK plus root cause found (2026-10-17)

The owner booted the default entry then the firmware entry on dt16. The USB
logs directory stayed empty because USB never enumerated, as expected.
Firmware held three records from one boot, all checksum-valid by read-only
export: slot 0 near 9 seconds with init running (command line proved the
firmware entry with the firmware flag); slot 1 near 9.5 seconds with the USB
host bound; slot 2 near 10 seconds with the USB controller deferred-probe
invalid-path error. No third slot: the machine died before the 60-second
deadline. Notably absent: the application-path workaround's continuing-
without-it warning was not the failing site.

Probe-order proof from source: the USB controller probe bound the host child
before running its interconnect setup; the parent then deferred on the lookup
and the framework tore the bound child down. The only remaining defer path in
that setup was the USB-memory path.

Graph walk from the interconnect source plus the shipped device tree: the
USB-memory route crossed several south, center, system, and memory
interconnects including the disabled tail node. Every provider on the route
was enabled with a built-in driver except that tail node, disabled since the
half-second reset investigation — so the lookup deferred forever. All four
USB controllers shared the cause. The project's own reset-mitigation disable
was what killed USB. The driver's failed-to-get-path line printed
microseconds after the trigger and was cut from the small record window —
inferred, not yet observed; the next diagnostic build tested the inference
directly. Fix direction: make the USB-memory path best-effort (mirroring the
prior workaround, with null guards and a success-init fix). If the host
stayed up and enumerated the stick, inference confirmed and the project
unblocked via real USB logs; then the true memory-path fix would follow. Not
for publication.

### 9.4 dt17 (USB-memory path optional) validated, on USB (2026-10-17)

The workaround was applied via an assertion script (six sites), with a patch
record for the diagnostic change. Incremental kernel rebuild, same size. The
Image carried both continuing-without-it warnings (application path plus
USB-memory path). The dt17 UKI (~244 MB, kernel build 3, same device tree)
passed the full gate: systemd multi-user in under five minutes virtual time,
kernel log plus journal plus stopped marker present, no panic. One flake: log
snapshots absent on the FAT despite a clean console (forced-poweroff versus
FAT flush timing; the full stream was present regardless) — watch item, not a
gate failure. USB file-only update verified with prior backup kept;
independent read-back matched; menu unchanged with default entry. Native
next: boot the default file-logging entry (which should then have worked if
the host survived); firmware entry again only if the default still tore
down, with firmware export first because records disarmed new writes.

Entry 8 then carried the firmware logger too and stale records were cleared:
the owner asked for the firmware logger in the default entry as well; the
entry was renamed accordingly with the same flags plus the firmware flag.
Menu-only USB update verified with backup kept; UKI untouched. A new scoped
checkpoint-clear helper (project identifier plus four names only, explicit
confirmation gate, pre-delete export, privilege hygiene) removed the cycled
records; the prior records were exported then deleted with read-back
confirming all slots missing. Reminder: each test boot consumed the four
one-shot slots, so export was required after every boot before retesting.
The host reader was also fixed to exit with explicit success and gated-
failure codes so callers could gate on it; the clear-script refusal path was
tested.

---

## 10. dt18 failed evidence and dt19 bounded-logger repair

### 10.1 dt18 — failed candidate, never installed on USB

A dt18 revision attempted combined console plus file initramfs logging with
the syntax `rd.log=console,file`. An EFI test rejected that syntax, so the
dt18 candidate was retained as failed evidence and never installed on the
USB. The dt19 repair below used the verified parser form with separate
console and file flags. No native dt18 boot is claimed.

Gap note: no separate dt18 narrative file was published; the failure is
recovered here from the dt19 repair document plus the build and validation
filenames in the private run export. Exact dt18 UKI hash and full EFI
rejection text were not re-quoted here because they were not needed for the
dt19 result and would have required quoting unredacted run output.

### 10.2 dt19 scope and corrections

Source: `../logger-v2-repair.md`.

This repair fixed diagnostic capture in the two tested entries, not USB
enumeration or desktop boot. Their shared UKI retained the dt17 kernel and
device tree. No port, physical-layer, interconnect, or kernel-configuration
changes were made by this repair.

Corrections to earlier reports recorded in the repair:

- A second identifier's records were a real second native capture, distinct
  from the earlier boot. Re-reading them later did not prove another
  successful capture. The host reader then reported boot IDs and whether
  bytes matched the previous export.
- A missing final slot did not prove the kernel died, a power-off occurred
  before 60 seconds, or USB tore down. A firmware-write or readback failure,
  logger exit, or disarmed logger could also explain missing evidence.
  Previous claims naming power-off as the cause were retracted.
- The three old records stopped at the first invalid-path error. They did
  not contain the following continuing-without-it warnings. Treat the memory-
  path explanation as source-based inference, not a complete native trace.
- The owner's later emergency-shell transcript proved continued kernel and
  initramfs activity but did not by itself prove every USB controller stayed
  bound.
- Earlier claims that exporting records rearmed capture were wrong. Export
  was read-only. Existing project records had to be separately cleared to
  rearm.
- Firmware persistent-RAM capture was disabled in both the embedded default
  command line and the loader platform parameters.

### 10.3 Capture changes

The former writer spent one slot on root-hub registration and another on the
first error, before the informative continuation lines. Raw kernel-message
metadata occupied much of each small payload. It could also exit on an input
error without reporting useful later state.

The v2 writer kept the same project identifier, four one-shot variables, at
most about 1 KiB per record, no overwrites or deletes, and a 60-second
lifetime:

- Slot 0 at start: capture version, kernel build, boot ID, current state.
- Slot 1 about a second after the first relevant error, or at six seconds:
  follow-up USB, interconnect, and physical-layer messages, not just the
  first failing line.
- Slot 2 at twelve seconds: later binding and enumeration state plus
  filtered messages.
- Slot 3 at fifty-five seconds, or at normal cleanup if earlier:
  boot-device-timeout observation and USB state.

Each record carried root-hub count separate from external devices, plus label
presence and binding status for the four named platform USB controllers.
Noisy sync-state chatter and auxiliary metadata were omitted from firmware
payloads; the larger RAM ring kept raw kernel messages for USB flushing if
storage became available. Input errors no longer canceled timed state
capture.

Both tested entries used the verified separate console and file logging
flags against the installed initramfs parser. This recorded initramfs
userspace mount errors in RAM as well as keeping them visible; kernel-message
buffer alone could not see those errors.

Console reported successful slots with explicit saved markers plus explicit
disarmed and stop conditions. A slot was marked saved only after byte-exact
readback. A rejected firmware write stopped further attempts.

### 10.4 Host recovery and rearming

The host checkpoint reader stayed read-only, checked checksums, saved raw
bytes and checked their readback, reported boot IDs and unchanged exports.
Checksum-valid did not mean complete or fresh.

The checkpoint-clear helper then required both explicit confirmation and the
exact exported boot ID. It launched the reader in a separate process,
rejected invalid, mixed, or mismatched records, verified raw backups and all
current bytes before the first deletion, deleted only the four named project
variables, checked all four absent afterward, and restored its token
privilege. It never cleared legacy, global, boot, security, or vendor
variables.

The user explicitly approved export plus clear of only those slots in this
repair. Native records were archived in a timestamped recovery directory,
then the saved slots were deleted and independent readback confirmed all four
missing. The previous exports stayed intact.

### 10.5 Verification evidence (results beside the build)

- Synthetic checkpoint-timeline result: delayed warnings, quiet-input later
  checkpoint, noise filtering, four-write limit, independent checksum check.
- Checkpoint unit result: filesystem gate, existing-record refusal, record
  bounds, and stop-on-write-error on an ordinary-directory backend.
- Checkpoint reader test result: host reader accepted valid records and
  rejected corrupt or truncated synthetic records; no firmware writes.
- Recovery-safety script: parsing, compilation, refusal without confirmation
  and malformed boot ID; no firmware calls.
- Artifact audit: PE sections equaled the exact kernel, device-tree, and
  initramfs inputs; persistent-RAM disable present; candidate hash.
- Exact-candidate logger test: PASS on the exact candidate hash below. Flag
  off produced zero project records. Hot-unplugging the virtual stick after
  the early hook reached the real boot-device timeout and emergency prompt.
  After an abrupt VM stop, a new VM process recovered four checksum-valid
  records. The final payload contained zero external USB, missing label, and
  the boot-device-timeout observation. A later flag-on boot with existing
  records refused and retained every recovered byte.
- Menu shell regression with the firmware flag removed solely for that
  file-logging regression: PASS, serial console with a short fixture menu
  timeout, full EFI to overlay to systemd multi-user in about five minutes
  virtual time under emulation within the declared test budget, with USB
  kernel-message, journal, RAM captures, and stopped marker all verified. No
  panic.
- Host VM-decode report: the host reader accepted the actual recovered VM
  timeout record, independently checking its checksum and payload.

### 10.6 Installed USB and next native attempt (dt19 state)

A USB update script passed its dry run, preserved dt17 rollback files, then
updated only the UKI and loader menu. An independent verifier re-resolved
the physical USB disk and FAT32 live volume, matched both changed files plus
the untouched loader and squashfs against staging, checked eleven menu
entries and both tested-entry flags, and read all four firmware slots as
missing.

- UKI: ~244 MB, SHA256 `fae9defe...cd7f3`.
- Menu: ~5.8 KB, SHA256 `1e02ed0a...73fc7`.
- Evidence: USB result JSON, independent USB result JSON, update manifest;
  existing staging menus then matched the stick.
- Tested entries: default plus confirmation-prompt variant, both with the v2
  capture.

Boot the default entry once. At the emergency prompt, no typing was required:
no USB keyboard was needed for capture. Leave it running until the final
checkpoint-saved marker and RAM-capture-stopped marker appeared (about
ninety seconds after kernel start). If it instead reported disarmed or a
firmware stop, retain that screen as evidence. Return to Windows for a
read-only export before another test; exporting alone did not rearm. Photos
remained a useful fallback. No desktop success claimed.

### 10.7 Native dt19 capture recovered

Read-only recovery archived in a timestamped recovery directory. Boot ID
distinct from the preceding dt19-preparation export. All four records
recovered with valid checksums; independent checks confirmed their raw hashes
and checksums. The preceding pre-boot export had all four slots missing, so
these were new native evidence rather than another export of the old boot.
Recovery made zero firmware writes and did not clear any slots.

- Checkpoint kernel uptimes: about 9, 10.8, 21, and 64 seconds.
- At the three later checkpoints: two root hubs, zero external USB devices,
  missing label. Root hubs were not external devices or evidence that the
  stick enumerated.
- One named USB controller stayed bound at those snapshots. Both optional
  interconnect paths reported deferred probe, then explicitly continuing
  without them; their parent probe returned success. These records did not
  show the former immediate teardown.
- Three other named USB controllers were unbound at the snapshots with
  deferred probes in the retained messages. The power-management link
  reported a link-creation failure. This was a concrete investigation lead,
  not yet proof of the cause of all missing external USB devices.
- Later slots contained the boot-device-timeout observation. Native live-
  root and desktop boot remained unresolved. The logger was still executing
  near 64 seconds; that did not prove indefinite kernel health.
- The USB logs directory still contained zero files. The installed UKI and
  menu hashes still matched the dt19 manifest. Persistent evidence was in
  firmware, also now in the local recovery directory; the RAM ring alone did
  not survive reboot.
- The owner reported continually flashing dashes. Their meaning was not
  established by these records; do not infer a crash or successful boot from
  that animation alone.

Native bounded checkpoint capture was then demonstrated for that boot,
including late timeout evidence. Existing slots stayed occupied and would
disarm another capture until separately authorized backup, clear, and absence
verification. Firmware runtime calls could still hang on broken firmware; the
bounded budget reduced risk but could not guarantee safety or survival
across every failure.

---

## 11. dt20: early USB-provider modules and a live-root shell

Superseded on the physical USB by the next revision; the failed dt20 native
evidence below is preserved and the instructions are historical.

Source: `../dt20-usb-shell.md`; comparison: `../dt20-native-log-comparison.md`.

### 11.1 Current state at the time of writing

The USB live volume held the dt20 revision. Only the UKI and loader menu
were changed, with physical-disk and volume identity, prestate hashes,
verified prior-revision rollback backups, temporary-file flushing, and
post-write readback. No formatting, partition changes, internal-disk, BCD,
BIOS, or boot-order changes. The native dt20 test still failed to enumerate
external USB or mount the live root. Boot reached the emergency initramfs
shell again. Comparison and recovered evidence are in the native-log
comparison below.

Firmware-checkpoint rearming was completed after explicit user approval
before that test and was then consumed by a new four-record capture. Current
firmware slots were occupied with a new boot ID; recovery was read-only and
did not clear them. Another capture required separately approved rearming.
Pre-test verification text below was not a current empty-slot claim.

A fresh checked backup was retained in a timestamped clear directory. Only
the four named variables under the project identifier were deleted, after
matching the exact prior boot ID and all current raw bytes to the backup.
The clear helper verified all four absent, and a separate read-only export
independently confirmed absence. USB and RAM capture stayed enabled. Earlier
evidence stayed preserved in the prior recovery directory. No boot, security,
vendor, or legacy variables were changed.

### 11.2 Evidence behind dt20

Native dt19 boot with its four valid checkpoints through 64 seconds: at the
later snapshots, one named USB controller was bound but there were two root
hubs, zero external USB devices, and no boot label. Three other controllers
were unbound. The boot-device timeout was seen.

Source, config, and archive checks confirmed:

1. The I2C bus-driver module was configured as a module but absent from the
   dt19 initramfs. Repeater support was present, but the bus needed to
   instantiate those I2C devices was missing. The board's I2C bus hosted the
   high-speed repeater devices; two named USB references used those PHYs.
2. Two interconnect-provider modules were configured as modules but neither
   was packaged. The built-in power-management link called into the packet-
   router framework; the missing provider turned the address-family error
   into a persistent deferred probe at the documented source lines. The retry
   mechanism was intentional, but the missing provider made the deferral
   persistent in that initramfs.
3. The dt19 packed runtime config only forced two filename-charset modules.
   Block and kernel-mode-setting hook discovery had not closed the board's
   non-storage provider dependencies. USB storage, USB-attached-SCSI, and
   USB HID support were already included.
4. Physical USB-A to controller wiring was not established by device tree
   alone. One controller binding did not prove the owner's USB-A port path
   was working.

A separate audit also found one USB physical-layer device disabled while its
controller requested it. That remained a possible blocker for that
controller. The candidate did not enable that PHY, change supply assumptions,
or claim all ports worked. The reset-associated tail interconnect stayed
disabled; no kernel or device-tree bisection delta was introduced in this
candidate.

### 11.3 Changes

- The UKI build script explicitly packed and early-loaded the I2C bus
  driver, the repeater PHY driver, and both packet-router modules, alongside
  the existing filename-charset list.
- The platform-USB gate script and the validator's platform-USB gate
  independently checked both archive presence and the runtime module list.
- Five unit tests covered the complete set, each missing packed module, each
  missing early-load entry, alias forms, and malformed config.
- The old dt19 image failed the new gate as expected and was retained as a
  red-team artifact. That did not retroactively invalidate its correctly
  scoped logger tests.
- Both tested entries added a live-root shell after the normal live-root
  mount. They bypassed the graphical login and systemd for that shell-first
  hardware test. This was not the early initramfs loader and not an
  intentional initramfs emergency shell.
- Kernel, device-tree blob, stub code, hardware IDs, embedded command line,
  checkpoint binary, and logger hooks were byte-identical to dt19. No new
  kernel build was needed.

### 11.4 Exact-candidate verification

All four gates matched UKI SHA256 `081b399d...e09d`.

- Artifact audit: PASS. PE inputs equaled current source artifacts;
  non-initramfs sections unchanged; full initramfs validator; module
  dependency resolution.
- Exact-candidate logger test: PASS. Disposable firmware-variable store:
  flag off had zero records; virtual USB unplug reached the real timeout to
  the emergency prompt; after abrupt stop a new process recovered four
  checksum-valid records; the final payload held zero external USB, missing
  label, and the boot-device-timeout observation; a later flag-on boot with
  existing records preserved every byte.
- Shell-target EFI test: PASS in under ninety seconds virtual time within
  the declared budget. Full EFI to exact candidate to FAT USB to squashfs
  and overlay to shell; actual runtime modules and overlay filesystem;
  log readback; power-off.
- Systemd-target EFI test: PASS in a few minutes virtual time within the
  declared budget. Separate fixture, firmware flag and shell override
  removed solely for that regression; multi-user, userspace logging, and USB
  log readback.

The QEMU shell test confirmed all four newly packed modules in the actual
runtime module list, not just file names. QEMU had none of the real board's
USB and I2C wiring: those gates proved packaging, module loading, boot
chain, and logger behavior, not native external USB operation. Firmware
regression modified only disposable virtual-machine variable storage, not
physical firmware. The earlier failed timeout-observation evidence stayed
retained.

### 11.5 Installed artifacts and rollback

- UKI on the USB loader path: ~244 MB, `081b399d...e09d`.
- Menu on the USB boot path: ~6.2 KB, `98f701d7...27c3`.
- Prior-revision backup retained in a timestamped USB-before directory.
- USB update script dry run then apply: exit zero with verified marker.
- USB verifier: exit zero; re-resolved the named USB disk and FAT32 live
  volume, read back changed UKI and menu plus unchanged loader, rootfs, and
  staging hashes, verified eleven entries and default shell plus logging
  arguments.
- Pre-rearm export retained the prior records while approval was pending.
  After approval, fresh checked backup and scoped deletion completed with a
  verified marker. Latest independent USB result reported firmware slots
  verified empty; an independent pre-boot export had all four slots missing
  with no boot IDs. All USB boot-critical hashes still matched.
- Canonical, alternate, and staging menus synchronized with the USB.

### 11.6 Next native test (historical instruction, result below)

Approved backup, clear, and independent absence verification were complete
for the four owned slots under the project identifier with the expected old
boot ID. The USB verifier with rearm-required check passed. No further
clearing was needed before that one native attempt.

Owner-executed boot with the same USB-A setup, using the on-device entry for
the USB-dependencies plus live-root shell (default).

Acceptance, in order:

1. Real external USB device enumeration, not just root hubs.
2. Live volume found, FAT and squashfs mounted, writable overlay created.
3. Shell on the real live root, with a working external USB keyboard.
4. If typing worked, the root filesystem type query should have reported
   overlay. No commands were requested if the keyboard still did not
   enumerate.
5. Do not exit the shell when it was PID 1. For shutdown use the forced
   power-off command exercised by the QEMU test.
6. If still at the emergency prompt, do not call it a live-root success.
   After rearming, allow about ninety seconds after kernel start for bounded
   checkpoint completion, retain the screen and markers, and return to
   Windows for read-only recovery before another trial. Missing slots never
   proved a crash location.

If the I2C bus then bound but no external USB appeared, the new records and
USB files would decide the next physical-layer, power, or controller change.
Do not stack the disabled-PHY change onto that candidate before the native
result. All generated firmware-bearing UKIs and root filesystems stayed
local-only and must not be published.

### 11.7 Native dt20 result — packaging-only candidate did not reach live root

Comparison source: `../dt20-native-log-comparison.md`.

Scope and provenance: comparison used the owner's pasted screen transcript,
not inspected image pixels, plus a read-only native firmware export in a
timestamped recovery directory. Boot ID distinct from the preceding dt19 ID.

All four recovered records passed the host reader and independent checksum
and hash checks. USB UKI and menu still matched the dt20 update manifest.
The USB logs directory existed but still contained zero files. Recovery
performed zero firmware writes and did not clear any slots. The newly
occupied slots would disarm another firmware capture until separately
approved rearming.

Same failure, different capture channels:

- Missing live-volume device: full initramfs error said the device did not
  show up after thirty seconds; firmware slots agreed with missing label and
  boot-device-timeout observation.
- Late USB checkpoint: screen showed the late-USB saved marker; firmware
  held a checksum-valid late-USB record near 21 seconds kernel uptime.
- Final checkpoint: screen showed the timeout saved marker; firmware held a
  checksum-valid timeout record near 64 seconds kernel uptime.
- Logger completion: screen showed the RAM-capture-stopped marker; that
  marker was not a full console mirror and the firmware slot was saved
  before that later status print.
- Noisy sync-state tail at 19.5 seconds on screen was deliberately filtered
  out of the bounded selected-evidence payload.
- USB files: no claim from the screen; host readback confirmed the logs
  directory had zero files — persistence here was firmware, not USB.

The visible last timestamp near 19.5 seconds belonged to the last displayed
kernel message, not the later untimestamped logger prints. The recovered
final slot proved the logger executed past 64 seconds; the screen did not
establish a kernel freeze at the earlier timestamp.

What persisted beyond the visible screen tail: all three later records said
two root hubs, zero external USB, missing label. One controller bound; three
others remained unbound with deferred-probe messages. Screen and firmware
therefore agreed on the boot failure, and native external USB and live-root
success had not been achieved by dt20. The emergency prompt was not the
requested USB-backed shell.

A newly retained warning appeared in slot 1 about a failed device-link
creation between the power-management link and one USB controller. The old
link-initialization line was absent from these selected snapshots. Absence
in a small filtered payload did not prove the full packet-router and
Type-C path was fixed; the new link warning was an investigation lead, not a
confirmed root cause. Similarly, pending sync-state lines alone did not
identify the supplier blocking the I2C and USB path.

Result: console and firmware were consistent, not byte-identical logs.
Firmware persistence and late capture worked again on real hardware. No full
raw boot log was recovered from USB in that attempt. The dt20 packaging-only
candidate did not achieve native USB or live-root boot. Evidence kept
intact; no further build, media change, or firmware deletion was authorized
by that comparison request alone.

---

## 12. Retraction log (do not reuse the old claims)

- Guaranteed graphical login, normal booted-system package management, and a
  fully closed repo phase from the first image era: retracted when the first
  hardware boot failed. Firmware in the rootfs does not imply availability
  to early drivers.
- Early control-failure verdict (October 9): retracted; the control entry
  never passed a device tree. Fixed with an explicit device-tree pass plus
  staged blob.
- Watchdog-reset theory for the half-second reset: ruled out by identical
  behavior with the watchdog disabled.
- Wall-clock firmware-watchdog theory for the 25-second reset: superseded by
  progress-dependent evidence once interconnect bisection moved the crash
  point twentyfold.
- Single-node south-interconnect reset-site claim: changed nothing; crasher
  was downstream, released by interconnects.
- Display, DSP, wireless, camera, video, and storage-host blacklist
  exclusions: two entries were void (symbols never matched) and the rest
  were modules absent from early boot. Explicitly retracted as exclusions;
  the UFS PHY had never been banned.
- Regulator-cleanup black-screen theory: ruled out when the keep-regulators
  boot also went black.
- Role-switch USB theory: dead; host mode already set in the device tree.
- Raw-handle USB reroute: broken by stale handles resolving to the mailbox;
  replaced with label-based routing under a never-raw-numbers rule.
- Duplicate-pair USB routing: rejected by the interconnect core; replaced
  with a different interconnect target, then a best-effort driver fallback.
- USB-stays-up claim for the early driver workaround: unverified without a
  later hardware trace; not stated as fact.
- Firmware-log ready, survives-any-crash, and no-photos-needed claims:
  retracted in the dt13 audit. Inclusion and flag-off boot were verified;
  firmware logging, persistence, and host recovery were not.
- Power-off as the cause of a missing final slot: retracted. Firmware-write
  or readback failure, logger exit, or disarmed logger could also explain
  it.
- Export rearms capture: wrong. Export was read-only; separate scoped clear
  with backup and absence verification rearmed.
- Re-reading old records proves another capture; missing final record proves
  a hang location; old records contain the continuation warnings; emergency-
  shell transcript proves all controllers stayed bound; host shell mount
  failures prove a builder reboot: all corrected in the logger documents.
  Last visible line lags execution; root hubs are not external devices;
  empty USB logs prove no file was recovered, not why boot failed.
- QEMU packaging, module-loading, boot-chain, and logger gates prove native
  external USB operation: never claimed. They prove packaging and behavior
  only.
- dt18 combined logging syntax: rejected by EFI test, retained as failed
  evidence, never installed.

---

## 13. Gaps not recovered for this history

- No dedicated Phase 3 results file was found in the records read for this
  document. Repo-flow state (fresh-target sync PASS, sandbox caveat) is
  recovered only indirectly from the Phase 4–5 file and the decisions file.
  Do not treat this history as the Phase 3 proof.
- dt18 is covered as failed evidence via the dt19 repair plus build and
  validation filenames in the private run export. No separate dt18 narrative
  was available, and the exact rejected-syntax log text was not re-quoted
  here.
- Several intermediate UKI and menu hashes are quoted by prefix only where
  the full string appeared only inside long tool-call arguments in the
  private export rather than in a reviewed docs file. Full strings used here
  are those printed in full in the docs files named above.
- Native transcripts after dt19 are screen text plus bounded firmware
  checkpoints plus an empty USB logs directory. No full raw native boot log
  exists for dt20. The comparison is consistent channels, not a complete
  log.
- Exact calendar times for some same-day USB swaps are recorded only as
  filename timestamps in result JSON names, not as prose dates. Day-level
  dates are used here where the prose date was the only reviewed date.
- Firmware, driver-store, and raw private-log contents were intentionally not
  read for this public-ready history. Anything requiring those bytes remains
  a gap by policy, not an oversight.
