# Brightness and battery on the Lenovo 83N3: analysis and experiment plan (2026-11-11)

Status: **brightness keys change the on-screen indicator but not the panel; no battery or AC adapter appears.** Both are
open hardware items, not release claims. This page is an analysis of the board device tree and kernel configuration plus a plan of
safe experiments; nothing here has been run yet. Line numbers refer to `boards/lenovo-83n3/x126100-lenovo-ideapad-slim3.dts`
and `boards/lenovo-83n3/kernel.config` at the time of writing.

## 1. Brightness

- The device tree defines `backlight` as a plain `pwm-backlight` on `&pmk8550_pwm` channel 0 (5 ms period, PMK8550 GPIO5, function 3)
  (about lines 57-62 and 1200-1209). The eDP panel node points at it (`backlight = <&backlight>`), with `enable-gpios` on PMC8380
  GPIO4 and `power-supply = <&vreg_edp_3p3>` (about 1065-1082).
- But `&mdss`, `mdss_dp3_phy` and `vreg_edp_3p3` are **disabled** (about 1771, 1725, 1713). The desktop runs on the firmware's
  `simple-framebuffer`, so the panel node never probes and the PWM backlight has no consumer. The embedded controller node is
  commented out (about 893-901).
- The needed drivers exist in the kernel configuration (`BACKLIGHT_PWM=m`, `LEDS_QCOM_LPG=m` as the PMK8550 PWM provider,
  `DRM_PANEL_EDP=y`, `DRM_MSM` with DPU/DP, `PHY_QCOM_EDP=m`), and the `backlight` sysfs device exists. So "missing driver" is ruled out.
- **Most probable cause:** the kernel adjusts a PWM that is not wired to anything the lit panel uses. The panel was initialised by the
  firmware (or the embedded controller), and the real brightness control is not this node. Not proven; a placeholder or wrong path is plausible.
  Direct control over the eDP AUX channel is unlikely while the panel is not bound.
- **Smallest experiment (live USB, text console):** read `max_brightness` and `actual_brightness`, write `0` and the maximum value,
  and read `/sys/kernel/debug/pwm`. If the duty cycle changes but the panel does not, this node is not the panel's control. Risk: a
  temporarily dark screen only.

## 2. Battery and power

- `remoteproc_adsp` and `remoteproc_cdsp` are enabled in the device tree with the expected firmware names (about 1257-1269); no
  patch disables them. `pmic-glink` is enabled (about 118-162); the battery manager is created by the driver, not the device tree.
- The patches that disable `gem_noc` and the `lpass_*_noc` interconnects (about 1695-1697, 1751) and the GPU/display nodes exist for boot stability. They
  also affect the audio DSP side; they are a candidate to revisit.
- Kernel options are present: `QCOM_Q6V5_PAS=m`, GLINK/RPMSG, `QRTR` and `QRTR_SMD=m`, `QCOM_PMIC_GLINK=y`, `QCOM_BATTMGR=m`,
  `UCSI_PMIC_GLINK=m`, PDR/QMI helpers. `QCOM_SPMI_ADC5_GEN3` is **not set**, so the merged PMK8550 ADC/thermal node cannot bind.
- The observed `pmic-glink` device-link message concerns the USB-C altmode and is not the battery cause. The real blockers are the
  protection-domain (PDR) dependency of `pmic-glink`, the missing userspace **`pd-mapper`** (not in the image), and the ADSP not running,
  which needs the vendor firmware staged by the user (`tools/setup-local-firmware.sh`; the public image deliberately omits it).
- Required order: firmware in `/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/`, `pd-mapper` running, ADSP started, PDR, `pmic-glink`, battery manager.

## 3. Safe experiment plan (from the live USB, no internal-disk writes)

| # | Experiment | Expected observation | Risk |
|---|---|---|---|
| 1 | Read `/sys/class/remoteproc/*/state`, `dmesg \| grep -iE 'adsp\|cdsp\|q6v5\|pmic.glink\|pdr'`, `/sys/class/power_supply/*` | Baseline: processors stopped, no supplies | None (read-only) |
| 2 | `setup-local-firmware.sh --dry-run`, then stage the user's own firmware; look for `Direct firmware load` errors | Files found, no load errors | None to disks |
| 3 | Add `pd-mapper`, start it, then `echo start > /sys/class/remoteproc/remoteprocN/state` | ADSP "is now up", battery supplies appear | ADSP crash or hang; keep the text-recovery entry |
| 4 | Unbind and rebind `pmic-glink` after the services are available | Battery manager binds | USB-C altmode disruption; no disk writes |
| 5 | Brightness: the PWM test above | Duty changes, panel does not | Dark screen only |
| 6 | Only if needed: rebuild a UKI re-enabling the display subsystem and the `lpass` interconnects | Real panel binding | Returns to the reset-prone boot; use a spare stick |

Related: the vendor firmware may not be redistributed (see [releases/FIRMWARE.md](releases/FIRMWARE.md)), so battery support, if it
works, will require the user to stage their own copy and the image to ship `pd-mapper` and an enabling device tree.
