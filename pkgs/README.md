# pkgs/

Packaging records: `PKGBUILD` files and the numbered kernel and bootloader patch history for the Snapdragon X1 port.

- `linux-cachyos-arm64/` — kernel package recipe and the retained numbered diagnostic patches. Some old patch documents are
  malformed; do not replay them blindly (the byte-tested cumulative deltas are in [`reproducibility/`](../reproducibility/README.md)).
- `stubble-arm64/` — patches for the UEFI stub used to build the UKI.
- `cachyos-arm64-hello/` — a minimal packaging smoke test.

The kernel patches derive from Linux and stay GPL-2.0-only; they are not relicensed by this repository.
No package binaries are published.
