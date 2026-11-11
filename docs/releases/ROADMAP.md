# Selected identities and recommended engineering milestones

All25 names/classes are selected by the owner in [CODENAMES.md](CODENAMES.md).
The following engineering scopes retain the previously supplied structure
draft's recommendations. They are **not** completed releases, committed dates,
owner-promised feature lists or publication permission. Features can land early;
Hellcat does not defer today's Hermes priority. A failed gate stops promotion,
not all safe source/test work. Current identity remains **0.1.0-dev Maverick**.

**Cross-cutting main goal (all series):** open every kind of file and run other platforms' apps and operating systems as natively as feasible; plan and
feasibility in [UNIVERSAL-COMPATIBILITY.md](UNIVERSAL-COMPATIBILITY.md). It is a direction, not a delivered feature or a dated promise.

| Series | Selected codename | Intended class | Recommended qualification focus — not delivered status |
|---|---|---|---|
| 0.1 | Maverick | Alpha | Qualify the first experimental, board-specific live baseline: native boot, usable text console/input, documented networking, safe shutdown and tested recovery. Establish release provenance and legal/publication gates. Hermes is included only if its own integration is accepted. |
| 0.2 | Chaffee | Alpha | Qualify a repeatable persistent live workspace: preserve the already accepted HOME proof and add real installed-application/settings/tool persistence. Do not repeat the sealed HOME challenge. |
| 0.3 | Hellcat | Alpha | Qualify the developer/AI workstation: native Hermes installation/authentication and skills/tools, bounded process lifetime including privileged paths, and recovery from interrupted setup. This work can land earlier; the name does not defer the current priority. |
| 0.4 | Viper | Alpha | Consolidate the primary laptop desktop and input experience; resolve or explicitly delimit graphics, touchpad, diagnostics and usability gaps. Close beta-blocking safety defects. |
| 0.5 | Raptor | Beta | First qualified beta of the declared target configuration: cohesive desktop/live workflow, critical input/network/power/thermal behavior verified, support matrix and known limitations published. |
| 0.6 | Pershing | Beta | Qualify the maintained update lifecycle: project-controlled signed package/repository integration, tested updates and recovery. This is not permission to postpone artifact integrity or redistribution checks until 0.6. |
| 0.7 | Apache | Beta | Qualify installation and migration on disposable targets first, then separately approved owner targets; include interruption/data-preservation/recovery tests. A live-only alpha does not imply an installer. |
| 0.8 | Wolverine | Beta | Run bounded endurance, regression and fault-injection qualification after thermal/power safety is established; verify persistence, updates, suspend and recovery under the declared support contract. |
| 0.9 | Nighthawk | RC | Freeze the intended first-stable feature set and qualify release candidates. No open critical safety/data-loss defects in the supported configuration. Rebuild/revalidate actual Sherman artifacts rather than just renaming Nighthawk binaries. |
| 1.0 | Sherman | Stable / major generation | First maintained stable baseline for explicitly qualified hardware. Documented support/security policy, signed distribution/update path, matching sources, tested install/live/recovery workflows and accepted supported features. |
| 1.1 | Mustang | Stable feature release | Extend the stable foundation to an independently qualified additional board or VM target, without implying that shared ARM64/SoC identity establishes compatibility. |
| 1.2 | Bulldog | Stable feature release | Strengthen stable-platform reliability, security maintenance and recovery behavior; security is already a requirement before this release, not a feature deferred until Bulldog. |
| 1.3 | Corsair | Stable feature release | Add a deliberately selected and qualified workload/profile or use case on supported targets; preserve compatibility and maintenance commitments. |
| 1.4 | Phantom | Stable feature release | Deliver measured kernel/desktop/device compatibility improvements across the supported matrix, retaining the stable upgrade contract. |
| 1.5 | Super Sherman | Enhanced stable | Enhanced stable 1.x consolidation: mature supported features, maintenance and upgrade preparation before Abrams. Retain both Sherman 1.0 and Super Sherman 1.5 as separate selected identities. |
| 2.0 | Abrams | Stable / major generation | Second major platform generation, only when a substantial approved baseline/architecture/compatibility change justifies a major version; provide migration and recovery evidence. |
| 2.1 | Thunderbolt | Stable feature release | Measured reliability/performance refinements to the qualified Abrams generation; no speed claims from the aircraft name. |
| 2.2 | Bradley | Stable feature release | Deeper integration of approved desktop, device and management capabilities within the maintained 2.x contract. |
| 2.3 | Stryker | Stable feature release | Qualified portability and laptop/mobile-operation improvements on explicitly tested targets. |
| 2.4 | Paladin | Stable feature release | Mature the 2.x support, maintenance and migration path before the next major generation. |
| 3.0 | Blackbird | Stable / major generation | Third justified major platform baseline with qualified migrations, maintenance and support scope—not a date-based renumbering. |
| 3.1 | Spectre | Stable feature release | Add qualified specialized capabilities/workloads appropriate to the supported platform. |
| 3.2 | Hornet | Stable feature release | Broaden verified use cases and target profiles while retaining the 3.x maintenance contract. |
| 3.3 | Valkyrie | Stable feature release | Graduate sufficiently validated experimental engineering into the stable feature line. The Valkyrie name does not make unstable defaults acceptable. |
| 4.0 | Banshee | Stable / major generation | Fourth justified major generation, with its own approved scope, migrations and evidence. No 4.1+ codename is assigned. |

