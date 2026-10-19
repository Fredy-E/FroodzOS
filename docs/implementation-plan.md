# FroodzOS — implementation plan (historical design)

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


> **Current tasks:** [TASKS.md](TASKS.md); current status: [project progress](project-progress.md). Native dt25b text/typed input and all 20 CPU/cpuss thermal readouts are verified. The cleaned physical GRUB menu now defaults to **#1 dt25b text**, with a distinct **#2 dt24 text recovery** image. Native shutdown, full graphics guard and software-Plasma gates remain open. Menu syntax/hashes are verified; the new menu arrangement still awaits its owner-executed native retest.
>
> The original phased design below is retained as history, not executable current instructions. Its systemd-boot, formatter/erase, open-name and early authorization assumptions have been superseded. Do not reformat the existing stick, rearm firmware, or restart completed bootstrap tasks from this old plan. Current publication remains deferred and separately approval-gated.

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Produce a bootable unofficial CachyOS-derived ARM64 live USB for the Lenovo IdeaPad Slim 3 15Q8X10 (83N3), then an ARM64 VirtualBox guest image, backed by our own signed ARMv8-A package overlay — without touching Windows, Kali, or upstream infrastructure.

**Architecture:** Native ARM64 builds in a separate WSL2 distro on this laptop (ALARM rootfs + our signed overlay `[cachyos-arm64]`); hardware-enablement kernel (Linux 7.3-line + Slim 3 DTS) shipped as a stubble HWID-matched UKI on a systemd-boot ESP; firmware staged locally from the machine's own Windows installation and never redistributed. Design rationale and citations: `docs/porting-design.md`.

**Tech Stack:** WSL2 (ARM64), Arch Linux ARM rootfs, makepkg/devtools, Linux 7.3 kernel + community Slim 3 DTS, stubble + ukify/stubblify, systemd-boot, pacman + repo-add (signed), archiso-aarch64 profile (or manual GPT image), qemu-system-aarch64 (smoke tests only).

**Authorization gates (hard stops):** G-A = creating the WSL builder and fetching sources (needs user go). G-B = writing the 64 GB USB stick (erases it; user executes). G-C = booting the laptop from USB (user executes). G-D = any publication (per-artifact user approval only). Nothing in this plan modifies BIOS, boot security, internal disks, Kali, or Windows.

---

## Phase 0 — control test: Ubuntu Concept live USB (USER-EXECUTED, G-B/G-C)

Purpose: isolate firmware/driver reality from our own image. Ubuntu is a control, never the project base.

