# dt25 — native software-graphics candidate (in progress)

Owner direction: continue development before publishing anything. No publication, account, domain or license changes are in scope.

## Target and approach

Progress from the accepted dt24 native interactive systemd console to a bounded native graphical session, preserving dt24 as the fallback. The native dt24 kernel log proves `simpledrm` registered the firmware framebuffer; first investigate that existing path with software rendering rather than enabling the reset-associated GEM/GPU/MDSS dependency graph blindly. This is not accelerated graphics acceptance.

Before any graphical attempt, establish usable SoC-temperature observation. Native dt24 only captured the battery thermal zone; battery data is not a CPU/SoC temperature proof. Exact TSENS dependencies and installed KWin 6.7.5/Plasma 6.7.5/Mesa 26.2.4 launch requirements are being reviewed independently against local pinned sources and rootfs files.

## Implementation/verification gates

1. Freeze the accepted dt24 source, DT, UKI, initramfs, input/USB closure and unchanged logger contracts. **Passed:** `testing/boot-failure/dt25-baseline.json`; frozen sources under `/home/builder/boot-failure-tests/dt25-baseline`. Kernel/source/DT/initramfs match the accepted dt24 UKI and its manifest.
2. Add a read-only fail-closed simpledrm + SoC-temperature preflight, exercised with explicit synthetic fixtures. **Implemented; 17 policy tests passed** (`dt25-graphics-guard-unit-result.json`) after an observed missing-module RED. No trip/fan/clock/voltage changes and no firmware writes. Conservative experiment stop at 80C; missing/invalid temperature data must prevent graphics, not normal boot. These are fixture checks, not native thermal or graphical validation.
3. Review exact TSENS and compositor/session dependencies. Apply only justified local diagnostic changes, with compiled-DT scope and rollback gates. Never enable internal storage or GPU/display hardware by implication.
4. Stage any graphical helpers/units only in the RAM overlay behind an opt-in flag. Retain a text fallback, no password/account edits, no remotely exposed root autologin, bounded runtime/process cleanup and recoverable logs. Preserve the independent bounded firmware/USB logger implementation.
5. Validate the exact candidate, opt-out/failure behavior, thermal policy, input/USB closure, source provenance and VM regression before any file-only media update. VM rendering/input are not native graphics/input proof.
6. Recheck physical USB identity/health and preserved records before any approved update. The prior dirty-volume report and occupied success-record slots remain unresolved prerequisites for new media writes/rearming; do not repair/clear them silently. Keep physical boot user-executed and preserve the known-working dt24 fallback.

## Latest verified state — native text and CPU readings recovered

The owner booted physical **#10** on dt25b and typed `kestrel-proof`. Boot `6a63f6cc-bab8-4140-a699-cabc59050514` saved valid systemd/overlay/Bash/tty1 typed proof and **62 complete samples of all 20 required CPU/cpuss sensors**: **1240 readings, 30.2–36.5 C**, uptime 17.80–115.66 s. Independent line-by-line parsing confirms these counts and values. Current USB UKI/menu/SFS were physically reidentified and fully rehashed; all match expected dt25b/unchanged SFS. Graphics was explicitly off. Full live guard ancestry checks, native graphics, final shutdown and the 120-sample capture finish remain unproven.

Details and exact archive: [dt25b-native-thermal-check.md](dt25b-native-thermal-check.md). Both independent read-only reviews completed (`deleg_1364f870`); no captured blocker prevents another text-only test. Complete typed proof establishes execution/save, though the final console return is not separately logged. The firmware reader confirms all four old dt24 records unchanged and valid; no firmware clearing/rearm occurred. Read-only CHKDSK reports no problems, but the USB dirty flag remains set; no repair performed. Current checklist: [TASKS.md](TASKS.md).

