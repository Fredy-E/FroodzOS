# Current status — 28 October 2026

This page, the [timeline](TIMELINE.md) and [current task list](TASKS.md)
supersede older top-level status descriptions. Historical reports and failed
experiments remain history, not retroactively successful runs.

## Accepted native observations

- USB/live-root boot, systemd, interactive tty1 text console and typed proof.
- Owner-observed Plasma desktop; keyboard and external mouse working.
  Software framebuffer only; no accelerated GPU acceptance.
- Built-in WCN7850 Wi-Fi working: owner confirmation plus ath12k/MHI,
  activation, DHCP on `wlP4p1s0` and `CONNECTED_GLOBAL` in the recovered
  dt27 boot. Older dt26 reports with only loopback are historical, not the
  current networking status.
- All exact 20 CPU/cpuss sensor types observed. Readout is not cooling,
  fan-control, thermal-throttling or sustained-load validation.
- One native graphical diagnostic captured owned-session cleanup. The other
  lacks the final cleanup snapshot; final physical poweroff remains open.
- **HOME file canary accepted across two different native boots** (creation
  `c62c897a...`, verification
  `f30b3a73...`): challenge checksum valid with
  private permissions, owner UID 1000, the same USB ext4 filesystem and the
  same versioned overlay generation. This accepts the canary file only, not
  installed settings, tools, peripherals or full workstation readiness.
- Ordinary native CLI/login observed as normal user UID 1000 in the 28 October
  canary captures (create `c62c897a...`, verify `f30b3a73...`); hardened
  account policy/password security, installed settings/tools and full
  readiness remain open. Sourced from accepted private receipts and owner
  transcript reflected in native-home-persistence-accepted.json and workspace
  parent assessment; no private metadata reproduced.

## USB persistence and guarded workstation

The approved 32 GiB USB tail was written in full and independently
read back (34,359,738,368 bytes), with identity, partition boundaries,
superblock and neighboring-data preservation checked.

A separate opt-in persistent text workstation image has been built, reviewed
and applied as the sixth displayed menu item. It retains password-based local
login, a continuously monitored thermal/space guard, independent recovery and
unchanged graphical diagnostic limits. Password setup occurs locally on the
first real boot, not through copied Windows credentials.

The exact candidate passed one uninterrupted emulated-EFI A/B/C invocation,
`dt27ws-ws1-a12`, exit 0: A 244.89 s (17 checks), B 116.71 s (18 checks),
C 212.42 s (15 checks), all 50 true. A establishes opt-out text boot; B proves
bad-UUID initramfs refusal; C proves sensor-dependent guard refusal and
poweroff on the virtual machine. Neither B nor C proves the native success
path. Parent-run harness suites contain 196 tests per platform with one
platform-specific lock skip each. The native validator passes 52 tests on
Windows (one POSIX-permission skip) and Linux (zero skips).

Fresh read-only USB verification on 26 October matched all 11 current
protected files and all 108 pinned log files. The handoff changed only the new
EFI and menu; it did not change firmware, format/repair filesystems or alter
other images.

On 27 October a small one-command readiness exporter (launcher, exporter and
start note) was deployed with a cache flush and independently read back: all
destinations verified and all previously protected files, the original
validation kit, prior logs and the menu unchanged. The owner later ran it
natively from the workstation entry: non-root capture and privileged USB
export succeeded, and recovery confirmed the protected files, kit, exporter
and prior logs unchanged with new logs archived and zero recovery writes.
Native export is proven; it did not by itself close battery, touchpad or
reboot acceptance. The same 27 October capture showed the battery collector
TypeError without a safe location; the safe location at `_safe_read_text:696`
was identified only by the later 28 October v2 readiness diagnostic (cause
and fix open). The same capture also showed no touchpad, audio/camera
presence-only, and all 20 sensor types as an instantaneous sample only.

On 28 October a versioned workspace validator/proof package (four files) was
reviewed, applied with a cache flush, and independently read back: all
destinations verified and all previously protected files, the kit, the
exporter and all prior logs unchanged. No boot, menu, partition, firmware or
settings change was made by the deployment itself.

## Local-only artifacts, not release downloads

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Guarded CLI workstation UKI | 244478976 | `4cbe283e6231d7e8269b4e89ade38b6a769e9abfa8bbfa00d8e200b1793ac222` |
| dt27 Wi-Fi/graphics UKI | 244398080 | `4fb18edfb4ae2f2727658b5c94f43a3ccee78dd33d8e952a1b11a656ddd90867` |
| dt26a3 bounded graphics UKI | 244398080 | `5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26` |
| dt25b default text UKI | 244424704 | `b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753` |
| Independent dt24 recovery UKI | 244503552 | `4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02` |
| Shared live squashfs | 1748525056 | `5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c` |
| Seven-entry device menu | 4285 | `74dc6cbf25727aec42f21fdd40e808f1eded3019fc85e9d3cd53f56b9f726bee` |

Current displayed order: default text; separate text recovery; Ubuntu Concept
control; bounded dt26 graphics; experimental dt27 Wi-Fi/graphics; guarded
persistent text CLI; firmware-menu exit. GRUB default index 0 and timeout 10.
The gfxterm/console-fallback mitigation is applied; whether it fixes the
reported post-keypress lag is still awaiting owner confirmation.

## Not accepted / remaining

- Hardened firstboot account policy, password security and password-required
  sudo remain open. Ordinary native CLI/login observed as UID 1000 in the 28
  October canary captures; the HOME canary does not prove installed settings,
  tools, peripherals or full workstation readiness.
- Independent text recovery and observed final physical poweroff.
- GRUB responsiveness. gfxterm, short titles, 10-second timeout and
  console fallback are applied. Firmware text-repaint cost remains a
  hypothesis; owner feedback must confirm whether keypress lag is fixed.
- Native Hermes installation/configuration. The HOME-canary prerequisite is
  now passed; lean bootstrap preparation and separately reviewed
  handoff/install/configuration remain owner-executed next steps. Actual
  application settings and tool persistence still need their own evidence.
  No local model weights, Windows profile/runtime or secret transfer; no WSL
  installation as a substitute.
- Touchpad function: I2C address is grounded, physical Linux interrupt line is
  unknown. ACPI pin 960 is not a Linux TLMM GPIO number; no guessed IRQ change.
- Battery behavior: the 27 October TypeError had no safe location; the 28
  October v2 diagnostic safely reported the location at `_safe_read_text:696`;
  cause and fix remain open.
- Audio, camera, wired connectivity, full USB/Type-C coverage, cooling/throttling,
  suspend/resume, exhaustive wireless and accelerated GPU.
- General ARM64/multi-board compatibility, final reproducibility, maintained
  signing/update/recovery infrastructure and binary redistribution rights.
- Separate ARM64 VM distribution target, deferred until native stability.

## Safety boundaries

Native boots remain owner-executed. Keep the independent text recovery and
180-second graphical diagnostic guard. Preserve known platform workarounds
and keep unaccepted accelerated GPU/GMU/MDSS paths disabled. No internal-disk
install, driver replacement, BIOS/BCD/security/boot-order change, further
partitioning, firmware rearm or dirty-flag repair is implied by this archive.

No image or firmware release is published. Vendor firmware, credentials,
private signing keys and raw private machine logs remain local-only.
