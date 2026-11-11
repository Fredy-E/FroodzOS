# release/

Machine-readable release identity, validated by [`tools/validate_release.py`](../tools/validate_release.py).

- `current.json` — the current development identity (`0.1.0-dev`, codename Maverick). Qualification flags are false; a
  qualified release needs a build manifest, owner authorisation and the gates in [docs/releases/POLICY.md](../docs/releases/POLICY.md).
- `codenames.json` — the 25 owner-selected codenames.
- `boards/` — board profiles (Lenovo 83N3).
- `manifests/` — source and verification manifests and the manifest format ([README](manifests/README.md)).
