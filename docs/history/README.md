# Development history — research to native desktop

This is a retrospective engineering record, not a claim that the original work
had Git commits. The main workspace and extracted kernel tree were not Git
repositories. The first public source snapshot is being prepared on 19 October
2026; the dated records below preserve the actual earlier chronology without
backdating commits or inventing successes.

## Read in order

0. [Project timeline, 7–25 October 2026](../TIMELINE.md) — one dated view from
   first research to the current state.
1. [Bootstrap, image defects and dt1–dt20](bootstrap-through-dt20.md)
2. [dt21 USB breakthrough through dt26 desktop](dt21-through-dt26.md)
3. [Current accepted state and remaining limits](../STATUS.md)

The original [design](../porting-design.md), [decision record](../decisions.md),
[implementation plan](../implementation-plan.md), [phase 1](../phase1-results.md),
[phase 2](../phase2-results.md), [phase 4–5](../phase4-5-results.md) and
[boot-failure investigation](../boot-failure-diagnosis.md) remain available.
Their original pending gates and hypotheses are historical. Follow later
retractions and the current status page instead of replaying old instructions.

## More than a milestone summary

- [Tool-call index](tool-call-index.csv): 3,621 recorded calls in chronological
  order, with safe targets and original message positions. Arguments, raw tool
  output and credentials are intentionally not uploaded.
- [Conversation coverage](conversation-coverage.json): reconciles all 6,828
  exported messages with the public derivative and lists omissions.
- 758 retained user/assistant discussion records, split by UTC date:
  [7 Oct](conversation-2026-10-07.md), [8 Oct](conversation-2026-10-08.md),
  [9 Oct](conversation-2026-10-09.md), [11 Oct](conversation-2026-10-11.md),
  [14 Oct](conversation-2026-10-14.md), [15 Oct](conversation-2026-10-15.md),
  [16 Oct](conversation-2026-10-16.md), [17 Oct](conversation-2026-10-17.md),
  [18 Oct](conversation-2026-10-18.md), [19 Oct](conversation-2026-10-19.md).
- [Workspace-to-publication catalog](workspace-catalog.json): each inventoried
  non-key project file is accounted for, whether included or withheld. Keys
  were not traversed or read. Extra recovered source inputs are identified.
- [Numbered patch history](../../pkgs/linux-cachyos-arm64/patches/) and
  [stubble patch history](../../pkgs/stubble-arm64/patches/) include rejected and
  malformed records rather than only the final apparent success.
- [Recovered replayable deltas](../../reproducibility/README.md) are separate
  from the malformed historical patch documents.
- [Legacy artifact metadata](legacy-artifacts/README.md) is preserved literally,
  without pretending that private firmware-bearing binaries are downloadable.

These counts describe records, not 6,828 unique experiments or 3,621 tests.
Some original tool responses in the conversation export were already truncated;
the public derivative cannot recreate missing output bytes. The complete
redacted logical export and original local evidence remain private.

## Proof ladder

Source inspected → compiled → packed bytes audited → disposable EFI/VM boot →
owner-executed native boot → real session → owner-observed pixels/input →
networking/persistence → maintained distribution are different gates. The
archive does not collapse them. Missing logs, LED changes, a loaded module or a
shutdown sync line do not establish the next gate.
