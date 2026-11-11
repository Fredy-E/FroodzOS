# Current FroodzOS development status

## Identity

| Field | Current value |
|---|---|
| Product target | **FroodzOS `0.1.0-dev`** |
| Selected codename | **Maverick** |
| Intended qualified milestone | **FroodzOS 0.1 Maverick — ARM64 Alpha** |
| Current state | In development; not a qualified alpha release |
| Initial experimental board | Lenovo IdeaPad Slim 3 15Q8X10 / 83N3, Snapdragon X1-26-100 |
| Architecture | AArch64 / ARM64; no universal ARM64 support claim |
| New exact image/build record from metadata work | None |
| Release date / qualified release | Not assigned / none established |

## Scope decision for 0.1 (2026-11-10)

The owner chose the fastest route to a first 0.1: a **limited live alpha without the native Hermes
workstation integration**. Dropping that scope is an explicit owner decision under the promotion policy
(gate 3), not a silent bypass. The Hermes work (cooperative lifecycle component, verified single-file
bundle, privileged-cleanup fixtures) is parked, not deleted; its record is in
[the history note](../history/hermes-track-status-through-20261110.md).

## Evidence boundaries

Saved native/owner observations run through **2026-11-10**. They are observations, not hardware tests
executed by the metadata validator. Source-unit checks, virtual fixtures, saved reports and native
acceptance are different evidence classes. A private development candidate (`0.1.0-dev` identity in
`/etc/os-release`, build `maverick-dev-20261110.1`, owner-only, **not published**) was booted natively by
the owner on 2026-11-10; that is an observation of one candidate, not qualification.

| Capability / gate | What is actually established |
|---|---|
| Native boot, text console | Native observations retained; the private 0.1.0-dev candidate also booted natively on 2026-11-10; not universal-board qualification |
| Keyboard and external mouse | Owner-observed operation; no touchpad implication |
| Wi-Fi | Native observations retained, again working in the 2026-11-10 candidate boots; not every adapter/network or general ARM64 qualification |
| Plasma desktop | Owner-observed desktop with software rendering; GPU acceleration not accepted |
| Display resolution | The panel is 1920x1200. A 1024x768 menu mode had been inherited by the kernel; a fix that returns the firmware's native mode before the kernel loads was applied on 2026-11-10 and is **awaiting owner confirmation** |
| HOME persistence | Different-boot proof accepted and sealed; **do not repeat the HOME challenge** |
| Installed application/settings/tool persistence | Not yet accepted |
| Native Hermes install/authentication | Out of the 0.1 scope (parked); not accepted; do not copy host credentials or runtime profile |
| Touchpad | **Not working.** 2026-11-10 progress: with a diagnostic device tree the touchpad's I2C bus now probes; the device tree's touchpad node describes a different variant (address 0x5d) and no interrupt line is mapped, so the driver refuses it. No guessed interrupt number is accepted. A read-only probe of the ACPI-indicated address 0x38 is prepared |
| Graphics acceleration, audio, camera, USB-C-PD | Unaccepted |
| Battery diagnostics, suspend, power/thermal endurance, final hardware power-off | Unaccepted |
| GRUB menu | Menu v3 applied 2026-11-10 (fewer entries, small font, selectable menu mode); responsiveness awaiting owner confirmation |
| General ARM64 boards / a distribution VM target | Downstream, independently qualified targets; not supplied by unit fixtures |

## Current blockers to a qualified 0.1 alpha

1. **Release qualification is open.** Exact-candidate boot with confirmed display mode, recovery and
   safe shutdown, declared hardware limitations, source/artifact provenance, authenticated artifacts and
   the legal/redistribution/publication gates are not satisfied by a codename catalog or a test count.
2. **Touchpad** is an open hardware item. It may ship as a documented limitation if it is not resolved.
3. **Rights for any public binary image.** Redistribution of the CachyOS repository in other distributions
   is prohibited by its policy, vendor firmware extracted from the owner's installation carries no
   redistribution grant, and the Arch Linux ARM base and branding terms are unreviewed. Public source
   is fine; a public image is blocked until these are resolved or avoided.
4. **Hermes workstation integration** is parked and not part of the 0.1 scope.

No firmware, driver, security-setting or HOME-retest action accompanies this documentation. Private
captures, rejected revisions' raw failure evidence and extracted vendor firmware are not published.
