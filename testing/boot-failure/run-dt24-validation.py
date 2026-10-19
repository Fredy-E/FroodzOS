#!/usr/bin/env python3
"""Serialize the exact-default text test and disposable EFI persistence regression."""
import subprocess
from pathlib import Path

T = Path('/mnt/d/CachyOS-ARM64/testing/boot-failure')
for name in ['validate-dt24-text-boot.py', 'validate-dt24-logger.py']:
    print('DT24_VALIDATION_START', name, flush=True)
    subprocess.run(['python3', str(T / name)], check=True)
    print('DT24_VALIDATION_PASS', name, flush=True)
print('DT24_ALL_BOOT_AND_LOGGER_GATES_PASSED', flush=True)