### Task 0.1: Download and record the control image
**Files:** `D:\CachyOS-ARM64\testing\control\`
1. `mkdir -p /d/CachyOS-ARM64/testing/control && cd /d/CachyOS-ARM64/testing/control`
2. `curl -fL -o stonking-desktop-arm64+x1e.iso "https://people.canonical.com/~platform/images/ubuntu-concept/stonking-desktop-arm64+x1e.iso"`
3. `sha256sum stonking-desktop-arm64+x1e.iso | tee SHA256SUMS` (no published checksum exists — HTTPS + recorded hash is the provenance; note this in `control-notes.md`).
**Verify:** file ≈ 4,645,531,648 bytes; `sha256sum` recorded.

### Task 0.2: Write the stick and boot (USER executes — G-B erases the 64 GB stick)
1. User writes the ISO to the USB stick with a Windows writer (Rufus/`dd` equivalent) after confirming the target drive.
2. One-time boot menu (F12) only; leave Secure Boot, TESTSIGNING, boot order untouched. Select the live/try session; **no installer, no internal-disk mounts**.
3. Watch for `HWID matching failed, no DT blob will be selected` — if seen, capture a photo/log and stop (our design depends on HWID matching).
**Verify:** `/proc/device-tree/model` reads `Lenovo IdeaPad Slim 3 15Q8X10`; desktop visible; fan audible/temperature sane (`sensors` or `/sys/class/thermal`).

### Task 0.3: Capture control evidence
1. Save `dmesg`, `journalctl -b`, `dmidecode -t1`, `lspci -nnk`, `lsusb`, `cat /proc/device-tree/model`, thermal readings to `D:\CachyOS-ARM64\testing\control\evidence\`.
2. Record per-feature status (display, keyboard, touchpad, Wi-Fi, audio, battery, USB) in `control-notes.md` — which firmware files were demanded (grep `dmesg` for `qcom|firmware|failed`).
3. Power off; boot Windows; confirm nothing changed.
**Verify:** `control-notes.md` lists every feature as works/broken/unknown; firmware demands listed. Output feeds our firmware-staging script (Task 3.4).

---

## Phase 1 — builder bootstrap (G-A)

### Task 1.1: Fetch and verify the ALARM rootfs
**Files:** `D:\CachyOS-ARM64\builder\downloads\`
1. `mkdir -p /d/CachyOS-ARM64/builder/downloads && cd /d/CachyOS-ARM64/builder/downloads`
2. `curl -fL -O https://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz && curl -fL -O https://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz.sig`
3. `gpg --keyserver keyserver.ubuntu.com --recv-keys 68B3537F39A313B3E574D06777193F152BDBE6A6` (Arch Linux ARM Build System key per `docs/porting-design.md` [29])
4. `gpg --verify ArchLinuxARM-aarch64-latest.tar.gz.sig ArchLinuxARM-aarch64-latest.tar.gz && sha256sum ArchLinuxARM-aarch64-latest.tar.gz | tee SHA256SUMS`
**Verify:** `Good signature from "Arch Linux ARM Build System"`; checksum recorded in `builder/downloads/SHA256SUMS`.

### Task 1.2: Import the builder as a separate WSL2 distro
1. `wsl.exe --import CachyOSBuilder "D:\CachyOS-ARM64\builder" "D:\CachyOS-ARM64\builder\downloads\ArchLinuxARM-aarch64-latest.tar.gz" --version 2`
2. `wsl.exe -d CachyOSBuilder -u root -- uname -m` → expect `aarch64`.
**Verify:** distro listed by `wsl.exe --list --verbose` as `CachyOSBuilder`, running version 2; Kali untouched (`wsl.exe --list --verbose` still shows it stopped).

### Task 1.3: Configure builder user, pacman, and swap budget
1. `wsl.exe -d CachyOSBuilder -u root -- sh -c "pacman-key --init && pacman-key --populate archlinuxarm"` (model per [29])
2. `wsl.exe -d CachyOSBuilder -u root -- sh -c "useradd -m -G wheel builder && echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder && printf '[user]\ndefault=builder\n[boot]\nsystemd=true\n' > /etc/wsl.conf"`
3. `wsl.exe --terminate CachyOSBuilder` then `wsl.exe -d CachyOSBuilder -- whoami` → `builder`.
4. `wsl.exe -d CachyOSBuilder -- sudo pacman -Syu --noconfirm && sudo pacman -S --needed --noconfirm base-devel git debugedit qemu-system-aarch64`
5. Add swap only if RAM is short: create `D:\CachyOS-ARM64\builder\swapfile` (6 GiB) and mount it in the builder (`fallocate`, `chmod 600`, `mkswap`, `swapon` via sudo in WSL).
**Verify:** `wsl.exe -d CachyOSBuilder -- makepkg --version` runs; `free -h` inside builder shows ≥ 6 GiB RAM or active swap; builds capped at `MAKEFLAGS=-j4`.

### Task 1.4: G0b — prove the ARMv8-A baseline
1. `wsl.exe -d CachyOSBuilder -- sh -c "readelf -A /usr/lib/libc.so.6 | grep Tag_CPU_arch"` → expect `ARMv8-A` (not `ARMv8.2`).
2. Same check on `/usr/bin/bash` and `/usr/lib/libssl.so*`.
3. Smoke: build the `hello` package (`git clone` ALARM PKGBUILDs pinned commit, `makepkg -s` in it), then `readelf -A` on the built binary.
**Verify:** every checked binary reports `Tag_CPU_arch: v8-A` (or lower). If any reports v8.2: base is rejected → switch to the ARMv8/8.1 community repo (`docs/porting-design.md` §2.2) and re-run this task. Record the verdict in `D:\CachyOS-ARM64\docs\decisions.md`.

