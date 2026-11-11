# Security policy

FroodzOS is an experimental, unreleased development project. There are **no supported releases and no
published binaries**; security fixes are made on the main branch of this source archive.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** for this repository (Security tab) if it is enabled.
If it is not available, open a public issue that says only that you have a security report and ask for a
private channel; **do not post exploit details, secrets or private data in a public issue.**

Useful reports include: leaked credentials, keys or private logs in the repository or its history; scripts that
could write to removable media or internal storage without the documented identity checks; and flaws in the
publication integrity tooling (`tools/verify-publication.py`).

## Out of scope

- Hardware behaviour of the experimental 83N3 bring-up that is already documented as open or unaccepted.
- Upstream components (Linux kernel, stubble, Arch Linux ARM packages): report those upstream.

## Handling secrets

No keys, credentials, password databases or raw private machine logs belong in this repository. If you find
one, report it privately as above; the history will be corrected and the credential treated as exposed.
