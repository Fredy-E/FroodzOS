# Battery, USB-C power data and the ADSP on Snapdragon X laptops (2026-11-14)

Status: **battery percentage, charge/discharge state and USB-C power data work on the Lenovo 83N3** with boot menu entry 3 of the private
test stick (owner test, 2026-11-14). Audio still needs a second step (below). This page records the cause and the method, which is not
specific to the 83N3.

## Cause

On Snapdragon X (Hamoa/Purwa) the battery gauge, the USB-C controller (UCSI) and the audio service live on the **ADSP**. Linux reaches them
through `qcom_q6v5_pas`, and that driver refused to probe: `failed to acquire interconnect path`. The remoteproc node carries an
`interconnects` bandwidth vote through a NoC provider (`lpass_lpicx_noc`) that is **disabled** in this board's device tree (the provider
was disabled during bring-up because its probe reset the machine). A vote through a disabled provider can never resolve, so the ADSP never
registered, `pmic_glink` had nobody to talk to and the battery read 0 % forever.

## Method (works on any board's compiled DTB)

`builder/public-image/fz-dtb-fixup.py <in.dtb> <out.dtb>`: for every Qualcomm PAS remoteproc node (ADSP by default, `--all-pas` for all)
whose `interconnects` point at a disabled or missing provider, delete `interconnects` and `interconnect-names`. A missing property is a
"no vote" path, which the driver handles. It edits the binary with `fdtput`, so it needs no board source tree and leaves everything else
byte-identical. It reports what it changed, and `--dry-run` only reports. Tests: `tests/test_dtb_fixup.py`.

Result on the 83N3: `remoteproc0: adsp is available ... attaching to adsp ... now attached`. **The laptop firmware had already started the
ADSP**, so Linux attaches to it and no Qualcomm firmware file is needed for the battery (the "Direct firmware load ... failed with error -2"
line is expected and harmless). That matters for distribution: the battery works without redistributing any vendor binary.

## What is still open

* Sound: no GPR/audio service appears on the firmware-started ADSP. The next step is `dsp-bringup.sh reload` on the stick: stop the ADSP and
  start it again with the board's own firmware (imported from the user's Windows driver store; never shipped). Not yet run with this device tree.
* Wi-Fi: the first experiment image used an old diagnostic device tree with PCIe switched off, so Wi-Fi disappeared; that was our mistake in
  the experiment, not a consequence of the ADSP change. The method above patches the shipped DTB instead of recompiling a source tree.
* The smart log counted an `attached` remoteproc as not running and derived no percentage when the driver reports only `energy_now` and
  `energy_full`; both are fixed in `fz-smartlog` (root r7).
* **I2C buses** (`b80000`, `b84000`, `b8c000`, `b9c000` = i2c0/1/3/7): `geni_i2c: Failed to get 'qup-config' ICC path`. Their `qup-config` path
  starts at the disabled `gem_noc`. `fz-dtb-fixup.py` now applies the same rule to GENI serial engines (the owner-tested I2C5/I2C9 fallback);
  in image H (not yet booted) these four buses lose their votes. The touchpad bus (`88c000`) is found by name by `fz-touchpad`, so bus renumbering is harmless.
* **Temperature alarms** (7 PMIC `temp-alarm`): they wait for the `pmk8550_vadc` IIO channel; the kernel config had `CONFIG_QCOM_SPMI_ADC5_GEN3` unset, so no
  driver existed. Set to `=m` in `boards/lenovo-83n3/kernel.config` for the next kernel build; the stick carries a module built from the same tree for an `insmod` test.
* `qcom-bwmon` (OPP table) and DWC3 `a800000` (`failed to register DWC3 Core`, no further reason in the log) stay open. The smart log now lists device links that
  are not active, which names the missing supplier on the next boot.
