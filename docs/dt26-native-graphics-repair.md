# dt26 — native graphics repair after the #1 text retest

## Owner direction and recovered evidence

The owner booted the cleaned-menu **#1**, entered `kestrel-proof`, waited more than 90 seconds and saw no further visible progress; they authorized fixes and requested a percentage update. Do not send them through another unchanged text-only round expecting a desktop.

New native boot: `7f84303a-7adb-4ada-a3ef-eb8cec4a722f`. Complete typed proof saved: systemd PID 1, overlay, Bash/tty1, multi-user and USB logger active. The actual cmdline has **`kestrel_graphics=0`**. Waiting is not a desktop-launch trigger.

Archive: `testing/boot-failure/native-dt25b-7f84303a-7adb-4ada-a3ef-eb8cec4a722f-20261018T150552197272Z/` (11 hash-preserved files, 497191 bytes). All 100 initializing/running thermal samples contain all 20 required CPU/cpuss readings, in the observed range **37.7–47.9 C**. The final sample is partial while the system is `stopping`: four required readings are missing, none of its numeric values is out of bounds. Preserve the raw collector's all-samples failure/exit 1 rather than silently weakening it. `parent-retest-verdict.json` distinguishes accepted live samples from this shutdown fragment.

Orderly shutdown and filesystem sync are captured (`systemd-shutdown` at monotonic 177.655291s); final hardware power-down is not proven. The earlier collector attempt at suffix `20261018T150439253494Z` is preserved: its obsolete fixed #8 menu audit raised IndexError after raw archival. That is a host collector defect, not a native crash.

## Implementation wave (in progress)

Wave `deleg_58c7d332`, disjoint ownership:

1. **Read-only native log / integration scout** `sa-0-f4d83615`: classify new boot and scout exact-image build/runtime tests. No edits, builds or VM execution while writers are active.
2. **Session contract writer** `sa-1-19ca1857`: owns only graphics supervisor and its focused tests/new evidence. Verify the actual systemd/logind properties before fixing suspected numeric User / Name / absent UID / empty Wayland Display mismatch. Query/list/detail errors must refuse GUI, not turn into a vacuous empty baseline. Preserve strict ownership, thermal bounds, 180s runtime, 25s cleanup and foreign-session safety.
3. **Observability writer** `sa-2-e5a4b363`: owns root USB logger, text proof/bashrc, parent graphics-unit output directives and new focused tests. Provide explicit text-only vs requested-GUI messages and real CPU readout. Persist exact bounded graphics preflight/cleanup outcomes through the already validated USB logger; supervisor stays /run-only. Preserve atomic last-good writes, byte/time budgets, startup/typed markers and normal boot on logging errors. Extend logging only for GUI opt-in long enough to cover bounded cleanup; don't merely assume 120 sleeps equals 120 seconds.

Parent owns shared docs/ledger/review/integration/media handoff. No writer may alter kernel/DTB/SFS/accounts/USB/firmware or publish anything. No secrets/private keys/shadow. Dedicated CachyOSBuilder only; Kali untouched.

**D reclaim: 11.8 → 27.5 GiB free.** Stale in-guest trial builds (36 superseded `uki-v2-*` dirs, baselines/current kept) plus journal vacuum freed 15.7 GB; `fstrim` + full WSL shutdown + `Optimize-VHD -Mode Full` compacted the D:-resident builder disk. No evidence touched. Admin rights confirmed, Hyper-V module present.

**VM case A (dt26-efi-dt26a3, fixed build) passed: 270 s, orderly poweroff.** Rerunning the 55 supervisor checks against the LF-only file and the BC graphics/SIGKILL case next.

## dt26 build + audit done; VM case A exposed two harness-contract drops (fixed), rerun blocked on D space

**Fresh image built and audited.** Parent-approved 31-source manifest (`dt26-source-manifest-v2-dt26.json`, all hashes verified live), canonical build `dt26a1`: UKI 244398592 B `b81479e5…`, initramfs 191544368 B `09062da5…`, kernel/DTB/SFS frozen. Audit receipt `dt26-audit-dt26a1/dt26-artifact-audit.json`: **passed true**, host copy `dt26a1-candidate.efi` readback-verified, old artifacts preserved. Gate suite 48/48.

