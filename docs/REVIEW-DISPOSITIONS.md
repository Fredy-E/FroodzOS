# Publication review dispositions

The initial read-only source/rights/privacy audit sampled headers and source,
not keys, credential stores, vendor blobs or raw private machine journals.
This page records what was fixed or deliberately kept outside the source-only
publication scope. It is not legal advice or a binary-release approval.

| Finding | Disposition |
|---|---|
| Original-code license not selected | No new blanket license added. Existing SPDX and third-party grants remain; unlicensed original work is not silently granted new terms. See NOTICE. |
| Windows-extracted firmware / keys / image payloads | Excluded; no private key directory traversal, no image or binary release. Catalog accounts for omitted non-key files. |
| Per-user paths / serial/MAC / private JSON fields | Redacted in public derivatives. Originals and original hashes remain local; no redaction is claimed as a byte-identical raw evidence copy. |
| Hardcoded shared live credential in the historical recipe | Public `build-live-rootfs.sh` now requires a caller-supplied, non-default, single-line local password **before any build effects**. Original recipe and the already-built private diagnostic are unchanged. The archive is not secure daily-driver media; passwordless live sudo and other experimental assumptions remain visible. |
| Site-specific builder networking | Five retired network/setup scripts use documentation-only address replacements and refuse execution by default. Their edited public derivatives are not the owner's working network configuration. No Windows/router/guest network was reconfigured for this publication. |
| Privileged / destructive historical helpers | Explicitly historical; no automatic execution or CI image/USB/firmware pipeline is supplied. Formatting/raw-media/owned-efivar helpers require separate reviewed scope before use. Publishing source does not authorize those actions. |
| Missing effective kernel config and board source | Captured under the existing builder lock, with before/after byte hashes; published with upstream notices. |
| Dynamic branch lookup / staging-only PKGBUILD | Original historical scripts retained and labeled; exact accepted source pins and hashes recorded separately. No turnkey or fully reproduced OS claim. |
| Malformed historical patches | All 21 records retained; 12 parser failures recorded. Separate actual-source cumulative deltas forward/reverse byte-tested, without changing the old documents. |
| Fresh-copy closure omissions caught by real tests | An initially omitted graphics-policy JSON and three synthetic golden test logs were restored. Every one of the accepted 31 build-source inputs now matches its original hash, and a fresh publication-copy rerun passes all 88 session/IO/logger fixture cases with zero failures/skips. The failed export attempts remain local; no fake fixtures or weakened tests were substituted. |
| Tool-verifier archive suffix gap | Added compressed/archive suffix refusal with real `.tar.gz` and `.zip` regression tests. Twelve portable publication tests now pass. |
| Third-party page/man/bug/README snapshots | Full fetched mirrors omitted unless specifically licensed source inputs; authored analysis, source URLs and limited quotations retained. |
| Overstated draft history | Parent corrected source-unit/databases distinctions, firmware-rearm scope, GB/GiB units, storage/rebuild order, missing execution-only CRLF failure and newly authored wrapped checksum literals before publication. Earlier original records are not rewritten. |

## Deliberately open downstream gates

A complete reproducible-image pipeline still needs version-pinned rootfs package
inputs, a fully enumerated build environment/HWID selection, clean packaging and
independent end-to-end rebuilding. Firmware rights, complete corresponding
source for binary distributions, public signing/update/recovery infrastructure,
additional boards and original-code license selection remain separate work.
None of those gaps is hidden behind the source-publication milestone.
