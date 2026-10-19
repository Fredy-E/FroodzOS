# Native console research: next repair for Lenovo 83N3

Research date: 2026-10-17. Target: Lenovo IdeaPad Slim 3 15Q8X10, machine type 83N3, Snapdragon X1-26-100. This is a research recommendation, not a built or native-tested fix.

## Decision

**Repair the configured internal keyboard's supplier/module chain, then select normal systemd with a text console. Do not spend another native round solely on the unchanged dt23 pre-exec markers, and do not enable the entire graphics stack at once.**

USB storage, the live overlay and execution of the live-root wrapper are already demonstrated by the archived native dt21/dt22 evidence. Successful Bash startup, actual keyboard input, native systemd and Plasma are not demonstrated. These are separate acceptance gates.

The selected diagnostic entries intentionally replace normal init with `/usr/local/sbin/kestrel-pid1`. That wrapper ends by attempting interactive Bash; it does not start systemd, its udev/getty services or SDDM. Waiting longer in that selected path will not advance it into Plasma. This is directly visible in `builder/diagnostics/kestrel-pid1.sh` and the archived native command lines.

## What the outside research established

### Exact-board expert sources

Jens Glathe's kernel tree contains a device tree explicitly identifying `Lenovo IdeaPad Slim 3 15Q8X10`, including the HID-over-I2C keyboard and board-specific firmware paths.[14] Stubble PR 69 supplies the hardware-identification integration, but its discussion explicitly distinguishes merging that mapping from upstream kernel support.[2] An HWID mapping is not a guarantee of a working desktop.

The recorded build pin is `3f0d8691afa098ba378d7d5a3968f03219887719`. It was successfully retrieved using that exact full identifier. The board-file Git blob is `c07734928289f8ab40520ef20193307bd6357a23`; its bytes equal the independently fetched 7.3rc branch-tip board file. The fetched branch-tip commit is `b1482e1e1590306027ebf5ebd6d7df1ceab84ec5`. Thus, replacing only our board file with that branch tip does not introduce a new board-file repair. This does not establish equivalence of the complete kernel trees. See `evidence/native-console-20261017/exact-pin-board-api.json`.

### Fedora exact-model report

