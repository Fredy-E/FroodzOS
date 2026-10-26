# FroodzOS — current tasks

Updated 26 October 2026. See the [timeline](TIMELINE.md) for chronology and
[current status](STATUS.md) for safety limits. Older plans and reports are
historical inputs, not instructions to erase or rebuild the working USB.

## Verified complete

- [x] Native systemd text console and saved typed-command proof.
- [x] Exact 20-type CPU/cpuss temperature readout; not fan/cooling acceptance.
- [x] Owner-observed Plasma desktop, keyboard and external mouse.
- [x] Built-in WCN7850 Wi-Fi: owner confirmation plus native activation/DHCP.
- [x] Public sanitized source/history archive; no binary/firmware release.
- [x] Approved USB-only 32 GiB ext4 partition written in full and independently
  read back; partition, superblock and neighbor preservation checked.
- [x] Separate guarded persistent text-CLI image built and independently
  reviewed; kernel/DTB/stub preserved, only the initramfs changed.
- [x] One uninterrupted real EFI/QEMU A/B/C invocation (`dt27ws-ws1-a12`):
  A 244.89 s / 17 checks; B 116.71 s / 18 checks; C 212.42 s / 15 checks.
  All 50 checks true, distinct boot IDs, process exit 0. Virtual proof only.
- [x] File-only workstation handoff applied and read back; nine other protected
  payloads and 108 prior logs unchanged. Default and independent recovery kept.
- [x] Fresh parent read-only USB check: 11 current protected files and all
  108 pinned log files match. No new native boot is inferred from readback.
- [x] Historical worker audit: 20 transcripts, 19 completed and one interrupted
  B-oracle task superseded by the reviewed harness and real a12 pass. Failed
  runs retained, not erased or blindly restarted.

## Current priority — owner-run native acceptance

- [ ] Boot the guarded persistent text workstation, set the `live` password
  locally and verify real login and password-required sudo.
- [ ] Finish packaging/review/deployment of the small offline native-validator
  handoff. The approved validator passes 52 tests on each platform; its
  readiness exit 0 means a report was produced, not every readiness gate passed.
- [ ] Capture native readiness as the non-root user; explicitly create the
  HOME canary, reboot into the same entry, verify a different boot ID with the
  same ext4-backed overlay generation. Same-boot readback is not persistence.
- [ ] Exercise independent text recovery and observe normal physical poweroff.
- [ ] Owner feedback on GRUB responsiveness after the first keypress. Modest-mode
  gfxterm/console fallback is applied, not yet confirmed to resolve the bug.
- [ ] Install/configure native Hermes after persistence is proved. Curated
  portable skills/bootstrap is prepared; no Windows runtime/profile or secret
  transfer and no local-model collection. WSL is not a substitute native gate.

## Hardware and distribution work still open

- [ ] Built-in touchpad. Address `0x38` on IC20/Linux i2c19 is grounded; the
  physical Linux TLMM interrupt line remains unknown. Do not treat ACPI 960 as
  a GPIO or invent a numeric transform. An isolated no-ICC experiment is not
  native enumeration or function proof.
- [ ] Audio output/input, camera, wired networking, all USB/Type-C ports,
  battery behavior, cooling/throttling, suspend/resume, exhaustive wireless
  coverage and accelerated graphics. Presence does not mean function.
- [ ] General-ARM64 packages, own signing/update/recovery chain, reproducible
  final images, more board tiers and binary/firmware redistribution clearance.
- [ ] ARM64 VM distribution target — deferred until the native workstation is
  stable. The QEMU regression harness is not that separate product.

## Current on-stick menu

| Displayed number | Exact title | Role |
|---:|---|---|
| 1 — default | FroodzOS - Text + CPU temperature log (default) | Native-tested text, RAM overlay |
| 2 | FroodzOS - Text recovery (dt24) | Independent recovery image |
| 3 | Ubuntu Concept - control boot | Preserved control/explicit DTB |
| 4 | FroodzOS - Graphics diagnostic (dt26, bounded) | Existing bounded graphics diagnostic |
| 5 | FroodzOS - Wi-Fi + graphics (dt27, experimental) | Native Wi-Fi accepted; bounded graphics |
| 6 | FroodzOS workstation v1 - Guarded persistent text CLI (opt-in) | USB ext4-backed CLI; native acceptance open |
| 7 | Return to firmware boot menu | Exit; no boot-order change |

Live readback on 26 October: menu 4,285 bytes,
`74dc6cbf25727aec42f21fdd40e808f1eded3019fc85e9d3cd53f56b9f726bee`,
GRUB default index `0`, timeout `10`, gfxterm with console fallback. The old
six-entry baseline is not the current device menu. Existing GUI entries keep
their 180-second guard and volatile overlay; the new persistent CLI is separate.

The actual builder and native boot artifacts are local. This repository's
source archive is not an unattended installer or permission to write internal
storage, alter firmware/security/drivers, repartition, repair the dirty flag,
or relax thermal protections. Preserve working images, logs and recovery.