**VM case A (dt26-efi-dt26a1) booted healthy but harness reported false.** Guest: systemd, overlay, multi-user, typed proof saved (`KESTREL_TYPED_COMMAND_OK`, helper v2-dt26), orderly poweroff in 258 s. Two harness-side drops, both present in dt25b and lost in the dt26 rewrite: the A guest command never echoed the boot ID to serial (bid stayed `unknown`, so every content check read empty), and both menu templates lost the machine-readable `KESTREL_EFI_MENU_REACHED` echo. Parent restored both (2 template lines + 1 send line, mirroring BC); a patch-tool escape corruption on the adjacent send line was caught and repaired, od-verified byte-identical to the proven pattern. New hashes recorded in the ledger; prior harness approval basis noted as superseded by this delta.

**Rerun (`dt26a2` prefix, ready) is blocked: D: has 11.02 GiB free, need 12.75 GiB.** The builder vhdx lives on D:, so the dt26a1 FAT/build/audit genuinely consumed it; `fstrim` does not shrink the vhdx. Not deleting archived evidence or user files, not lowering the 10 GiB reserve. **Need ~2 GiB freed on D:** easiest is the user deleting something, or explicit approval for the Optimize-VHD offline-compact path (requires full WSL shutdown). Do not reboot into anything yet — USB is untouched (dt25b text still installed).

## Parent logger final rerun

The parent independently reran all four logger suites against the watchdog source (`9ebf9922…`): **33 passed, zero failures/skips**, sources byte-identical before/after. Receipt: `dt26-parent-logger-final-20261018T180504139204Z/result.json`. One parent-harness lesson recorded: running these suites with `TMPDIR` pointed at a root-owned dir breaks their `unshare -rm` kmsg bind (exit 45); default `/tmp` is required. Formal spec/quality review `deleg_863677f4` is running. No VM/FAT/media ran.

## Final harness counterexample rerun

The parent reran the completed parser/harness/lock-lifecycle suites: **228 checks passed, zero failures/skips**, with unchanged source hashes. It also re-executed the concrete counterexamples: a real unrelated lock-holder is now refused, BC correctly budgets zero new FAT allocation (while the same free space still refuses pre-allocation), and injected log-open failure creates zero fake QEMU processes. Receipt: `dt26-parent-harness-fix-verification-20261018T165133307907Z/result.json`. Formal spec/quality review `deleg_be649d99` is pending. These are unit/private-fixture checks; no real FAT or VM ran.

## Final supervisor rerun and logger coverage gap

The parent independently reran the corrected supervisor's four suites: **55 run, 55 passed, zero skipped**, SHA256 `7ece0b64b70df38402d4858d84ed28274c739ba85b9ec281ff1573036ea31fa9`. Receipt: `dt26-parent-session-final-20261018T164807600438Z/result.json`. This includes actual file-fsync EIO and full session-path no-start regressions. Fresh formal review `deleg_bdc3212c` is pending; native graphics is still not accepted.

The observer writer reported 27 tests green with true monotonic/per-call timeout fixes and private mount namespaces. Parent source inspection still found unwrapped startup/final and intermediate filesystem commands, and namespace setup that did not fail fast on required mounts. `deleg_69e0622b` is applying one bounded whole-graphics watchdog and checked fixture setup, with slow-sync/copy/TERM-resistant tests. Do not mistake per-journal timeouts for a whole-logger bound, and do not mark watchdog expiry as normal loop completion. No new image/media yet.

## Corrective implementation — earlier independent verification

Parent reran all three session suites in CachyOSBuilder: **49 run, 49 passed, zero skipped**. This verifies the empty/partial/Remote/session-path fixes, not native graphics. Receipt: `dt26-parent-fix-verification-20261018T160145495817Z/result.json`.

The same isolated production-code probes still found concrete remaining failures: the supervisor treats file-fsync EIO as successful persistence; observer accepts `detail:null` over last-good and reads its old destination without a byte limit; a requested 2-second loop takes 4.1009 seconds with stale per-call timing, 4.1049 seconds with a TERM-resistant ordinary command, and 3.1119 seconds when timeout is missing. These are not kernel D-state cases. Corrective wave `deleg_05bd294e` owns the narrow IO/bounds fixes and private mount-namespace E2E fixture safety. No build/USB acceptance yet.

