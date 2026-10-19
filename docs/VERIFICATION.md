# Verification

## Verify the downloaded source tree

From a fresh checkout or extracted GitHub source ZIP, run:

```sh
python -B tools/verify-publication.py
python -B -m unittest discover -s tests -p test_publication.py -v
```

The verifier does not require `.git`. It rejects missing, unlisted or changed
files, unsafe checksum paths, symlinks, private-key/binary-image/archive paths, malformed
hash records and CRLF checksum manifests. `SHA256SUMS` uses standard ASCII
`SHA256  filename` records; on a system with GNU coreutils the equivalent content
check is:

```sh
sha256sum -c SHA256SUMS
```

This checks source-package integrity and the declared file set. It is not an
independent secret detector, a signature/authenticity proof or native hardware
validation. Publisher-side gitleaks and explicit scope/privacy reviews are
separate gates.

## Fixture-only graphics/session regressions

These tests import the supervisor and use controlled fixtures; they do **not**
execute the supervisor's live system-control entry point:

```sh
python -B testing/boot-failure/test-dt25-graphics-supervisor.py
python -B testing/boot-failure/test-dt26-session-supervisor.py
python -B testing/boot-failure/test-dt26-session-fix.py
python -B testing/boot-failure/test-dt26-preflight-io.py
```

The four final session/IO suites contain 55 cases. Linux shell/logger fixtures
also require Bash, standard Linux tools and private user/mount namespace support
for the strongest behavior tests; they must never be replaced by a Windows run
that skips the Linux cases:

- `test-dt26-observability.py`
- `test-dt26-observability-fix.py`
- `test-dt26-observability-bounds.py`
- `test-dt26-logger-watchdog.py`

Each logger CLI supports `--out-prefix` and refuses existing outputs. Supply a
fresh private result path. They exercise controlled stubs and fixtures, not the
owner's live device. See the public publication-verification receipt for the
actual fresh-run counts, skips and source hashes.

## Historical evidence

The retained `testing/boot-failure/` receipts include earlier successful and
failed fixture/EFI runs. Some point at private images or raw logs not uploaded
here. The final dt26a3 A and B+C receipts identify the exact local UKI hash;
virtual B proves refusal, and C uses labeled fake processes. Native acceptance
is documented separately in [dt26 native desktop](dt26-native-desktop-success.md).
Do not rerun archived build/media/firmware scripts merely to verify a source ZIP.

A first check cannot prove complete image reproducibility, private-key security,
all possible secret patterns or hardware safety. All these limits remain
explicit in [STATUS](STATUS.md) and [publication scope](PUBLICATION.md).
