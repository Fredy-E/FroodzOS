# FroodzOS — current tasks

Updated 2026-10-18 after native dt25b evidence review and the verified USB menu cleanup. This is the current checklist; the original [implementation plan](implementation-plan.md) is historical design, not instructions to erase or rebuild the working stick.

## Verified complete

- [x] **Native dt25b text boot:** systemd PID 1, live overlay, Bash on tty1, multi-user target and a saved typed-command proof. Native boot `6a63f6cc-bab8-4140-a699-cabc59050514`.
- [x] **Native CPU-temperature visibility:** all 20 required CPU/cpuss types in 62 complete samples, 1240 readings, 30.2–36.5 C. This is readout validation, not cooling/fan/thermal-control validation.
- [x] **Clean physical USB menu and real recovery image:** four entries, first entry default; separate dt24 image installed and fully hash-verified. GRUB syntax passes; 11 menu contract tests pass; volume cache flushed; independent on-device readback passes. Main dt25b image, SFS, loader/control boot files and all 48 prior USB log files preserved.
- [x] **Synchronize current project status and task list:** native evidence/review, current menu, preserved fallback and remaining gates recorded in the project docs and Hermes checklist.

## Latest owner retest recovered; graphics repairs in progress

- [x] **New #1 native text retest recovered:** boot `7f84303a-7adb-4ada-a3ef-eb8cec4a722f` saved typed proof and 100 complete live samples of all 20 CPU/cpuss sensors, 37.7–47.9 C. Orderly shutdown reached filesystem sync; final hardware power-down remains unproven. Its final stopping sample is partial and the raw strict collector result remains failed rather than being rewritten.
- [ ] **Observe final hardware poweroff/recovery:** sync and service shutdown alone do not close this gate.
- [x] **Active dt26 repair wave — VM-green, USB handoff done, native graphics attempt pending:** supervisor, logger, harness and build-tools fixes all independently verified (55+33+228+48 checks, zero skips) and formally reviewed. Fresh exact image `dt26a3` built from a parent-approved 31-source manifest, audited passed with readback-verified host copy; disposable EFI runs green — case A text boot 270 s and case BC graphics-refusal/SIGKILL-cleanup 362 s, orderly poweroffs, distinct boot IDs. A CRLF shebang break the VM caught (unit imports hid it) is fixed and re-verified (55/55 on LF bytes). USB handoff committed 2026-10-18: `EFI/Linux/kestrel-live-dt26.efi` (dt26a3, readback-verified) plus 5-entry menu (default still dt25b text; entries 1–3 and firmware exit byte-identical; prior 59 logs and all protected payloads unchanged). See [dt26 repair gates](dt26-native-graphics-repair.md). Next: owner boots entry 4 for the bounded native graphics attempt.

## Native desktop milestone — recovered 2026-10-19

- [x] **Real native graphics preflight:** both recovered dt26 boots passed the exact 20-type CPU/cpuss checks and real `simple-framebuffer` DRM identity with connected 1920x1200 output. All captured CPU samples were complete/in-range: 142 and 67 samples respectively. See [native desktop success](dt26-native-desktop-success.md).
- [x] **Desktop launch observed:** owner reports the desktop loaded; both captures show accepted `live` Wayland sessions. The pixel observation is not uniquely attributed to either boot. Neither a screenshot nor input success has been independently verified.
- [x] **Native owned cleanup captured on one full run:** deadline reached, private GUI stopped, owned session absent, tty2 getty active. The second boot ended its capture early and has no cleanup JSON; preserve that distinction.
- [ ] **Finish bounded Plasma acceptance:** keyboard and external mouse are owner-confirmed working; built-in touchpad is not working. Still confirm visible text recovery and final physical poweroff. Keep the reset-associated accelerated GPU graph disabled.
- [ ] **Native Hermes CLI workstation:** Linux aarch64 is officially supported, but no native Hermes installation has been performed. Both native captures enumerate only network loopback; first establish Internet and a persistent USB workspace suitable for installation. The current volatile 512 MiB overlay and 180-second graphics diagnostic are not a persistent workstation. Do not substitute WSL or modify Windows/internal storage.
- [ ] **Complete peripheral/power enablement and support matrix:** touchpad; wired networking/Wi-Fi; speakers/microphone; camera; all USB/Type-C ports; battery, cooling/throttling and suspend/resume. Loaded modules and started NetworkManager are not functional peripheral tests.

## Deferred downstream work

- [ ] **ARM64 VirtualBox target:** resume after native progress, per the owner's native-first direction. QEMU regression evidence is not VirtualBox or hardware acceptance.
- [ ] **Maintainable general-ARM64 distribution:** final reproducible packaging, own signing/update/repository/recovery chain, additional-board support tiers and firmware/redistribution/license review. Publication remains separately user-approved and currently deferred; vendor-firmware-bearing artifacts stay local-only.

## Current on-stick menu

| Number | Entry | Role |
|---:|---|---|
| **1 — default** | FroodzOS dt25b — Text + CPU temperature logging | Same native-tested dt25b UKI and cmdline; text only, USB logging on, firmware capture off. |
| **2** | FroodzOS dt24 — Text recovery (previous image) | Separate `EFI/Linux/kestrel-live-dt24.efi`, native-tested baseline bytes. CPU sensors unavailable. New menu wiring has not itself been native-booted yet. |
| **3** | Ubuntu Concept — control boot (Try Ubuntu only) | Existing control block and boot files preserved, including its explicit Slim 3 DTB. No new control-boot success claim. |
| **4** | FroodzOS dt26 — BOUNDED graphics diagnostic (opt-in) | NEW `EFI/Linux/kestrel-live-dt26.efi` (dt26a3, VM-green); supervised ≤180 s, guard may refuse to text console. |
| **5** | Return to firmware boot menu | Exit GRUB; no persistent boot-order change. |

Canonical sources: `builder/live-grub.cfg` (4-entry text baseline, unchanged) and `builder/live-grub-dt26.cfg` (5-entry with dt26 graphics opt-in). On-device menu: `E:/boot/grub/grub.cfg`, 3424 bytes, SHA256 `1249291c07d42c4b07c456dfe4fb93c4ab8c792ec3b36672bde33be8a27ac935`, plus `E:/EFI/Linux/kestrel-live-dt26.efi` (dt26a3, 244398080 B, SHA256 `5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26`). Handoff receipt: `testing/boot-failure/dt26-usb-handoff-apply-20261018T193000Z/apply-receipt.json` (dry-run + 8 contract tests + GRUB syntax + identity + flush + readback green; 59 prior logs and all protected payloads unchanged).

Menu evidence/backup: `testing/boot-failure/dt25b-menu-cleanup-20261018T142458148359Z/` (`canonical-before.cfg`, `usb-before.cfg`, candidate, dry-run/apply receipts and independent readback).

Native report: [dt25b native thermal check](dt25b-native-thermal-check.md). Earlier dt24 baseline: [native text success](dt24-native-text-success.md).

## Safety and unresolved housekeeping

No formatting, partitioning, internal-disk, BIOS, BCD, firmware-variable or security-setting changes were made. Firmware slots remain preserved/occupied; capture is off in both FroodzOS entries. The USB dirty flag remains set despite read-only CHKDSK finding no problems; no repair was performed or silently marked complete. No USB log was deleted. Names/labels/logger GUID contracts remain unchanged.
