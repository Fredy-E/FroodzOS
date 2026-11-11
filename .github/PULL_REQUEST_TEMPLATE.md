## What and why

## Evidence class
- [ ] Unit / fixture test only
- [ ] QEMU or other virtual run
- [ ] Native hardware observation (board, boot, what was observed)

## Checklist
- [ ] No binaries, firmware, keys, credentials or private logs added
- [ ] `python tools/verify-publication.py` passes (checksums updated if files changed)
- [ ] `python tools/validate_release.py` and `python -m unittest discover -s tests` pass
- [ ] Claims match the evidence; failed attempts are recorded, not removed
