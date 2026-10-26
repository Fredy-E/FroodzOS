# FroodzOS — project timeline

One chronological view of the ARM64 port from the first research session to the
current state. Dates come from the archived conversations and the dated reports
in `docs/`; where a later finding corrected an earlier claim, the later record
wins. This page summarizes and links; the linked documents carry the evidence.

The source snapshot here dates to 19 October; later entries document local
work beyond that snapshot. The current update publishes documentation only,
not newer workstation/validator code, private raw logs or boot images.

Status labels used below: **verified** (observed on the real machine or by a
real readback), **component** (tested in isolation), **open** (not yet proved).

## 7–9 October 2026 — research and bootstrap

- Board and firmware research for the Lenovo IdeaPad Slim 3 15Q8X10 / 83N3
  (Snapdragon X X1-26-100), and the decision to derive an unofficial ARM64
  distribution from the CachyOS stack. See [porting design](porting-design.md)
  and [decisions](decisions.md).
- Isolated builder environment (own WSL distro and VHDX), pinned kernel and
  stubble sources, ARMv8-A baseline check, and the first signed-package
  rehearsal. See [bootstrap through dt20](history/bootstrap-through-dt20.md).

## 14–17 October — boot chain bring-up (dt20–dt23)

- **dt20** — early USB-provider modules plus a live-root shell.
  [report](dt20-usb-shell.md)
- **dt21** — USB enumeration and live-root mount succeed on the device.
  [report](dt21-native-usb-success.md)
- **dt22** — the silent `switch_root` handoff is diagnosed and fixed.
  [report](dt22-pid1-handoff-fix.md)
- **dt23** — post-switch proof: writable userspace, keyboard LEDs, root fstype.
  [report](dt23-postswitch-proof.md)

Result at this stage: a real overlay-root Linux userspace on the laptop, with no
desktop yet.

## 18 October — systemd text and CPU temperature (dt24, dt25b)

- **dt24** — interactive systemd text boot: PID 1, multi-user target, Bash on
  tty1 and a saved typed-command proof.
  [report](dt24-native-text-success.md)
- **dt25b** — all 20 required CPU/cpuss sensor types observed: 1,240 valid
  readings across 62 complete samples, 30.2–36.5 °C.
  [report](dt25b-native-thermal-check.md)
- **dt25** — bounded software-graphics candidate prepared.
  [report](dt25-software-graphics.md)

## 19 October — first native desktop (dt26) and source publication

- Owner report: “Goal achieved Desktop loaded!” — user-observed desktop pixels.
  [report](dt26-native-desktop-success.md)
