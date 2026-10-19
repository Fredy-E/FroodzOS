# Source inputs and reproducibility boundaries

This is a source/evidence archive, **not a turnkey rebuild or binary release**.
The package recipes include historical staging from already-built trees. The
rootfs contains locally provisioned firmware and private signing material is
intentionally absent; neither is distributed here.

## Exact upstream pins

| Component | Revision | Recorded source-archive SHA-256 |
|---|---|---|
| `jglathe/linux_ms_dev_kit`, `jg/ubuntu-qcom-x1e-7.3rc` | `3f0d8691afa098ba378d7d5a3968f03219887719` | `31d344b3fce132ae24a9ae87b4f5bb10efd0e68772286bf6db872c1b415299d0` |
| `ubuntu/stubble` | `9f11278e080a5c4a77db6acf4c8f75c14412087a` | `b966a60e3badc0a759d56b37680ef1693f5b24239ac1443ea0a552e8a2a80ac0` |

Sources: [kernel phase report](../docs/phase2-results.md). Full source snapshots:

- https://codeload.github.com/jglathe/linux_ms_dev_kit/tar.gz/3f0d8691afa098ba378d7d5a3968f03219887719
- https://codeload.github.com/ubuntu/stubble/tar.gz/9f11278e080a5c4a77db6acf4c8f75c14412087a

These are pinned upstream download references, not files rehosted in this repo.
The historical `builder/fetch-sources.sh` resolves a branch head; **do not use
that moving lookup as a replacement for these accepted pins**.

## Captured source state

- `boards/lenovo-83n3/kernel.config`: publication-day configuration snapshot.
- `boards/lenovo-83n3/x126100-lenovo-ideapad-slim3.dts`: publication-day modified
  board source; original SPDX/copyright headers retained.
- `reproducibility/stubble/linux.c`: modified loader source with its original
  LGPL notice.
- Applicable license texts under `third_party/`.

The capture held the existing dt25 build lock and verified source hashes before
and after copying. It did not build, change kernel/DT sources, read signing keys
or write any physical medium. A source snapshot is not by itself a proof that a
fresh complete OS build will reproduce an earlier UKI or rootfs hash.

## Historical patch documents versus replayable deltas

All 21 original numbered patch documents under `pkgs/` are retained as history.
A fresh parser check found **12 malformed documents**. Some have incorrect hunk
counts or collapsed line boundaries. The on-disk built source differs from the
pristine pin correctly, but those old documents must **not** be advertised as an
executable patch series. Their bytes were not silently repaired or deleted.

Two separate publication recovery artifacts were generated from actual pristine
and modified bytes:

- `kernel-current-source-recovered.patch`: cumulative differences for the six
  named modified kernel/board files against the pinned kernel source.
- `stubble-current-source-recovered.patch`: cumulative loader alignment fix
  against the pinned stubble source.

Both passed dry-run, actual forward application, exact modified-byte comparison,
reverse dry-run, actual reversal, and exact pristine-byte comparison in fresh
isolated fixtures. Original sources remained hash-identical. The machine-readable
[receipt](patch-recovery-receipt.json) records every covered file/hash and the
parse result of every historical patch. This establishes those deltas' replay,
not the absence of every possible unenumerated change anywhere in the large
builder tree or an independently reproduced full OS.

The kernel cumulative delta is diagnostic: it intentionally retains disabled or
no-vote hardware paths used to reach the bounded desktop. It is not a general
performance, power-management or production-device-tree recommendation.

## Still needed before a distributable image

1. A clean, from-source packaging pipeline rather than packaging mutable staging.
2. Complete version-matched package sources, build dependencies and manifests.
3. Fresh exact-image build/EFI validation and separately owner-executed hardware
   acceptance; never reuse old test claims for changed source bytes.
4. Firmware redistribution clearance or a lawful local-provisioning design.
5. Independent public keyring, signed packages **and** signed repository
   databases, update/rollback/recovery policy, license/source notices and keys
   held privately. Local signing rehearsals are not a maintained public service.
