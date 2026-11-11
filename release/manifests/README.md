# Exact-build manifest boundary

No exact Maverick image/build manifest is created by the development naming
work. `../current.json` is not a build/provenance or approval receipt.

When an actual candidate is assembled, use a fresh `<build-id>.json` that binds
its real source revision plus dirty-tree/delta identity, source/config/component
pins, build inputs/toolchain, declared board/firmware profile and redistribution
status, actual artifact paths/formats/byte counts/digests, separate review/test
receipts, known limitations and publication/delivery status. Use measured values,
not placeholders or copied approval claims. Keep private credentials, captures,
owner identifiers and unlicensed firmware out of public manifests.

An integrity manifest records provenance; it does not grant independent source,
package, native, legal, physical-delivery or publication approval. An old EFI/SFS
must not be reclassified as a new complete Maverick disk image by restamping
metadata. Actual candidate records require their own validation and qualification.