A Fedora discussion author reports: “I now have Fedora KDE 44 running properly on a Lenovo IdeaPad Slim 3x 15Q8X10 / machine type 83N3.”[1] This is the most directly relevant desktop-success report found, but it is a single-author community account with an AI disclaimer—not an independently reproduced result on our unit. **[unverified — single source: https://discussion.fedoraproject.org/t/fedora-44-on-snapdragon-x-end-to-end-installation-hardware-enablement-for-lenovo-ideapad-slim-3x-83n3/204767]**

The report is useful as a comparison recipe, not a DTB or command-line bundle to adopt blindly. Its touchpad changes must be matched to the physical variant. Our tree maps `i2c19` to `88c000`, while `i2c0` maps to `b80000`; copying a snippet by label without resolving its target can modify the wrong bus. The expert board also contains several commented touchpad variants, so a report about one panel/touchpad combination cannot establish our combination.[14]

### Other distribution paths

| Project | Useful evidence | Limit for this laptop |
|---|---|---|
| Ubuntu Concept | Its FAQ describes a WIP Qualcomm kernel and patched packages beyond generic Ubuntu.[11] Stubble and the expert DTS are directly relevant.[2][14] | No verified plug-and-play live image for our exact physical unit was established. The support request is separate from proven support.[3] |
| Fedora | Official guidance documents Snapdragon command-line and model-specific firmware considerations.[10] The community report names 83N3 specifically.[1] | The exact-board desktop claim remains single-source; generic guidance is not an 83N3 certification. |
| Debian | `qcom-firmware-extract` documents Windows-derived firmware as a temporary licensing workaround.[12] | Firmware extraction alone is not a board/kernel/display enablement solution. |
| Arch Linux ARM / related Arch images | Surveyed related Snapdragon projects as possible packaging references. | No independently verified ready-made 83N3 image was established by this investigation. |
| postmarketOS / NixOS / openSUSE | Surveyed device and related Snapdragon enablement material. | No independently verified ready-made 83N3 image was established by this investigation. This is a bounded research finding, not a claim that no such work exists. |

Changing the distribution does not by itself repair the compiled device tree's disabled suppliers. The strongest immediate inputs are the exact-board expert sources and our own compiled/native evidence, not another laptop's feature matrix.

## What the local audit proved

These are local artifact observations, not inferences from web reports. Evidence files are retained under `evidence/native-console-20261017/`.

| Component | Actual dt23/build state | Consequence / evidence limit |
|---|---|---|
| Configured built-in keyboard | `/soc@0/geniqup@ac0000/i2c@a84000/keyboard@3a`, HID-over-I2C | Its bus is `i2c9`, not the repeater bus repaired by dt21. |
| Keyboard power | Its `vdd-supply` resolves to `/regulator-misc-3p3`, explicitly disabled | A real supplier defect; the I2C-HID OF driver requests `vdd` and `vddl` with checked regulator acquisition. |
| Keyboard bus interconnect | `i2c9` retains `qup-config` through disabled `gem_noc` | Mandatory GENI ICC acquisition still names a provider that cannot bind in this configuration. |
| Keyboard DMA | `i2c9` references `gpi_dma1` at `a00000`, explicitly disabled | Conditional blocker: GENI requires this DMA path if firmware disables FIFO mode. The native FIFO-mode bit has not yet been established. |
| Early HID drivers | `CONFIG_I2C_HID=m` and `CONFIG_I2C_HID_OF=m`; neither module appears in the actual dt23 initramfs listing | Early module closure is incomplete. This does **not** mean the modules are absent from the complete live root. |
| Captured input devices | gpio-keys and a receiver named `2.4G Mouse`, with multiple HID interfaces | Neither a Keyboard-class interface nor multiple interfaces proves real keyboard keypress input. |
| Current init selection | `init=/usr/local/sbin/kestrel-pid1` | Normal systemd/getty/SDDM is bypassed by design in those entries. |
| Text framebuffer | Native logs show simpledrm/fbcon initialization | Disabled native GPU/MDSS does not, by itself, prove text-console output is impossible. |
| Accelerated display | GPU, GMU, MDSS, eDP PHY and eDP rail remain disabled | Plasma hardware enablement remains a separate later task. |
| Backlight description | A `pwm-backlight` node already exists and its PMK8550 PWM provider is enabled | Adding another backlight node is not a justified next fix. |

Relevant saved audits: `keyboard-chain-audit.txt`, `inspect-compiled-suppliers.txt`, `inspect-local-console.txt`, and `check-next-step.txt`. An independent `lsinitcpio -l` read also confirmed that `hid-generic`, `usbhid`, `gpi` and `i2c-qcom-geni` are present while the two I2C-HID modules are not.

### Important correction to a research finding

Searching only the top-level board DTS and finding no `interconnect` or `gem` string does **not** show that GEM is absent from the board's effective graph. The pinned `hamoa.dtsi` defines I2C9's `qup-config` route through `gem_noc`, and its DMA references point at `gpi_dma1`.[13] The compiled DTB independently confirms both. DT21's local I2C5 no-vote workaround is not an upstream absence-of-ICC configuration to assume for every bus.

Similarly, GPU and MDSS in our compiled tree still contain GEM references. Enabling GPU/MDSS while leaving those dependencies unresolved is not a complete display repair. The existing PWM/backlight objects must be audited, not duplicated.

## Ranked next implementation

### 1. Repair keyboard dependency closure, keeping the working USB path intact

- Restore only the configured keyboard's fixed 3.3 V supplier to the expert-described state; preserve its voltage and GPIO definition. Do not restore every disabled rail.
- Resolve I2C9's mandatory dead ICC dependency. A narrowly scoped diagnostic extension of dt21's existing no-vote approach is a candidate; it skips normal bandwidth voting and must not be represented as an upstream or production-quality solution.
- Audit and, if required for the GENI mode, enable the correctly referenced `gpi_dma1`, preserving its existing channel, IOMMU and controller definitions. Keep this conditional requirement distinct from the already-proven missing regulator/ICC closure.
- Pack and explicitly early-load `i2c-hid-of` with its dependency closure. Check the actual archive and runtime module list, not merely a successful build.
- Keep dt21's proven repeater/USB settings, the current rollback and bounded logger unchanged.

This is a concrete repair candidate for real input blockers, not a claim that it alone will make the prompt visible or boot Plasma.

### 2. Boot normal systemd in text mode with an explicit TTY

Use the normal live-root init instead of the diagnostic Bash override, with `systemd.unit=multi-user.target`. Systemd defines that target as non-graphical multi-user operation.[6] Use the standard `getty@tty1` path with explicit TTY ownership rather than an ad-hoc PID1 shell on `/dev/console`; systemd's getty template supplies TTY-backed input/output and a named `TTYPath`.[7] The kernel distinguishes the foreground virtual console from a specific VT, so `console=tty0` is not itself a full login/session setup.[5]

Our live root already contains systemd and getty and enables [REDACTED_EMAIL]`. The USB logger service is staged by `builder/initcpio/hooks/kestrel_log` into `sysinit.target.wants`; its absence from the static root's `multi-user.target.wants` is not evidence that logging is disabled. Verify that staged service in the exact candidate.

If a local diagnostic shell is needed before login configuration is validated, use a deliberately scoped systemd debug-shell mechanism rather than introducing an unreviewed custom PID1 supervisor.[8] Keep such a shell restricted to the diagnostic live boot, not a production image default.

### 3. Native acceptance, not more pre-exec-only evidence

Require all of: systemd actually running as PID1; recovered userspace journal/service evidence; a visible text console or independently verified console route; and a command typed on a positively identified physical keyboard whose output is recovered or visible. A marker written from inside executed Bash can additionally prove Bash startup. A parent-process heartbeat or `kill -0` check cannot prove that a child successfully execed Bash, read a key, or is not a zombie.

QEMU remains an exact-candidate regression gate for live-root/systemd/logging only. It cannot validate the physical I2C keyboard, PMIC rail or panel.

### 4. Then restore native graphics as a separate dependency-driven repair

Audit the exact panel/rail/PHY/MDSS/dispcc, GPU/GMU, firmware and interconnect dependencies together against the pinned expert tree.[14] Do not simply remove blacklists or globally re-enable GEM after the earlier native resets. Restore thermal observation before sustained graphics workloads; thermal nodes are still disabled in the current diagnostic tree. Keep Windows-derived firmware local-only.

A fresh, board-matched Ubuntu/expert live image on separate approved media is an optional control if the repaired text path still fails—not a reason to overwrite the working Kestrel stick or repeat an old, already-failing control unchanged. Its exact DTB and loader workarounds must be verified first.

## Flags not to copy

Do not adopt the community report's `efi=noruntime`: it conflicts with our owned-variable firmware logger. Do not blacklist `gpi`: the existing native USB breakthrough depends on the GPI closure we deliberately added. Do not copy touchpad GPIO/address or fingerprint USB changes without matching physical hardware. Do not blanket-enable `regulator_ignore_unused` or introduce the ECV workaround without identifying the specific problem it is meant to address. These are source-comparison candidates, not established repairs for our present frontier.

## Scope and status

Only public retrieval, local read-only audits, research helpers and documentation were performed for this research. No kernel/DT/build configuration, USB boot file, firmware variable, internal-storage layout, BIOS, BCD or boot order was changed. No new candidate was built and no new native boot was verified. Dt23 remains a diagnostic revision, not the repair recommended above.

## Sources

[1] https://discussion.fedoraproject.org/t/fedora-44-on-snapdragon-x-end-to-end-installation-hardware-enablement-for-lenovo-ideapad-slim-3x-83n3/204767
[2] https://github.com/ubuntu/stubble/pull/69
[3] https://bugs.launchpad.net/bugs/2114876
[5] https://docs.kernel.org/admin-guide/serial-console.html
[6] https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.special.xml
[7] https://raw.githubusercontent.com/systemd/systemd/main/units/getty@.service.in
[8] https://raw.githubusercontent.com/systemd/systemd/main/man/systemd-debug-generator.xml
[10] https://fedoraproject.org/wiki/Snapdragon_WoA_Laptop_Install — Fedora Snapdragon installation guidance
[11] https://discourse.ubuntu.com/t/faq-ubuntu-25-04-25-10-on-snapdragon-x-elite/61016 — Ubuntu Snapdragon FAQ and Concept kernel differences
[12] https://packages.debian.org/sid/misc/qcom-firmware-extract — Debian Qualcomm firmware extraction package
[13] https://raw.githubusercontent.com/jglathe/linux_ms_dev_kit/3f0d8691afa098ba378d7d5a3968f03219887719/arch/arm64/boot/dts/qcom/hamoa.dtsi — Pinned Hamoa inherited I2C9 suppliers
[14] https://raw.githubusercontent.com/jglathe/linux_ms_dev_kit/3f0d8691afa098ba378d7d5a3968f03219887719/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts — Pinned exact Lenovo 15Q8X10 board DTS
