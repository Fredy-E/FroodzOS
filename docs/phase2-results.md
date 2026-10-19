# Phase 2 results — kernel + Slim 3 DT + stubble UKI (2026-10-08)

**Gate status: G2 PASS** (kernel+DT+stubble-UKI package builds and installs signed; QEMU smoke boot OK). **G0b PASS (runtime)** — the same kernel booted to userspace under `qemu-system-aarch64 -cpu cortex-a53`, proving the ARMv8-A baseline at runtime.

## Pinned sources (SHA256-verified)

| Source | Ref | SHA256 |
|---|---|---|
| `jglathe/linux_ms_dev_kit` (kernel tree) | `3f0d8691afa098ba378d7d5a3968f03219887719` (branch head 2026-09-19) | `31d344b3fce132ae24a9ae87b4f5bb10efd0e68772286bf6db872c1b415299d0` |
| `ubuntu/stubble` (HWID boot stub) | `9f11278e080a5c4a77db6acf4c8f75c14412087a` (PR #69 merge) | `b966a60e3badc0a759d56b37680ef1693f5b24239ac1443ea0a552e8a2a80ac0` |

Note: the research pin `bc513d262c8d` was superseded by the branch head above; the head is a WIP tree that needed five port patches (below).

## Port patches (`pkgs/linux-cachyos-arm64/patches/`)

1. **0001** `hamoa-pmics.dtsi`: add missing `qcom,spmi-vadc.h` include (insufficient alone — include guards keep the local function-like macros winning — kept as a harmless part of the series).
2. **0002** `remoteproc_core.c`: drop unreachable `RPROC_DELETED` check (token exists nowhere else; enum is complete/consecutive).
3. **0003** `qcom_q6v5.c`: resolve a committed merge conflict in `request_stop()` (kept HEAD's "logical crashes still need a stop" guard — also satisfies the incoming upstream commit's intent).
4. **0004** `qcom_q6v5_pas.c`: unify two stray `qcom_scm_pas_metadata_release()` calls to the file's own `qcom_pas_metadata_release()` (idempotent, matching `struct qcom_pas_context`).
5. **0005** `hamoa-pmics.dtsi` (generated diff from pristine+0001): merge the duplicate `adc@9000` nodes (`pmk8550_adc_tm` stale partial copy into `pmk8550_vadc`, dual-labeled, keeping the complete channel set), and use the local `ADC5_GEN3_VPH_PWR(1)` macro (VIRT_CHAN(1,0x8e) = 0x18e = `channel@18e`).

Every patch is a partial-merge artifact in the upstream WIP branch; all documented with rationale. `build-kernel2.sh` also needed `bc` (installed).

## Build configuration

`make ARCH=arm64 ubuntu_x1e_defconfig` (full 7525-line config in-tree). Verified: `CONFIG_ARM64=y CONFIG_ARCH_QCOM=y CONFIG_ACPI=y CONFIG_EFI_STUB=y CONFIG_ATH12K=m CONFIG_DRM_MSM=m CONFIG_PCIE_QCOM=y CONFIG_SOUNDWIRE=m CONFIG_I2C_HID_ACPI=m`. No LTO. `MAKEFLAGS=-j4`.

## Artifacts (installed via signed package `linux-cachyos-arm64-7.3.0rc3-1`)

| Artifact | Size | SHA256 |
|---|---|---|
| `/boot/vmlinuz-linux-cachyos-arm64` (Image) | 52,492,800 | `82ec645cc7712ed71dcf0c2840a68263d2802fcb6be31cce22487094bb2f27db` |
| `/boot/vmlinuz-cachyos-arm64.efi` (stubble UKI) | 52,853,760 | `e155d12a2ed6cfa947d79a67dde73c8c3e08212c6eea12a81d5130a86c309301` |
| `/boot/dtbs/…/x126100-lenovo-ideapad-slim3.dtb` | 207,632 | `656fd217b48ffb6f8aa5cc7cc1f91ffcf5855dd91c30e33b67291c12e2572ff3` |

UKI contents verified via `stubblify inspect`: `.dtbauto` = the Slim 3 DTB, `.hwids` = 18,085 bytes (incl. the 83N3 HWID JSON), `.cmdline` = `clk_ignore_unused pd_ignore_unused console=tty0 quiet`. Package signed with the G1 build key; `pacman -U` verified keyring + integrity (note: `modules_install` needed `INSTALL_MOD_PATH=$pkgdir/usr` for the `/lib`→`usr/lib` convention, and read access to the tree's build-time module-signing key).

## G2 smoke boot (QEMU, virt only — no device claims)

`qemu-system-aarch64 -M virt -cpu cortex-a53 -m 2048 … -append "console=ttyAMA0 rdinit=/init"` with a static init:

```
Run /init as init process
SMOKE_OK uname=Linux 7.3.0-rc3 aarch64
reboot: Power down
```

Exit 0, clean poweroff. cortex-a53 = ARMv8-A without LSE: the G0b runtime proof for the user's broad-baseline decision.

## Not yet done (gates ahead)

- G3/G4: boot the UKI on the real 83N3 (user-executed; needs the image assembly from Phase 4 or direct USB boot of the UKI).
- G5: from-source reproducible rebuild + repo flow (Phase 3).
- `.osrel` in the UKI currently carries the builder's ALARM identity — regenerate with neutral identity at packaging time (ADR-8).
- Firmware staging script (Task 3.4) still pending; control test results will feed its file list.
