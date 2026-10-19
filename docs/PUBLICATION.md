# Publication scope and preservation policy

## Requested target

The owner explicitly requested the source/history upload to
https://github.com/Fredy-E/FroodzOS on 19 October 2026. Preflight verified the
existing repository was **public, empty and writable by the intended Fredy-E
account**. No new account, visibility change, tag or binary release is part of
this operation. The main development workspace remains separate from the
publication copy; the original build/evidence files are not edited by staging.

## What is preserved publicly

- Authored research, design/interview decisions, plans, phase reports and current
  state, including superseded assumptions labeled as history.
- Build recipes, platform gates, logger/console/graphics sources, package
  recipes, all numbered diagnostic-patch documents and historical helper/test
  scripts. These are engineering source, not an unattended installer.
- Structured validation receipts, including failures, with private identity
  fields redacted in public derivatives. Three fully reviewed synthetic unittest
  golden logs are also retained because preservation tests depend on them; these
  contain only test-runner output, not private hardware journals.
- The actual board DTS, kernel configuration, modified stubble loader source,
  component license texts and separate cumulative source-recovery deltas.
- A privacy-reviewed chronological discussion derivative, a 3,621-call action
  index, detailed narratives and a complete inventory inclusion/exclusion map.

The recovered logical conversation export contains 6,828 records. Its public
exchange derivative retains 758 discussion records, omitting raw tool outputs,
empty/tool-only assistant entries, repeated context summaries, system/async
worker dumps, credential-related user content and historical code/output
fences. Counts and the local export's hash are in
[conversation coverage](history/conversation-coverage.json). This is not a claim
that the unredacted conversation is on GitHub.

## Retained local — intentionally not uploaded

- Signing keys, credential stores, password databases and private config. The
  `keys/` directory was never traversed or read for publication.
- Windows-extracted Qualcomm/vendor firmware and firmware-bearing UKIs, rootfs
  squashfs files, OS/control ISOs, VHDX, caches and compiled/binary payloads.
- Raw native journals, firmware-variable records, device dumps, private machine
  metadata, screenshots/video containing personal context and worker/tool raw
  transcripts. Reviewed technical conclusions and source/receipt references
  preserve their role without exposing the raw environment.
- Full third-party web/code snapshots with unresolved copying scope. Authored
  analysis, quotations, provenance and upstream source URLs remain available.
- Incomplete/malformed JSON receipts that could not be safely parsed for privacy
  review. Their inventory entries remain visible; they are not called passes.

[Workspace catalog](history/workspace-catalog.json) accounts for every non-key
file in the initial 2,555-file metadata inventory. It also identifies explicitly
recovered authored reports/source inputs. Excluded large/private files were not
hashed merely to produce a public checksum: metadata-only entries say so. An
omitted file is not deleted from the development workspace.

## Derivative and byte-integrity rules

Original source/evidence stays local. Public copies may normalize LF line endings
and redact credentials, personal paths, USB identity fields or other private
metadata. The catalog records original and published hashes for included copies;
original hash-specific test approvals are not silently applied to changed bytes.
Current fixture tests are rerun against the **publication copy**. Public-only
recipe hardening also removes the historical shared live password and makes
retired site-network scripts refuse by default; no already-built image or working
builder configuration was changed. The original
source manifest retains its historical meaning, and current checkout integrity
uses the separate root `SHA256SUMS`.

The numbered historical patches are preserved; 12 failed a fresh syntax check.
New cumulative patches were generated mechanically from real pristine/live
bytes and passed forward/reverse byte comparisons. That is source-delta replay,
not a reproduced complete image. See [reproducibility](../reproducibility/README.md).

## Rights, policy and current limits

Current GitHub Terms of Service, Acceptable Use Policies and DMCA policy were
retrieved and reviewed before operational API/authentication requests:

- https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
- https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
- https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy

This batch is software-engineering source/history for the owner's project, not
third-party binary mirroring, license-key bypass tooling or account-restriction
evasion. The repository is explicitly unofficial. Original component licenses
and notices are retained; **no new blanket project license was selected**. See
[NOTICE](../NOTICE.md). No upstream endorsement, firmware redistribution right,
public image readiness or general ARM64 support is asserted.

Publication does not change the working USB, firmware records, internal disks,
Windows/BCD/BIOS/security settings, Kali or the native boot protocol. No new
physical boot, hardware support or OS build is claimed by this upload.