Initial frozen-runtime work is **partial only**: a 16,209,062-byte subset proves chvt/timeout, but other clients still use builder-library fallback, Qt/KDE transitive dependencies were not staged and Python lacks encodings. `deleg_ad4fb199` is completing hermetic recursive closure in a new subset; no compositor may run. `deleg_5724fe83` prepares build/audit tooling only, gated by a future parent-reviewed source manifest.

The newer frozen subset now has **18/18 parent-reexecuted core/PAM ELF loader checks passing with no host fallback**, plus isolated frozen Python stdlib and Bash 5.3.20 clock-feature checks. Parent byte comparisons match SFS for SDDM, KWin and loader. Receipt: `dt26-parent-runtime-verification-20261018T162447162091Z.json`. The frozen Bash really provides `BASH_MONOSECONDS`; wall-clock fallback is not required by this image. Snapshot supervisor imports are of the earlier source hash and do not approve pending IO changes.

The Qt5 generic `sddm-greeter` is broken, but **the source image also contains `sddm-greeter-qt6`**. Treating the generic path as the actual required target would be premature. `deleg_defdc0af` resolved shipped defaults and the Qt6 candidate without launching a display. Parent independently re-executed five SDDM/Qt6-greeter/helper loader checks and the documented config-only `--example-config`; all returned zero, and Qt6 greeter bytes match the SFS (`95664832…`). Receipt: `dt26-parent-sddm-verification-20261018T164002546367Z.json`. No package/config repair was needed. Runtime greeter-suffix selection remains unproved, so static availability is not a successful login claim.

**Scope clarification:** Plasma's selectable session is Wayland-only, but the stock SDDM display-server default is `x11`; these are separate layers. No X11 Plasma fallback was added. The frozen autologin is `User=live`, `Session=plasma`, with desktop Exec `/usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland`. Actual display/PAM/QML/DRI behavior still requires the bounded native trial.

The prior reviewers' nominal PASS/APPROVED verdicts are **not accepted by the parent**: they waived explicit monotonic/bounded-call and IO-failure requirements despite reproducible counterexamples. Ordinary command stalls and injected EIO are not covered by the kernel D-state caveat. Corrective wave2 remains required; native GUI is still unvalidated.

The prepared build/auditor tooling also remains **unaccepted**, despite 28/28 independently rerun gate checks. The parent reproduced acceptance of LF-suffixed literals/wrong source identifiers and a premature `passed:true` receipt after a copy failure; source review found a different lock from the shared pipeline and an SFS path the actual EFI schema rejects. Receipt: `dt26-parent-artifact-gates-parent-20261018T163419914719Z.json`. `deleg_fe998055` corrects only these new tooling files, their explicit environment/provenance and storage accounting. No reviewed source manifest or build has been authorized.

## Initial implementation — preserved historical RED findings

Wave `deleg_58c7d332` returned session/observability source changes and reported focused green tests. These are not accepted for build or media. Formal reviews `deleg_f2aba956` returned **REQUEST_CHANGES for both at Stage1**; quality review was not run. `dt26-review-wave1-verdicts.json` records their concrete requirements.

Fix wave `deleg_3a848860` assigns disjoint supervisor and observability repairs plus a frozen-image runtime-closure worker. Separate `deleg_fc45ea1f` prepares only new harness/parser/tests, no VM. Runtime subset is capped at 512 MiB, and the proposed test uses one sequential 2.25 GiB FAT instead of two old 2600 MiB fixtures, to keep D above the 10 GiB reserve without deleting old failures. Source review and parent reruns must pass before any fresh dt26 build.

The harness preparer returned 87 reported parser checks but **parent Stage1 is RED**. Real isolated calls reproduced a wrong-filesystem/post-allocation reserve bug, a graphics0→1 patch that never changes the token, echoed-marker acceptance, trailing-newline identifier acceptance and a late collision check. Shared extraction and standalone lock gaps were also found by source review. Receipt: `dt26-parent-harness-probe-20261018T154758731647Z.json`; corrective writer `deleg_f7d944ec` owns only the harness/parser/fixture/test files. No FAT or VM was created. These checks are not native graphics evidence.