## Main goal mapped onto the series (proposal, 2026-11-11)

The cross-cutting main goal ([UNIVERSAL-COMPATIBILITY.md](UNIVERSAL-COMPATIBILITY.md)) lands in the selected series as below. The
names and their order are the owner's; the "main-goal focus" column is a **recommendation, not a promise or a date**, and every item
passes the same gates as any other feature (rights review, hardware test, honest release notes).

| Version | Codename | Main-goal focus (recommended) |
|---|---|---|
| 0.1 | Maverick | Qualify the first live baseline; the goal and the extension catalogue are recorded. |
| 0.2 | Chaffee | **Phase 1 first slice:** archive, document, image and media handlers in the image and a first "Open Anything" launcher. |
| 0.3 | Hellcat | AI workstation (Hermes) and **Phase 2 start:** Windows programs through Wine with FEX-Emu or Box64. |
| 0.4 | Viper | Close the desktop and hardware gaps the compatibility layers need: brightness, battery, GPU acceleration, touchpad gestures, audio. |
| 0.5 | Raptor | First qualified beta with a published support matrix, a tested Windows-app set and **Phase 3:** Android apps through Waydroid. |
| 0.6 | Pershing | Signed update lifecycle that also covers the compatibility packages. |
| 0.7 | Apache | Installer and migration. |
| 0.8 | Wolverine | Endurance and regression testing of the compatibility layers. |
| 0.9 | Nighthawk | Freeze the first-stable feature set, including the declared compatibility set. |
| 1.0 | Sherman | Qualified files, Windows programs and Android apps on the supported hardware, with an honest matrix. |
| 1.1 | Mustang | A second board or VM target, with the compatibility set retested there. |
| 1.2 | Bulldog | Security hardening, including sandboxing of foreign executables. |
| 1.3 | Corsair | **Phase 4:** whole-OS guests (QEMU/KVM) where the hardware allows. |
| 1.4 | Phantom | Compatibility improvements: GPU translation and more formats. |
| 1.5 | Super Sherman | Consolidate and widen the catalogue. |
| 2.0 | Abrams | Second generation, only with a substantial justified change. |
| 2.1 | Thunderbolt | Measured translation-speed improvements. |
| 2.2 | Bradley | "Open Anything" fully integrated in the desktop. |
| 2.3 | Stryker | Laptop and mobile operation, including Android apps. |
| 2.4 | Paladin | Mature the 2.x maintenance and migration path. |
| 3.0 | Blackbird | Third generation. |
| 3.1 | Spectre | Specialised emulation: legacy and console platforms. |
| 3.2 | Hornet | Broaden use cases and target profiles. |
| 3.3 | Valkyrie | Validated experimental capabilities, for example macOS command-line tools through Darling. |
| 4.0 | Banshee | Whatever remains feasible. |

iOS apps and macOS GUI apps stay *not feasible* unless the technology or the law changes.

There is no automatic date/percentage progression. Security, integrity and legal
checks apply before each artifact, not only at their named later milestone.
Support stays board/configuration-specific. No 4.1+ name or release date is
assigned. See [POLICY.md](POLICY.md) for admission and promotion gates.
