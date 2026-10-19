#!/usr/bin/env python3
"""Parent fix: harness send strings must terminate with a REAL newline (Enter).

Three guest send strings ended with literal backslash-n, so the guest shell
never executed the typed line (v2 Case A sat at the prompt until deadline).
Asserts exact occurrence counts; refuses to write on mismatch.
"""
from pathlib import Path

HARNESS = Path("/mnt/d/CachyOS-ARM64/testing/boot-failure/dt25b-efi-harness.py")
src = HARNESS.read_text()

fixes = [
    # Case A: trailing Enter missing (literal \\n in file bytes).
    ('"sleep 5; sync; poweroff\\\\n"', '"sleep 5; sync; poweroff\\n"', 1),
    # B collect: last command piece had no trailing newline at all.
    ('head -n 100 || true; "', 'head -n 100 || true; \\n"', 1),
    # C chaos + retired C_09 reference: same literal-\\n trailer.
    ('sync; poweroff\\\\n"', 'sync; poweroff\\n"', 2),
]
for old, new, expected in fixes:
    found = src.count(old)
    assert found == expected, f"{old!r}: found {found}, expected {expected}"
    src = src.replace(old, new)

HARNESS.write_text(src)
print("HARNESS_ENTER_FIXED", {"replacements": len(fixes)})
