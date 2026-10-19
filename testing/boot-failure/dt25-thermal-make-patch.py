#!/usr/bin/env python3
"""Generate 0020 patch from frozen dt25 baseline (append TSENS0/1 okay only)."""
import difflib
from pathlib import Path

P = Path('/mnt/d/CachyOS-ARM64')
BASE = Path('/home/builder/boot-failure-tests/dt25-baseline/board.dts')
PATCH = P / 'pkgs/linux-cachyos-arm64/patches/0020-diagnostic-restore-cpu-tsens.patch'

base_text = BASE.read_text()
assert base_text.endswith('&gpi_dma1 {\n\tstatus = "okay";\n};\n'), 'unexpected frozen tail'
addition = base_text + """
/* DIAGNOSTIC (0020): restore only CPU thermal sensors TSENS0/1.
 * TSENS0/1 carry the configured CPU0/CPU1 core top/btm and
 * cpuss0/cpuss1 top/btm zones (20 types). TSENS2 (GPU/camera,
 * cooling-maps reference disabled GPU) and TSENS3 (physically
 * present/unconfigured per purwa.dtsi) stay disabled. No ICC,
 * clock, regulator, trip or cooling-map changes. Local-only.
 */
&tsens0 {
\tstatus = "okay";
};

&tsens1 {
\tstatus = "okay";
};
"""
base_lines = base_text.splitlines(keepends=True)
work_lines = addition.splitlines(keepends=True)
diff = difflib.unified_diff(
    base_lines, work_lines,
    fromfile='a/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts',
    tofile='b/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts')
body = ''.join(diff)
header = """From: Kestrel local diagnostic build
Subject: [PATCH 0020] arm64: dts: Slim3: restore CPU TSENS0/1 only

Restore only the configured CPU thermal suppliers TSENS0 and TSENS1
without touching TSENS2 (GPU zones with cooling-maps tied to disabled
GPU), TSENS3 (present/unconfigured), ICC/clocks/regulators, trips,
cooling-maps, PCIe/GPU/MDSS rails, or the dt24 keyboard/USB closures.
Compiled nodes already expose two MMIO windows, PDC+GIC interrupts and
qcom,x1e80100-tsens fallback data; generic tsens-v2 ops require no
initramfs module change (CONFIG_QCOM_TSENS=y). Local-only.

---
"""
with PATCH.open('x') as f:
    f.write(header + body)
print('WROTE ' + str(PATCH))
print(body[:3000])
