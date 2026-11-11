# testing/boot-failure/ — per-revision evidence

Filename families (the number after `dt` is the boot-revision generation; later records win over earlier ones):

| Prefix | Meaning |
|---|---|
| `dt<N>-...` | Records, manifests and results for boot revision N (build, update, native result). |
| `qemu-...` | Emulator harnesses and their outputs. Emulation is **not** native proof. |
| `usb-...` | Results of writing or verifying a revision on the USB test media. |
| `test-...`, `check-...`, `verify-...`, `validate-...`, `audit-...` | Unit-style tests and gates for one revision. |
| `prepare-...`, `update-...`, `build-...` | Scripts that prepared a revision (owner's workspace only). |
| `diag-...`, `find-...`, `show-...`, `inspect-...`, `firmware-...` | Diagnostics and read-only inspections. |

Red results (failures) are retained. A green unit test is not hardware acceptance; native acceptance is recorded in
[docs/releases/CURRENT.md](../../docs/releases/CURRENT.md). Some files contain historical machine details (for example
a USB volume serial or Windows profile paths) kept for hash integrity; see [SECURITY.md](../../SECURITY.md) to report a concern.
