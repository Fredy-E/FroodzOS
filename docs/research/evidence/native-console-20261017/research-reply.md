**The next step is a real keyboard/input repair plus normal systemd text boot—not another marker-only revision.**

I checked the expert kernel tree, Ubuntu/stubble discussions, Fedora and other ARM distro projects. The useful findings are:

- **Exact-model evidence exists:** a Fedora author reports KDE running on **83N3 / 15Q8X10**.[1] **[unverified — single source: https://discussion.fedoraproject.org/t/fedora-44-on-snapdragon-x-end-to-end-installation-hardware-enablement-for-lenovo-ideapad-slim-3x-83n3/204767]** It includes an AI disclaimer; it is a comparison recipe, not proof on our laptop.
- **Stubble's model mapping is not full hardware support.** Its maintainer discussion explicitly separates the two.[2] Switching distro alone does not solve our current configuration.
- **Our local audit found concrete keyboard blockers:** its 3.3 V supplier is disabled; its I2C9 bus still requires disabled GEM; and the modular I2C-HID drivers are missing from the early initramfs. The inherited I2C9 dependency is also visible in the pinned expert source.[13]

### Recommended repair

1. Restore the keyboard's specific power supplier and resolve **I2C9's dead interconnect dependency**, preserving the USB fix. Audit **GPI1** too: it is disabled and is required if that bus uses GPI DMA.
2. Include and early-load **`i2c-hid-of` and its dependencies**.
3. Stop selecting Bash as PID1 for the forward-progress entry. Boot normal **systemd → `multi-user.target` → `getty@tty1`**, keeping the USB logger. Multi-user target is explicitly non-graphical.[6]
4. Require **actual typed input and recovered systemd logs** before restoring GPU/MDSS/Plasma as a separate repair.

**Why this matters:** #8/#9 currently bypass systemd intentionally. Even a working Bash there will never automatically continue into Plasma. Also, our PWM/backlight node already exists—adding another one, as one review suggested, would not address the actual disabled dependencies.

**Research completed; no boot files changed.** The recommendation is not yet built or native-tested. I saved the detailed findings and linked them from the diagnosis document.

## Sources

[1] https://discussion.fedoraproject.org/t/fedora-44-on-snapdragon-x-end-to-end-installation-hardware-enablement-for-lenovo-ideapad-slim-3x-83n3/204767
[2] https://github.com/ubuntu/stubble/pull/69
[6] https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.special.xml
[13] https://raw.githubusercontent.com/jglathe/linux_ms_dev_kit/3f0d8691afa098ba378d7d5a3968f03219887719/arch/arm64/boot/dts/qcom/hamoa.dtsi — Pinned Hamoa inherited I2C9 suppliers
