# Current status — 19 October 2026

This page and the [dt26 native report](dt26-native-desktop-success.md) supersede
older top-level progress descriptions. Historical reports remain available and
are not rewritten into success stories.

## Accepted milestones

- Native boot chain → USB source → squashfs/live overlay → systemd.
- Interactive native tty1 Bash and saved typed-command proof on dt24/dt25b.
- Native dt26 CPU/DRM preflight and real live-user Wayland session in both
  recovered boots; owner-reported visible Plasma desktop.
- Keyboard and external mouse work per owner. Built-in touchpad and Wi-Fi do not.
- Exact required 20-type CPU/cpuss readout; this proves temperature visibility,
  not fan, cooling or throttling control.
- First recovered dt26 boot captured deadline cleanup: private GUI stopped,
  owned session absent, tty2 getty active. The second lacks that final snapshot;
  absence alone is not a hang or cleanup verdict.
- Final dt26a3 exact-image EFI A and B+C virtual regressions passed. B establishes
  fail-closed refusal on absent physical sensor/DRM inputs; C uses explicitly fake
  payloads to test the lifetime graph. Neither is a native compositor test.

## Known-working local boot artifacts

The images are **not uploaded**. These hashes identify the local diagnostic
baseline; they are not download links or public release assets.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| dt26a3 opt-in UKI | 244398080 | `5ff40d9cfe1f4b4435c79532ad4045873344a3a1130cac5eec59fa65f28e8b26` |
| dt25b text/default UKI | 244424704 | `b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753` |
| genuine dt24 text recovery UKI | 244503552 | `4fca331543a347da2d431631ae002f90046507e485765ef24f383257902edc02` |
| Shared live squashfs | 1748525056 | `5041e7d0e9c6af0a5c754f083ca9d77197bf226854f4db3a781b544725d94d4c` |

Current local menu: #1 dt25b text (default), #2 separate dt24 recovery, #3 Ubuntu
Concept control, #4 bounded dt26 graphics, #5 firmware-menu exit. The canonical
five-entry source is `builder/live-grub-dt26.cfg`; the older
`builder/live-grub.cfg` is the historical four-entry text baseline.

## Not accepted / remaining

- Native wired DHCP, routing, DNS and HTTPS connectivity. USB-network modules
  being present does not prove the attached adapter's chipset or Internet access.
- Persistent USB workspace; current writable overlay is only 512 MiB in RAM.
- Native Hermes installation and an appropriately supervised developer session.
- Touchpad, Wi-Fi, GPU acceleration, audio, camera, full USB/Type-C coverage,
  battery, suspend/resume, fan/cooling/throttling and final physical poweroff.
- Full M1 acceptance (desktop + input + wired network + USB + safe shutdown).
- Native Windows-on-Arm VirtualBox target; deferred under native-first scope.
- General ARM64/multi-board compatibility, reproducible final image packaging,
  maintained signed update/repository/recovery infrastructure and binary rights
  clearance. No project completion percentage is recalculated in this snapshot.

## Non-negotiable safety contracts

Preserve known-working text recovery and the bounded 180-second GUI guard. Keep
accelerated GPU/GMU/MDSS paths disabled until their own reviewed experiments.
Native boots remain owner-executed. No internal-disk install, formatting, raw
physical-disk writes, BCD/BIOS/security/boot-order changes, dirty-flag clearing or
unscoped firmware changes are authorized by this repository.

Private firmware and signing secrets are local-only. Original evidence and
failed runs are retained locally. Missing logs are not proof of kernel death;
filesystem sync is not proof of final hardware poweroff.