### Task 1.5: First signed package (G1)
1. `gpg --quick-generate-key "Builder <builder@local>" ed25519 sign 0` inside builder (throwaway build key; real key model is ADR-7 and comes in Phase 3).
2. `wsl.exe -d CachyOSBuilder -- bash -c "cd ~/build/hello && makepkg -s --sign --key 'builder@local'"`
3. `sudo pacman -U hello-*.pkg.tar.zst` then `pacman -Qi hello` and `pacman -Svv hello 2>&1 | grep -i sig`.
**Verify:** package installs; signature check shows the build key. G1 = **PASS**.

---

## Phase 2 — kernel + device tree + stubble UKI (G2)

### Task 2.1: Pin upstream sources
**Files:** `D:\CachyOS-ARM64\pkgs\linux-cachyos-arm64\SOURCES.md`
1. Record pinned refs (from `docs/porting-design.md` §2.3 and the hardware report): kernel 7.3.x tarball; `jglathe/linux_ms_dev_kit` branch `jg/ubuntu-qcom-x1e-7.3rc` (commit `bc513d262c8d`) for `arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts`; `ubuntu/stubble` at the commit containing `hwids/json/x126100-lenovo-ideapad-slim3.json` (PR #69 merge `9f11278e080a`).
2. Fetch each with `git clone --filter=blob:none` + `git checkout <commit>`; record `git rev-parse HEAD` in `SOURCES.md`.
**Verify:** `SOURCES.md` lists URL + commit + license per source; DTS present at the pinned path.

### Task 2.2: Kernel package `linux-cachyos-arm64`
**Files:** `D:\CachyOS-ARM64\pkgs\linux-cachyos-arm64\PKGBUILD`, `config`
1. Start from ALARM's `linux-aarch64` PKGBUILD (pinned commit); set `pkgname=linux-cachyos-arm64`, `arch=('aarch64')`, localversion `-cachyos-arm64`.
2. Add the Slim 3 DTS as a patch/source; `make defconfig` + `scripts/config` for: `CONFIG_ARM64=y`, ACPI + EFI stub, msm/adreno + DPU, ath12k (WCN7850), soundwire/WCD9385, NVMe, USB, HID over I2C; **no LTO, no x86 families** (design ADR-3).
3. `wsl.exe -d CachyOSBuilder -- bash -c "cd ~/pkgs/linux-cachyos-arm64 && makepkg -s --skipchecksums --holdver"` (first iteration; pin checksums afterwards).
**Verify:** build exits 0; `pacman -Qip` shows `linux-cachyos-arm64` with `aarch64`; package contains `/boot/Image` (or `vmlinuz-*`) + DTBs incl. `x126100-lenovo-ideapad-slim3.dtb`.

### Task 2.3: Build stubble and the UKI
1. Build stubble per its pinned README (`docs/porting-design.md` [32]); package it as `stubble-git`.
2. Generate the UKI: `stubblify build --linux=/boot/vmlinuz-linux-cachyos-arm64 --stub=stubble.efi --hwids=<pinned>/hwids/json --devicetree-auto=.../x126100-lenovo-ideapad-slim3.dtb --output=vmlinuz.efi` (exact flags per pinned README).
3. Package `linux-cachyos-arm64-uki` containing `vmlinuz.efi`.
**Verify:** `stubblify` output contains `.hwids` + `.dtbauto` sections (`objdump -h vmlinuz.efi`); HWID JSON for 83N3 present.

### Task 2.4: QEMU smoke boot (G2)
1. `qemu-system-aarch64 -M virt -cpu cortex-a57 -kernel <Image> -initrd <initramfs> -append "console=ttyAMA0" -nographic` inside the builder (initramfs via `mkinitcpio` in a chroot).
2. Separately boot the full rootfs: `qemu-system-aarch64 -M virt -cpu cortex-a53 ...` to prove ARMv8-A runtime.
**Verify:** kernel reaches userspace or at minimum mounts root; `cortex-a53` boot = G0b runtime proof. G2 = **PASS** when both smoke boots complete. This proves nothing about the laptop.

---

## Phase 3 — overlay packages + signed repo (G5 prerequisites)

### Task 3.1: Project keyring (ADR-7)
1. Offline master key (user-held export to `D:\CachyOS-ARM64\keys\offline\` — never in the builder); build key in builder.
2. Package `cachyos-arm64-keyring` (neutral name pending ADR-8) with `pacman-key --populate` support.
**Verify:** `pacman-key --list-keys` shows master + build key; local package installs with `pacman -U --verify`.

### Task 3.2: Overlay identity packages
1. Port `cachyos-settings`, `cachyos-hooks` (strip `ID=cachyos`, logos, URLs — ADR-8), `cachyos-mirrorlist` (own `[cachyos-arm64]` only), `systemd-boot-manager`; each from pinned CachyOS sources with license headers preserved.
2. `cachyos-kernel-manager` already declares `arch=(aarch64 x86_64)` — build it; defer `chwd` (x86-only profiles) and `cachyos-hello`.
**Verify:** each builds under `makepkg`; `os-release` shows neutral ID + `NAME` + `ID_LIKE=arch`; no CachyOS mirror is referenced anywhere in the rootfs.

### Task 3.3: Repository with signed DBs (G5)
1. `repo-add --sign --verify /srv/cachyos-arm64/aarch64/cachyos-arm64.db.tar.gz *.pkg.tar.zst` in the builder.
2. Point `pacman.conf` at `Server = file:///srv/cachyos-arm64/aarch64`; `pacman -Syu` inside a clean chroot.
**Verify:** `pacman -Sy` verifies both package and DB signatures (unlike ALARM's unsigned DBs [29]); `pacman -Syu` completes in a fresh chroot. G5 = **PASS**.

### Task 3.4: Firmware staging script (local-only, ADR-5)
**Files:** `D:\CachyOS-ARM64\tools\setup-local-firmware.sh`
1. Script copies the required firmware files from the machine's Windows DriverStore (read-only NTFS mount in the live session or via `\\wsl$` export) into `/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/`, matching the DTS names (`qcadsp8380.mbn`, `qccdsp8380.mbn`, `qcdxkmsuc8380.mbn`, `qcdxkmsucpurwa.mbn`, `adsp_dtbs.elf`, `cdsp_dtbs.elf`, `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`).
2. Refuse to run if BitLocker is detected locked; never write back to Windows; log file list (names only) to `firmware-staged.log`.
**Verify:** shellcheck-clean; dry-run mode prints actions only; on this machine it stages ≥ the files demanded in Task 0.3's `dmesg`.

---

## Phase 4 — image assembly

### Task 4.1: Choose the assembler
1. Inspect `ironrobin/archiso-aarch64` at a pinned commit (`docs/porting-design.md` [46]) — its profile + stubble integration is the primary path.
2. Decision recorded in `D:\CachyOS-ARM64\docs\decisions.md`: adapt its profile (replace kernel/UKI with ours, repos with ours) **or** manual assembly (Task 4.2 fallback).
**Verify:** decision note written with commit pin.

### Task 4.2: Manual GPT image fallback (if 4.1 fails)
1. `truncate -s 8G cachyos-arm64-live.img`; `sfdisk` GPT: 512 MiB EF00 ESP + rest Linux.
2. `mkfs.fat -F32` + `mkfs.ext4`; mount; `pacstrap` the rootfs from our repos; `bootctl --esp-path=<mnt>` + copy `vmlinuz.efi`; fstab + minimal `airootfs` overlays (live user, no root login).
3. `mksquashfs` root → `overlayfs` live semantics, or plain ext4 (record choice).
**Verify:** `sfdisk -l` shows the GPT; `file cachyos-arm64-live.img` reports boot sector; image ≤ 8 GB.

### Task 4.3: Image manifest and checksums
1. Write `manifest.txt` (package versions, kernel version, DTS commit, stubble commit) + `SHA256SUMS` into `D:\CachyOS-ARM64\artifacts\`.
**Verify:** `sha256sum -c SHA256SUMS` passes on the artifact.

---

## Phase 5 — boot test on the Lenovo (G3/G4, USER-EXECUTED)

### Task 5.1: Write our image (G-B; erases the stick — explicit user approval)
1. User writes `cachyos-arm64-live.img` to the 64 GB stick (same writer path as 0.2), or boots it from Ventoy if preferred.
2. F12 boot; select our entry.
**Verify:** systemd-boot menu appears; the UKI selects the DTB (no `HWID matching failed`); kernel reaches desktop.

### Task 5.2: M1 acceptance checklist (G4)
On the live session: desktop renders; built-in keyboard + wired mouse/keyboard work; wired network gets DHCP; USB storage mounts read-write; `systemctl poweroff` shuts down cleanly. Run `setup-local-firmware.sh` first if display/graphics demand firmware (per Task 0.3 notes). Monitor thermals (`watch -n5 'cat /sys/class/thermal/thermal_zone*/temp'`) the whole session; **power off immediately if fan fails or temperature climbs**.
**Verify:** all five pass = M1 **PASS**. Capture `dmesg`, `journalctl -b`, thermal log to `D:\CachyOS-ARM64\testing\m1-evidence\`. Touchpad/audio/Wi-Fi recorded as known gaps (T2/T3 per design).

---

## Phase 6 — ARM64 VirtualBox guest (G6)

### Task 6.1: Install VirtualBox (USER executes)
1. Download the Windows Arm host package from virtualbox.org (experimental host support — design [14]); user installs; Hyper-V coexistence noted if boot fails.
**Verify:** `VBoxManage --version` runs on this host.

### Task 6.2: Create the ARM64 VM
1. `VBoxManage createvm --name CachyOSArm64 --ostype Linux_64 --register`; 4 GB RAM, 4 vCPU, VMSVGA only, EFI firmware; attach `cachyos-arm64-live.img` as a disk (or boot the UKI via EFI shell).
2. Use the generic UEFI/ACPI boot entry (ADR-4), not the HWID path.
**Verify:** VM boots to the desktop (VMSVGA); `uname -m` = `aarch64`. G6 = **PASS**. No x86 guest on Arm host (not supported [14]).

---

## Phase 7 — post-MVP (only after M1/M2 pass)

1. **Scheduler port:** apply BORE/PRJC patch subset to our kernel tree; A/B benchmark on the Lenovo (boot stability, `sysbench`, interactive latency); keep both kernel flavors only if the win is real.
2. **Touchpad:** track the GPIO IRQ mux driver; bring the touchpad to T1.
3. **Installer:** `archinstall` in image 2.0 (Calamares fork only after naming/licensing clarity).
4. **Optimized tier:** additive `[cachyos-arm64-v2]` repo with `-march=armv8.2-a` — never replaces the baseline.
5. **Gaming experiments:** FEX/Box64 packaging (no compatibility promises; anti-cheat unsupported [48]).
6. **Upstream draft (user sends):** message to [REDACTED_EMAIL]` asking (a) comfort with source-based rebuilds of their GPL-licensed packaging, (b) naming/branding expectations. Agent drafts; **never sends**.
7. **Publication (G-D):** per-artifact approval; GitHub policy preflight already on record.

---

## Decisions now confirmed (2026-10-07 second interview)

Signing = own keyring, packages + DBs signed, local-only until approval. Publication = per-artifact approval only. Test fleet = this Lenovo as the only verified machine. Upstream message = agent drafts, user sends. **Name = still open:** pick from Kestrel Linux / Aster64 / Peregrine Linux / Lumen64 (or your own) before publication.

## Definition of done (project-level)

M1 acceptance passes on the Lenovo with evidence captured; G5 signed-repo flow verified; G6 VM boot verified; every design gate G0b–G6 has a recorded result; no internal-disk, firmware, or Windows state changed; nothing published without explicit approval.
