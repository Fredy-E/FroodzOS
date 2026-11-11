# tools/

| Tool | Purpose |
|---|---|
| `verify-publication.py` | Checks a checkout against `SHA256SUMS` and refuses binaries, keys, caches and oversized files. |
| `regenerate-publication.py` | Rebuilds `SHA256SUMS` (never rewrites the historical `publication-manifest.json`). |
| `validate_release.py` | Validates `release/` metadata; development metadata only, not a qualification. |
| `check-privacy.py` | Pattern scan for secrets and personal data (added lines vs a base ref, or the whole tree). |
| `add-spdx-headers.py` | Adds `SPDX-License-Identifier` headers to the project's original source files (dry run by default). |
| `compat-catalogue.py` | Source of truth for `docs/compat/formats.tsv` and `SUMMARY.md` (the universal-compatibility catalogue); `--check` fails if they drift. |
| `setup-local-firmware.sh` | Copies firmware from the owner's own Windows installation into a live session. Never uploads anything. |

Run with Python 3.11 or newer and `-B` (no bytecode files, which `verify-publication.py` would reject).
