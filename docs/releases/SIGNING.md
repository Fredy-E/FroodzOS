# Release signing

Release assets are accompanied by `SHA256SUMS` and a detached OpenPGP signature `SHA256SUMS.asc`.

| Item | Value |
|---|---|
| Key | `FroodzOS Release Signing (Maverick 0.1)` (ed25519, signing only) |
| Fingerprint | `1432 DC7D B541 96FF 471E  FD57 A558 604E 9E92 C7EA` |
| Created | 2026-11-11, expires 2028-11-10 |
| Public key | [`release/signing/froodzos-release-public.asc`](../../release/signing/froodzos-release-public.asc) |

## Verify a download

```
gpg --import froodzos-release-public.asc
gpg --fingerprint 1432DC7DB54196FF471EFD57A558604E9E92C7EA      # compare with this page
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
```

A good signature proves the checksum file was made by the holder of this key; it does not prove the image is safe or that the
key holder is who they say they are. Compare the fingerprint with the one in this repository **as it appears on GitHub at the
tag** and, if you can, with a second source.

## Key custody (honest status)

The private key was generated on the maintainer's PC without a passphrase so that releases can be signed non-interactively; a
protected backup exists outside this repository and must never be committed. **Recommended before 1.0:** add a passphrase, move the
key to a hardware token, and rotate. If the key is ever exposed it will be revoked and the revocation published here. Images are
unsigned at the boot level (no Secure Boot); this signature covers downloads only.
