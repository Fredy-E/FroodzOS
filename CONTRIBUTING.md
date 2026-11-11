# Contributing

Thanks for your interest. FroodzOS is an early, hardware-specific project (first target: Lenovo IdeaPad Slim 3
15Q8X10 / 83N3), so contributions that are **evidence-backed** are the most useful.

## Ground rules

- **No binaries and no firmware.** Do not add images, kernel images, ISO/squashfs, vendor firmware, signing
  keys, credentials, or raw private logs. `python tools/verify-publication.py` enforces this.
- **Keep evidence classes honest.** Unit tests, virtual fixtures (QEMU) and native hardware observations are
  different things; say which one you have. Do not describe a mocked test as hardware proof.
- **Do not rewrite history.** Failed and rejected revisions are kept on purpose; add a new dated entry instead.
- **Names and versions.** Codenames follow `docs/releases/CODENAMES.md` exactly. Component or fixture versions are
  not product versions.
- **Scripts that touch devices** must keep their identity checks and be reviewed before use; never add a script
  that writes to internal storage, firmware or security settings.

## Licence of contributions

By contributing original source code or tools you agree that they are licensed under **GPL-2.0-or-later**
(see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md)). Files imported from upstream keep their own licence and
header; say where they came from and under what terms.

## Checks before a pull request

```bash
python tools/verify-publication.py
python tools/validate_release.py
python -m unittest discover -s tests
```

Hardware reports (what booted, what worked) are welcome as issues using the hardware-report template.
