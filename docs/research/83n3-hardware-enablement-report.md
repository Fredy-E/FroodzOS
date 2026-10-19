# IdeaPad Slim 3 15Q8X10 (83N3, Snapdragon X1-26-100): Linux hardware-enablement report

**Purpose:** device #1 research for the CachyOS-derived ARM64 distro (see `docs/project-brief.md`). Research only — nothing was installed, flashed, or changed. All evidence fetched from public sources on **2026-10-07** (HTTP, read-only). Unit under study: 83N3, BIOS RVCN21WW, FastConnect 7800 (WCN7850 -> ath12k), Secure Boot off, BitLocker off (per inventory). Ubuntu Concept and the community trees below are *sources to reuse*, not the target product.

## 1. Bottom line

- **Initial enablement for this exact model exists** in Ubuntu's experimental "Ubuntu Concept 26.10 Snapdragon Edition" ISO (tobhe, 2026-09-29): its additions list includes "New X1 machines -> Lenovo IdeaPad Slim 3". ISO `stonking-desktop-arm64+x1e.iso`, 4,645,531,648 bytes, Last-Modified 2026-09-29 15:03:44 GMT; "initial enablement" is explicitly experimental [S1][S2].
- **Not yet verified publicly.** No end-to-end user verification of the current image on a Slim 3 was found; the most recent community evidence is the DT author running a Slim 3 variant with a known EC caveat (2026-07-06) [S12]. Failure reports that exist (2025-11 .. 2026-05) predate the DT/stubble merges and must not be assumed current [S8].
- **Boot chain:** the firmware ships no device tree (its ACPI is not usable by Linux). Ubuntu uses **stubble** — "a minimal UEFI kernel boot stub ... loading machine specific device trees embedded within a kernel image" — matching SMBIOS HWIDs to a DTB before jumping to the kernel [S4]. The Slim 3 HWID entry (18 IDs) merged 2026-07-17 (PR #69, commit 9f11278, "even though it isn't supported upstream yet" — tobhe); Ubuntu shipped stubble 14-1 on 2026-09-28, one day before the ISO [S3][S5].
- **Device tree is community-maintained, not upstream:** `x126100-lenovo-ideapad-slim3.dts` (Jens Glathe, branch `jg/ubuntu-qcom-x1e-7.3rc`, last changed 2026-08-14, commit bc513d262c8d); absent from the torvalds mirror (404) and from `linux-msm/laptops-kernel` on 2026-10-07 [S6][S7]. Ship it as a managed board profile, not a mainline assumption.
- **Three concrete gaps to design around:** (1) `qcom-firmware-extract` v20 rejects this model — "error: Device is currently not supported" — so manual firmware staging is required for now [S9]; (2) the touchpad has an unpublished GPIO-IRQ-mux dependency for some panel variants [S8]; (3) the EC node was disabled after a fan failure: "after firmware update fan would cease to function. Removing the EC node was the interim solution" (Glathe, 2026-07-06) [S12][S6].
- **Wi-Fi variant matters:** this unit's FastConnect 7800 = WCN7850 (ath12k) — the variant the DT targets (`pci17cb,1107`, `wcn7850-pmu`, `wcn7850-bt`). Units with WCN6855 (ath11k) exist: "will need a dtb for ath11k (WCN6855) and ath12k (WCN785x)" (Glathe, 2026-06-09) — capture card variant in every board profile [S3][S6].

## 2. Hardware/boot matrix (per-device vs inherited)

| Area | Status for this unit (2026-10-07) | Evidence | Class |
|---|---|---|---|
| Boot / DTB selection | stubble HWID match expected (BIOS RVCN21WW matches the merged capture); no firmware DT | S3,S4,S5 | proven mechanism; this unit's match unverified |
| Device tree | `x126100-lenovo-ideapad-slim3.dts` (community); NVMe/USB/Wi-Fi/audio/display nodes; EC node disabled | S6 | per-device; not upstream |
| Kernel | Linux 7.3 (26.10); concept `linux-qcom-x1e 7.3.0-15.15` (stonking, 2026-09-17); official 7.3.0-6.6 sync 2026-09-26 used patches from linux-msm/laptops-kernel | S9,S10 | broad base + per-device patches |
| Display / GPU | eDP + MDSS + Adreno X1-45 + zap shader + PWM backlight in DT; GPU firmware via Windows extract | S6 | initial; unverified |
| Wi-Fi / Bluetooth | WCN7850 (ath12k); a WCN7850 5 GHz regression was reported on 6.17 (Slim 7x) — test 5 GHz | S3,S6,S11 | per-variant; test |
| Trackpad | one of four variants enabled (GXTP5100 @0x5d); "The touchpad wont work without a GPIO IRQ MUX driver which I have written but have not published yet" (mikevale, 2026-05-29) | S6,S8 | unknown; test |
| Keyboard | i2c-hid `keyboard@3a` with IRQ | S6 | expected; test |
| Audio | WCD9385 + WSA8845 speakers + sndcard in DT; ADSP firmware needed; speakers were "work in progress" class in FAQ era | S6,S11 | initial; test |
| Battery / charging | via pmic-glink/ADSP (`battmgr.jsn`); EC node disabled 2026-07-06 (fan fail) | S6,S12 | interim; test |
| USB / external displays | Type-C SS0 (SBU mux + PTN3222 retimer), eUSB2 repeaters, pmic-glink, HDMI (RTD2171), DP-alt sound | S6 | per-device DT; test |
| NVMe | pcie3 + rails (fixes: regs always-on, 2 s startup delay) | S6 | expected; verify read-only |
| Suspend | no per-device data; thread: "If the laptop sleeps, Wi-Fi is gone" (device unspecified) | S1 | unknown; defer |
| Firmware extraction | QFE v20 fails on this model; manual staging into `/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/` with the DT names (`qcadsp8380`/`qccdsp8380` .mbn, `adsp_dtbs`/`cdsp_dtbs` .elf, `adspr`/`adsps`/`adspua`/`battmgr` .jsn, `qcdxkmsuc8380`/`qcdxkmsucpurwa` .mbn) | S9,S6 | finding |
| Redistribution | firmware "not available under a compatible license"; "Respect the firmware's license terms and your local laws/policies before redistribution" — keep extraction local | S1,S9 | constraint |

## 3. Exact artifacts and working branches

- **Image:** `stonking-desktop-arm64+x1e.iso` (+ dated `...-20260929.iso`) at https://people.canonical.com/~platform/images/ubuntu-concept/. No SHA256SUMS file is published in that directory (checked 2026-10-07) [S2].
- **DT:** `jglathe/linux_ms_dev_kit`, branch `jg/ubuntu-qcom-x1e-7.3rc`, file `arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts`; compatible `lenovo,ideapad-slim3`, `lenovo,thinkpad-t14s`, `qcom,x126100`, `qcom,x1p42100`. Recent commits: backlight (2026-08-14), eUSB2 renumbering (2026-08-14), EC node disabled (2026-07-06), PCIe 7.0 syntax (2026-05-31) [S6].
- **stubble:** `ubuntu/stubble` PR #69; merged commit `9f11278e080a5c4a77db6acf4c8f75c14412087a`; file `hwids/json/x126100-lenovo-ideapad-slim3.json`; Ubuntu package stubble 14-1 (2026-09-28) [S3][S5].
- **Trackers:** Launchpad ubuntu-concept #2114876 (2025-06-18) and #2162975 (2026-08-06); kernel sync #2167217; QFE model-mapping precedent #2169092 [S8][S9][S10].
- **CachyOS base state:** no official ARM64 port — "There are no plans for this as of yet" (linux-cachyos issue #646, closed 2025-12-18); maintainer position unchanged through 2026-08-19; community precedent (nabu-cachyos) = Arch Linux ARM base + CachyOS kernel patches, noting "Most CachyOS packages are x86-only" [S13][S14].

## 4. Safest first-contact sequence (live USB; non-installing, non-persistent)

1. **Media:** 8 GB+ USB stick (none attached); write the ISO with an ARM64/UEFI-capable writer. No server-side checksum exists — rely on HTTPS + the writer's verification.
2. **Firmware posture:** leave Secure Boot, TESTSIGNING, Hyper-V, boot order untouched; use the one-time boot menu (F12). No key resets or updates. BitLocker is off (inventory), so no recovery-key step.
3. **At GRUB:** choose the live/try session only. No installer, no internal-disk mounts, no EFI-variable writes.
4. **Known messages:** "error: file /boot/ not found" (seen on earlier images; non-fatal only if boot proceeds) and the red `pe.c:372@pe_locate_sections: HWID matching failed, no DT blob will be selected` (no DTB chosen — capture, stop, report).
5. **Read-only checks:** `cat /proc/device-tree/model` (expect "Lenovo IdeaPad Slim 3 15Q8X10"); display/brightness; keyboard; trackpad; `dmesg | grep -iE 'ath12k|wcn7850|stubble'`; Wi-Fi scan incl. 5 GHz; battery %; quick speaker/mic test; USB ports. Defer suspend.
6. **Capture:** `dmesg`, `journalctl -b`, `dmidecode`, `lspci -nnk`, `lsusb` -> `docs/research/evidence/`.
7. **Exit:** boot Windows; confirm nothing changed (no installs, mounts, or firmware edits).
8. **Gate:** move toward image/install planning only after the gaps above are accepted; no blind flashing.

## 5. Fallback and recovery gates

- Windows stays default and intact; this sequence writes nothing to NVMe. If boot fails: try another port / re-write media; don't chase pre-July-2026 workarounds (DT-less era).
- Existing fallbacks: the DT author's non-official ISO builds (linked from PR #69); later, an image built from the same DT + stubble inputs once the port has a builder.
- If stubble matching fails: refresh an ubuntu-concept device bug (pattern #2162975) with `dmidecode` + HWIDs; keep `stubble.dtb_override` experiments on a disposable medium.
- BIOS: test first on RVCN21WW; don't update before first contact. BIOS-bearing HWIDs change with updates (captures: RVCN21WW, RVCN25WW; RVCN18WW on an older unit) — re-verify matching after any update.

## 6. What this means for a multi-device distro (board profiles + tiers)

- **Board profile = {DT file + branch/commit, firmware profile (redistributable + Windows-extract list), hwids mapping, quirks/settings, test status}.** The Slim 3 shows why: the DTB changes with the Wi-Fi card variant; firmware mapping is per model; none of it is machine-introspectable.
- **DTB selection is a designed subsystem.** Proven options: stubble-style UKI embedding (used here), systemd >= 257 UKI HWID auto-selection, ESP driver + device DB (postmarketOS style). Pick one; keep the DB in-tree.
- **Support tiers (proposed):** T1 verified on real hardware (boot + input + storage + network + battery); T2 boots with documented gaps; T3 initial enablement (Slim 3 today). Tier each feature per machine.
- **Feature gates, dependency order:** boot -> input/display -> NVMe/network -> firmware extraction -> battery/power -> audio/mic -> accelerated GPU -> suspend -> camera -> external monitors -> USB diagnostics. Not promised at first launch; the matrix marks each proven/expected/unknown.
- **Reuse boundaries:** Ubuntu/community code is reference and upstream source, subject to their licenses; do not silently convert the product into Ubuntu. Extracted Windows firmware stays local to the device.
- **"Oracle ARM64":** unresolved per brief — do not assume OCI/VirtualBox/Oracle Linux. If it means an OCI Ampere A1 build/CI node: standard UEFI/ACPI server, a separate simpler tier, no Snapdragon DT work.

## 7. Unknowns and open questions

1. Define "Oracle ARM64" (unresolved in the brief).
2. USB media for the first live boot: size/availability/timing? (No spare media detected.)
3. Acceptable first-boot gaps: is "no confirmed touchpad/audio/battery/suspend" acceptable for the boot milestone, or must specific peripherals pass first?
4. BIOS stance: hold at RVCN21WW for the first test? (Update later only if a fix demands it.)
5. QFE gap handling: manual per-device staging now, an upstream model-mapping patch later, or both?
6. Which machine defines the T1 template for the public fleet (the well-supported T14s-class devices are the obvious donor, subject to licensing)?
7. Confirm evidence convention: `docs/research/evidence/` in this folder.

## Sources (fetched 2026-10-07)

- [S1] Ubuntu Concept 26.10 Snapdragon Edition — https://discourse.ubuntu.com/t/ubuntu-concept-26-10-snapdragon-edition/88518 (first post 2026-09-29)
- [S2] Concept image directory (ISO name/size/date; HTTP HEAD) — https://people.canonical.com/~platform/images/ubuntu-concept/
- [S3] stubble PR #69 "hwids: Add Lenovo IdeaPad Slim 3 15Q8X10" — https://github.com/ubuntu/stubble/pull/69 (merged 2026-07-17)
- [S4] stubble README (DTB selection: HWID / compatible string / machdb) — https://github.com/ubuntu/stubble
- [S5] stubble 14-1 (Launchpad) + merged hwids JSON — https://launchpad.net/~ubuntu-concept/+archive/ubuntu/x1e , https://raw.githubusercontent.com/ubuntu/stubble/main/hwids/json/x126100-lenovo-ideapad-slim3.json
- [S6] Device tree + commit history — https://raw.githubusercontent.com/jglathe/linux_ms_dev_kit/jg/ubuntu-qcom-x1e-7.3rc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts
- [S7] linux-msm/laptops-kernel (no Slim 3 DT on 2026-10-07) — https://github.com/linux-msm/laptops-kernel
- [S8] Launchpad #2114876, #2162975 — https://bugs.launchpad.net/bugs/2114876 , https://bugs.launchpad.net/bugs/2162975
- [S9] qcom-firmware-extract v20 + manpage — https://git.launchpad.net/ubuntu/+source/qcom-firmware-extract (ref ubuntu/stonking) , https://manpages.debian.org/unstable/qcom-firmware-extract/qcom-firmware-extract.8
- [S10] Kernel sync #2167217 (linux 7.3.0-6.6 changelog, 2026-09-26) — https://bugs.launchpad.net/ubuntu/+source/linux/+bug/2167217
- [S11] FAQ 25.04/25.10 (dual-boot advice; WIP classes; WCN7850 5 GHz report) — https://discourse.ubuntu.com/t/faq-ubuntu-25-04-25-10-on-snapdragon-x-elite/61016
- [S12] Discourse topic 48800, post #1998 (Glathe, 2026-07-06, EC/fan) — https://discourse.ubuntu.com/t/48800/1998
- [S13] CachyOS ARM64 status — https://github.com/CachyOS/linux-cachyos/issues/646 , https://discuss.cachyos.org/t/arm-future-for-cachyos/727 , https://discuss.cachyos.org/t/please-make-an-arm64-version/28549
- [S14] nabu-cachyos (community ARM precedent) — https://github.com/FisiFla/nabu-cachyos

*Research-only document. No installs, media writes, firmware extraction, or configuration changes were performed; all fetches were public HTTP reads.*