**Handoff correction and subsequent repair:** the former #8 was NOT an untouched dt24-image fallback: it shared the overwritten main UKI with former #10. The owner-authorized cleanup has now installed the actual archived dt24 image as a separate, hash-verified file and **#2 text recovery** entry. The cleaned menu defaults to **#1 dt25b text** (same native-tested image/cmdline); #3 preserves Ubuntu control and #4 exits to firmware. Actual GRUB syntax, 11 menu contract tests, cache flush and independent device hashes pass; prior logs/unchanged boot payloads are preserved. New arrangement awaits native retest. `kestrel-proof` does not print temperatures; separate USB status samples contain them. Its `revision=v2-dt24` identifies the inherited helper, not the UKI. Menu evidence: `testing/boot-failure/dt25b-menu-cleanup-20261018T142458148359Z/`.

## Historical dt25/dt25b integration and pre-native gates

The statements below record earlier gates and are superseded by the native observation above where applicable.

A real private dt25 UKI is built at `/home/builder/uki-v2-dt25/vmlinuz-live.efi`, copied to `testing/boot-failure/dt25-candidate.efi`: **244421120 bytes**, SHA256 `9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb`. The parent independently verified **13/13 provenance checks**, including PE kernel/stub/HWIDs/base-cmdline/uname equality, exact accepted DT25 DTB and new initramfs, matching source hashes, and unchanged dt24 UKI/SFS. Receipt: `dt25-parent-20261018T080733201702Z-integration-probe.json`.

Component reviews pass and the existing **106-test, zero-skip** component run remains recorded. The builder reports 66 validation clauses (32 graphics), 52 board checks and 11 policy checks; these counts were parsed from the real audit. Parent true-chroot execution of packed findmnt/mountpoint succeeds without host library fallback. A full staged multi-user/default/graphics unit check also exits 0 with documentation checks disabled: `dt25-parent-20261018T080854313952Z-full-target-graph.json`. The first full-target exit 1 was missing manpage tooling, **not** an ordering-cycle proof.

**Candidate is not accepted for native/media handoff.** The new test/evidence harness defects are now repaired: the parent independently reran **24 platform-gate + 10 packed tests = 34, zero skips**, including real chroot dependency closure and actual flag-on/off latehooks. All seven original archived JSON hashes and the candidate hash remain unchanged. Receipt: `dt25-fix-parent-20261018-084409-packing-preservation.json`.

EFI text case A passed with normal systemd/live overlay, typed input, logging, graphics disabled and observed VM poweroff. Recovered case B also genuinely passes: Python executes/imports, the real guard reports missing CPU sensors/DRM and refuses the GUI, preserving text and masks. This is absent-hardware refusal proof, not native thermal/pixel acceptance.

**The remaining confirmed blocker is case C:** in actual v2 raw serial `dt25-efi-graphics-fw-off-v2.log:555-586`, both owned fake-payload units were active (parent PID 1147, child PID 1169). SIGKILL delivery returned 0; the parent became failed/PID 0, but the child stayed active/PID 1169. `PartOf=` alone therefore did not enforce death cleanup. These are v2 PIDs, not the worker's separate 1151/1171 v1 example. The recovered JSON remains failed; no inactive-child shortcut is accepted.

`dt25-efi-parent-verdict.json` records the independent decision. Focused wave `deleg_87a89a3f` changed only the two diagnostic units: the private child now has `BindsTo=` plus existing `After=`/`PartOf=`, while the parent removes only the owned launch marker in `ExecStartPre` and `ExecStopPost`. Parent independently reran the **16 focused contract/cleanup tests, zero skips**, all exit 0; receipt `dt25-lifecycle-parent-contract.json`. These are static/private-fixture tests, **not** actual SIGKILL proof. Read-only unit review `deleg_03f10f91` has returned **spec+quality PASS for code scope**. Its sole minor note (dead no-op in the test) is deferred as non-blocking; no production effect.

Fresh build/preparation wave `deleg_869808bc` produced `/home/builder/uki-v2-dt25b` (244424704 bytes, SHA256 `b535444f8a3560b602d2a8549a35389d3914a8b8b4294c7408ca8e1840a11753`) plus `dt25b-candidate.efi`/`dt25b-artifact-audit.json`; the parent verified PE sections, source hashes and old-artifact preservation independently. The prepared EFI harness needed three parent-found repairs (missing Enter on sends, `;try:` one-liner, MainPID string-vs-int); each was proven from guest output, fixed minimally and re-validated (`bash -n` + payload compile) before the next run.