Parent independently reran the corrected parser/harness checks: **163 passed, zero failures/skips**, but this is still not enough to launch a VM. Additional exact-code probes show foreign lock contention is falsely called inherited ownership; the BC disk gate subtracts an already allocated FAT again; and an injected log-open failure leaves an already created fake QEMU process uncleaned. Receipt `dt26-parent-harness-fix-verification-20261018T161701680316Z/result.json`; `deleg_1f97c818` owns the focused lock/incremental-capacity/process-lifetime correction. The process probe is an explicit in-memory mock, not a real orphaned VM.

Independent production-function probes reproduced important gaps: empty/partial successful session queries still fail open; missing Remote can be treated as local; partial JSON and symlink sources overwrite last-good status; a size-check/copy race exceeds the byte cap; 260 samples has no actual 260-second deadline; Bash octal/malformed sensor strings can abort or misreport; the new test entrypoint overwrites fixed evidence. Exact receipts and required corrections: `testing/boot-failure/dt26-review-wave1-parent-findings.json`. No new image or USB update is permitted before review fixes close.

The core real-schema change is justified: frozen SFS loginctl/systemctl client bytes match the builder clients used for genuine API probes. `chvt`, `timeout`, SDDM/KWin/Plasma, dbus-run-session and SDDM PAM/session paths are present in the frozen SFS. This is presence/client-byte evidence, not complete runtime closure or native rendering. Real systemctl accepts comma-separated property names; real loginctl requires repeated property flags—do not conflate them.

## Gates before a new native graphical handoff

- [x] Archive/correlate new boot and distinguish a text-only expectation from an actual GUI-start failure.
- [ ] Focused regressions and independently sourced real-shaped logind schema evidence.
- [ ] Spec review PASS, then quality review PASS; fix important findings before integration.
- [ ] Parent reruns actual Linux tests, records counts/skips and verifies source changes; no all-skipped acceptance.
- [ ] Fresh `/home/builder/uki-v2-dt26` build plus host artifact, preserving dt24/dt25/dt25b and archived failures. Hold `/home/builder/boot-failure-tests/dt25-build.lock` for builds/extractions/VMs; never delete the lock. Keep D free >10 GiB and process/compression budget bounded.
- [ ] Exact packed-helper/unit/source provenance, frozen SFS runtime closure where needed, unchanged kernel Image/config/TSENS DTB. No GPU/GEM/GMU/MDSS/clock/voltage/fan or internal-storage enablement.
- [ ] Exact fresh-image disposable EFI regression: text remains usable; absent hardware refuses GUI and persists why; real private-unit SIGKILL cleanup remains non-vacuous; observer outcomes survive. Verify real logind API shape where feasible without confusing a PAM/VM session with native pixels. With only ~15 GB D free, prefer one fresh sequential disposable fixture rather than allocating two full FAT images or deleting old evidence.
- [ ] Fresh physical identity/health/source-hash/backup gates, file-only update, cache flush and independent device readback. Keep both a dt25b text recovery and the genuine separate dt24 baseline when exposing a guarded graphics test. Firmware capture stays off; no rearming or filesystem repair.
- [ ] Owner-executed bounded native graphics attempt: actual guard identity/temperature/DRM pass, visible pixels/input and observed recovery/shutdown. A passed preflight or active session is not pixel proof.

No new image is built or installed at this checkpoint. The USB still holds the four-entry text-first menu (hash `9c99836e41896defc99b3104eb3a65bf9c9d5d886c73a84cb7d58615078b4406`), dt25b main image `b535444f…`, separate dt24 recovery `4fca3315…`, unchanged SFS `5041e7d0…`.

## Percentage requested by the owner

The existing milestone rubric was recalculated, not inflated for an unbooted GUI candidate: **63.0 weighted points → about 65% for the first usable Lenovo live desktop**, and **35.05 → about 35% for a maintained general-ARM64 release** (nearest-five display rounding). These are subjective milestone weights, not measured code/time completion or daily-driver readiness. Graphics, wired networking and final shutdown still gate the desktop goal; public multi-board distribution adds packaging, signing/update, recovery, licenses and broader QA. Current calculations: `docs/research/evidence/froodzos-publication-20261018/progress-estimate-dt26-preparation.json`.
