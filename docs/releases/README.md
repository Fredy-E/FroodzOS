# FroodzOS release identity and qualification

**Current product target: `0.1.0-dev`, Maverick. No qualified OS binary release is established.**

- [Exact owner-selected naming authority](CODENAMES.md): all 25 selected pairings; unchanged original document.
- [Current evidence and blockers](CURRENT.md): observed versus accepted versus open.
- [Promotion and publication policy](POLICY.md): engineering gates, version namespaces and authorization.
- [Recommended milestone scopes](ROADMAP.md): future engineering recommendations, not dates/promises.
- [Maverick alpha target](0.1-maverick.md): scope and unmet exit criteria, not shipped release notes.

Machine records are `release/codenames.json`, `release/current.json` and
`release/boards/lenovo-83n3.json`. They describe development and experimental
board status, not approval receipts. Future exact-build records belong in
`release/manifests/`; no fictitious build record is created for this work.

From the project root, `python -B tools/validate_release.py` performs a bounded,
read-only metadata consistency check. It prints `DEVELOPMENT_METADATA_ONLY`
and `qualification: NOT_EVALUATED`; exit0 is **not** package, hardware or release
acceptance. `python -B testing/test_release_metadata.py` runs inert regression
checks; for this project, Linux execution is gated to the named CachyOSBuilder
UID/EUID1001 with clean PATH. Windows fixtures use the Hermes scratch directory.
No installer, network, privilege, boot or media operation is performed.

The validator pins the exact original naming-document bytes, compares every
selected mapping/display/slug, refuses duplicate JSON keys and malformed version
literals, and admits only this development-status snapshot. It is not an
independent approval service or hostile-filesystem atomic snapshot. Future
status/promotion changes require evidence and a separately reviewed update; do
not edit a boolean to manufacture approval.

Adopting these records does not relabel the working UKI/SFS/GRUB/persistence
markers, change `/etc/os-release`, create a tag, or publish anything. Component
versions remain independent of the product version.