Final v5 run (`dt25b-efi-fw-off-v5`) is **fully green**: Case A 36/36 with typed proof and observed VM poweroff; Case B+C 50/50 with real Python guard refusal on missing CPU sensors/DRM, private SDDM never started, and proven SIGKILL auto-cleanup (parent failed/PID 0, child auto-inactive/PID 0/gone, launch marker absent, 09 USB evidence valid). The old failed `9c1abc4f…` image stays archived and rejected for native handoff. No physical USB or firmware changes occurred.

## Open gates (no local action taken)

- Exact-image native run on the Lenovo (CPU TSENS readings, software-Plasma pixels/input) — still unproven; VM refusal is not thermal/pixel proof.
- Physical USB health (`Volume E: is Dirty`) and four occupied firmware slots — recheck before any file-only media update; no repair/clear performed.
- Media/update decision and any publication remain user-gated.

The separate repaired harness/canonical-wiring review returned **spec+quality PASS**. After unit approval, the next output is a fresh `/home/builder/uki-v2-dt25b` / `dt25b-candidate.efi`; old `9c1abc4fdb4bd0aaee5cd83b2427eb094a6d870f62d59aa56b36d2aa413499fb` stays archived and rejected for native handoff. The new exact image must pass EFI/crash tests, including startup marker clearing, an actually active child before SIGKILL, automatic child death and post-exit marker removal. No physical USB or firmware changes occurred.

## Earlier implementation and review history

The owner requested subagent implementation with the parent as orchestrator after fixing the API key. Wave `deleg_495499a9` assigns disjoint ownership to: (1) TSENS0/1-only DT restoration and derived CPU-sensor policy; (2) opt-in RAM-overlay software-graphics hook/session supervisor; (3) fail-closed guard hardening and focused regression tests. The configured worker route was read back as `opencode-go` / `muse-spark-1.3-contributor` / `xhigh`, with fallbacks `[]`; dispatch acceptance is not provider-execution proof.

The accepted dt24 baseline and previous evidence remain preserved. Late read-only predecessor batch `deleg_e70b62e2` corroborated the two-TSENS approach and normal SDDM/logind software-rendering route. Its stale `slim3-keep.dts` disabled-rail claims are explicitly rejected as a dt24 baseline; current compiled/frozen evidence wins. Its suggested 90C/few-sensor threshold does not replace the active conservative 80C/derived CPU-cpuss sensor policy. Findings and DRM-device-identity hardening were relayed to active writers; `dt25-readonly-predecessor-notes.json` records the distinctions.

New implementation is **not accepted or ready for native testing**. Parent reruns independently confirmed the thermal board's 52 clauses, but reproduced valid kernel-shaped thermal/DRM class symlinks being rejected. Under the actual WSL command, staging attempted 10 tests with one failure, two errors and six skips; supervisor reported OK with all eight tests skipped because of Windows-only root paths. These results supersede any interpretation of the first graphics GREEN report as a working Linux stage/supervisor. Exact receipt/logs: `testing/boot-failure/dt25-parent-20261018T071355462077Z-receipt.json` and matching prefix logs. The receipt's initial parser error was corrected from actual checker stdout without rerunning or overwriting evidence.

Read-only review wave `deleg_7e5a0933` has returned **REQUEST_CHANGES from both reviewers at the spec stage**; quality approval was deliberately not attempted. It independently reconciled the thermal counts (52 board clauses, 22 mutations, 11 policy checks) and confirmed the evidence-reuse and graphics safety gaps. Full actionable summary: `dt25-review-wave1-verdicts.json`. Earlier follow-up steering missed the completed review workers; the now-delivered formal findings were queued to the active fix writers instead.

Based on reproduced parent findings, disjoint fix wave `deleg_b4595d51` repairs (1) immutable tagged evidence helpers, (2) real sysfs-link compatibility without weakening identity checks, and (3) genuine Linux staging/tests plus gate ordering and owned bounded cleanup. No canonical builder/image integration is authorized until review findings are closed and independent verification passes.

