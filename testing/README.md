# testing/ — historical evidence and test scripts

This directory holds the project's test scripts, captured logs and reviewed receipts from October and November 2026.
It is **evidence**, not a test suite you run: most scripts target one specific numbered boot revision (`dt<N>`), expect the
owner's build workspace, and are pinned by hash in the records that cite them. Failed and rejected runs are kept on purpose.
**Do not edit, rename or "clean up" files here**; a changed byte breaks the hash that a later record refers to.

| Path | What it is |
|---|---|
| [boot-failure/](boot-failure/README.md) | About 960 files: per-revision (`dt*`) test scripts, QEMU harnesses, USB result records and native-boot captures. |
| [control/](control/README.md) | Scripts used to prepare and check the first control media. |

To run the project's actual unit tests use [`tests/`](../tests) (`python -m unittest discover -s tests`).
Start with [docs/releases/CURRENT.md](../docs/releases/CURRENT.md) for the current state and [docs/TIMELINE.md](../docs/TIMELINE.md)
for the order of events.
