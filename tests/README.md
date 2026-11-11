# tests/

Unit tests for the publication checks and release metadata. Run from the repository root:

```
python -B -m unittest discover -s tests
```

On Windows set `TMPDIR` to a writable directory first. The tests are inert: no hardware, network, privilege or media access.
CI runs them on Linux and Windows with Python 3.11 and 3.12 (`.github/workflows/tests.yml`).