After the fixes, independent spec-then-quality review and a single integration/build/validation owner are still required before any media handoff. The parent retains shared docs, the orchestration ledger, review decisions and independent verification.

## Post-fix independent checks (still not accepted)

Fix wave `deleg_b4595d51` returned. Parent reran the actual Linux commands: **71 guard + 14 staging + 16 supervisor tests = 101 tests, zero skips**, all exited 0. The positive kernel-shaped sysfs fixture passed, immutable evidence/collision checks passed on a fresh tag, and all 11 policy clauses passed against the real current guard (not the prior mock). Receipt: `dt25-parent-20261018T073038735715Z-receipt.json`; failed earlier receipts remain intact.

Renewed staged review `deleg_33e1ed91` returned **thermal spec+quality PASS** and **graphics REQUEST_CHANGES at spec**. The graphics review narrowed the remaining blockers to preserved-state rollback and strict overlay-FSTYPE proof with explicitly packed helper dependencies. `dt25-review-wave2-verdicts.json` records the accepted thermal state, non-blocking local-tooling limitations and exact remaining gates. Focused wave `deleg_277a9e45` now assigns one writer only those hook/install/staging-test fixes, plus a separate read-only image/regression integration scout. No canonical builder/image is being changed before these blockers close.

Separately, the parent reproduced the blocking failure path: when an existing text stage and SSH/GUI masks are present, forcing the first graphics-copy failure makes rollback delete all three text helpers and four inherited masks while returning success to boot. Proof: `dt25-parent-20261018T073250139286Z-ordering-rollback.json`; fixture script `dt25-parent-order-rollback-probe.py`. This must be repaired before image integration even though the focused suite is green. No patch is applied by the parent during the read-only review.

A suspected multi-user ordering cycle was **not reproduced** by a minimal `systemd-analyze --root ... verify` fixture (exit 0, no cycle); do not label it a confirmed defect. Full packed-initramfs/ash and staged systemd dependency-graph validation remain downstream integration gates. The absent-findmnt overlay fallback and crash-independent GUI shutdown are also under review, not native acceptance claims.

## Final staging fix — independent checks

Wave `deleg_277a9e45` returned the targeted hook/install repair. Parent reran **71 guard + 19 staging + 16 supervisor tests = 106, zero skips**, all exit 0. The unchanged parent rollback reproducer now records no lost inherited helpers and no lost masks. Receipt: `dt25-parent-20261018T074415894485Z-receipt.json`. Final graphics review `deleg_37cb82f3` has now returned **spec+quality PASS**; `dt25-final-component-review.json` records the exact acceptance boundary. Thermal component review is also PASS.

Sole integration/build worker `deleg_c0d07ae2` / `sa-0-e383596e` completed canonical wiring and the local UKI build. Its first wrapper attempt failed by running `bash -n` on a Python file; that failed record was preserved and the language/exit-status checks corrected before the successful build. The parent subsequently verified the artifact independently, then reopened only the new test/evidence harness gaps listed in the latest-state section. The existing SFS and dt24 UKI remain byte-identical; component approval does not imply final image/native acceptance.

The integration scout's conclusion that EFI firmware was missing is **retracted**: the parent verified the exact existing `testing/boot-failure/uefi-package/usr/share/qemu-efi-aarch64/QEMU_EFI.fd` (3145728 bytes; SHA256 `a996c72d5258dabf5fcb11a64bd22e0cc6673e3d193031feea02ac643f16dad5`). No package installation is needed for that input. `dt25-integration-scout-corrections.json` records this and the real packed-overlay/SFS/systemd/chaos validation boundaries. No new UKI/SFS or physical media acceptance is claimed yet.

No publication, physical USB update/repair, firmware clearing, private-key access, internal-disk/Windows-boot/Kali change is in scope for this wave. A local candidate is now built; exact-candidate EFI/chaos regression proof and the physical USB-health/occupied-slot prerequisites remain open. Workspace and kernel source are tarball/non-Git directories; `git status` returning 128 is expected, not source corruption.