- Public source and sanitized engineering history published at
  [Fredy-E/FroodzOS](https://github.com/Fredy-E/FroodzOS), commit
  `36999afec19392e4ff85b67b3a5bdf548945086e`: 1,125 files, 7,793,608 bytes,
  independently verified against the downloaded GitHub source ZIP.
  [handoff](froodzos-publication.md)

## 20 October — storage cleanup

- 63.27 GiB reclaimed on the build drive; builder VHDX compacted
  119.73 → 56.46 GiB offline after a verified lossless archive; all 42
  historical disk contents remain restorable.

## 25 October — Wi-Fi accepted, persistence created, workstation image built

- **Built-in Wi-Fi accepted as working.** Owner: “The OS wifi is running
  perfectly”. Read-only recovery of boot
  `c3b7343f-a15f-4dcd-a07c-a5754eb13ebc` (12 files, 503,695 bytes) shows the
  WCN7850 enumerating through ath12k/MHI, activation and DHCP on `wlP4p1s0`,
  and NetworkManager `CONNECTED_GLOBAL`.
- **32 GiB USB persistence created and verified.** A new tail ext4 partition
  (`FROODZ_PERSIST`, UUID `129ab898-439c-471d-84e0-2f6f7e155ccb`) was written
  in full — 34,359,738,368 bytes — then independently reopened and re-hashed
  against the pinned source image, with the ext4 superblock checked. The
  original boot partition, recovery image, 10 protected boot files and 108 log
  files were preserved; nothing else on the stick was repartitioned.
- **Workstation image built** as an initramfs-only derivative of the accepted
  dt27 image: 244,478,976 bytes, sha256 `4cbe283e…`. Parent verification shows
  only the `.initrd` section differs, the DTB/kernel/stub are byte-identical,
  and the packed payload carries the 10 seed files, 2 hooks and the 78-member
  Hermes bundle with exact hashes, modes and root ownership.
- **EFI/QEMU validation completed.** The exact workstation candidate passed
  one uninterrupted `--case all` invocation (`dt27ws-ws1-a12`, exit 0):

  | Case | Measured outcome | Seconds | Checks |
  |---|---|---:|---:|
  | A | Opt-out text boot, saved proof, poweroff | 244.89 | 17/17 |
  | B | Bad persistence UUID, initramfs refusal, forced poweroff | 116.71 | 18/18 |
  | C | Missing CPU sensors, guard refusal in journal, poweroff | 212.42 | 15/15 |

  All 50 checks pass with distinct boot IDs. Earlier failures were harness
  defects, not retroactively declared successes: echo could forge literal
  acknowledgments, long serial sends were unreliable, chunks lost shell
  state, and C had no interactive shell because the guard powers off.
  C now sends nothing, attributes its fresh log directory using a pre/post
  snapshot, and verifies the measured refusal chain in the extracted journal.
  Original failures remain retained locally. The final harness has 196 tests
  and independent spec/quality approval; virtual proof is not hardware proof.
- **GRUB menu v2** written to the USB: `gfxterm` at 1024×768 with a console
  fallback, initially six entries and a 10 s timeout — aimed at the reported
  slowdown after the first keypress. Firmware text-console repaint cost is
  the suspected cause, not a confirmed diagnosis. The v1 menu is backed up
  byte-for-byte and the readback passes a real `grub-script-check`; owner
  feedback on responsiveness remains open.
- **Reviewed workstation handoff applied.** The separate UKI
  (244,478,976 bytes, `4cbe283e…`) and a seven-entry menu were read back from
  the USB. The new workstation is the sixth displayed entry; the first
  remains the default and independent dt24 recovery remains available.
  Nine other protected files and all 108 prior logs stayed unchanged.
  This file-only update made no firmware writes or filesystem repair.
- **Touchpad IRQ investigation.** The live DSDT places the FTCS touchpad at
  I²C address `0x38` on the controller that maps to Linux `i2c19`
  (`0x88c000`), and an independent byte-level decode of the `GpioInt`
  descriptors retracted an earlier “unmappable” inference: ACPI pin numbers
  are not Linux TLMM numbers. The actual TLMM line for pin 960 is still
  unknown, so no touchpad IRQ is wired and no function is claimed.

## 26 October — continuation checks and native-validation handoff

- Fresh read-only verification matched the exact USB identity, all 11 current
  protected files and all 108 pinned log files. The seven-entry menu is
  4,285 bytes, SHA-256
  `74dc6cbf25727aec42f21fdd40e808f1eded3019fc85e9d3cd53f56b9f726bee`.
- Parent-run suites: native validator 52 tests on Windows (one POSIX-only
  skip) and Linux (zero skips); EFI harness 196 tests on each platform (one
  platform-specific lock skip each). Guest suites use a clean PATH rather
  than altering WSL or accepting a broken Windows-side shell as a Linux tool.
- Twenty historical worker transcripts were reconciled: 19 completed and one
  interrupted B-oracle task, superseded by the reviewed, passing harness.
  Its failure was retained; it was not blindly restarted.
- The small offline native-readiness/persistence-challenge handoff is being
  packaged. The owner still has to boot the workstation, set the password
  locally, create the canary and verify it on another boot. No native
  persistence or new hardware acceptance is claimed.

## Current state

| Area | State |
|---|---|
| Native text console, thermal logging | verified |
| Built-in Wi-Fi | verified |
| Desktop (Plasma) | observed by the owner (dt26); full input/session acceptance open |
| 32 GiB persistence | media written and fully read back; native reboot persistence **open** |
| Workstation image | reviewed, uninterrupted EFI A/B/C pass, applied to USB; native boot **open** |
| GRUB responsiveness | gfxterm mitigation applied; owner confirmation **open** |
| Touchpad | I²C address known; IRQ line unknown |
| Audio, camera, USB-C, power management | open |
| Signed packages, updates, installer, extra boards | open |

No binary or image release is published; the repository carries source and
history only. Firmware extracted from the machine and the private build
workspace stay local.
