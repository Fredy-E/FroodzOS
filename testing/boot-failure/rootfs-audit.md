# Rootfs audit — ARM64 live rootfs readiness (Kestrel live stick / Lenovo 83N3)

- Date: 2026-10-09, 08:57–09:12 UTC. Read-only audit by subagent.
- Rootfs audited: `/home/builder/imgroot` inside WSL distro `CachyOSBuilder` (Arch Linux ARM aarch64 under WSL2, host `FEID-CSS`).
- Build script reviewed: `D:/CachyOS-ARM64/builder/build-live-rootfs.sh`; live-boot script: `D:/CachyOS-ARM64/builder/build-live-uki.sh`.
- Method: bash audit snippets piped over stdin into `wsl.exe -d CachyOSBuilder` (nothing written inside the guest; no guest script files were needed). A few commands run as root **purely to read metadata/configs** blocked to the `builder` user.
- Constraints honored: **no writes to rootfs, squashfs, staging, or media**; `/etc/shadow`, `/etc/gshadow` contents and all key material NOT read (perms/listing only).
- Tags: **[obs]** = directly observed output; **[hyp]** = inference that needs runtime confirmation.

## Verdict

Two hard rootfs-side blockers would prevent a Plasma desktop even if the boot chain worked:

1. **SDDM is not enabled** — no `display-manager.service` symlink; `systemctl --root=/home/builder/imgroot is-enabled sddm` → `disabled`. **[obs]**
2. **NetworkManager is not enabled** — `is-enabled NetworkManager` → `disabled`; no `multi-user.target.wants/NetworkManager.service`. **[obs]**

Root cause is visible in the build script: `build-live-rootfs.sh` writes `autologin.conf`, creates user `live`, stages firmware, builds the squashfs — but **never runs any `systemctl enable`** (nor sets hostname/locale). Steps 74–85 create the session identity; enablement is absent.

Everything else needed for the session is present, and the artifact hash chain is verified end-to-end. No WSL contamination, no mounted leftovers, fstab empty (correct), DT↔firmware paths match for every DT-named file.

---

## 1) Users / accounts — PASS (with notes) [obs]

- `live:x:1000:1000::/home/live:/bin/bash`; `wheel:x:998:live`; `/etc/sudoers.d/live` = `live ALL=(ALL) NOPASSWD: ALL`, mode 440 root:root.
- `/home/live` = 0700, numeric owner 1000:1000 (builder-side `ls` resolves uid 1000 to its own `alarm`/`alarm` name — numeric ownership is what counts), contains only skel dotfiles (`.bashrc`, `.bash_profile`, `.bash_logout`); no `.config` yet (first-login artifact).
- `sddm:x:966:966` system user present; `/var/lib/sddm` exists 0700 as 966:966 (builder shows `qemu` for 966 — numeric correct). PAM: `/etc/pam.d/sddm` and `/etc/pam.d/sddm-autologin` both present.
- No `builder`/`wsl` accounts leaked into the rootfs `passwd`. `/etc/shadow` and `/etc/gshadow` are 0600 root:root (content not read, per constraint). Password set-state not verifiable without shadow read — irrelevant because SDDM autologin is passwordless.
- `/root/.ssh` exists but is **empty** (0 entries). `/etc/ssh` contains only systemd-package artifacts (`ssh_config.d/20-systemd-ssh-proxy.conf`, `sshd_config.d/20-systemd-userdb.conf`); openssh is NOT installed (pacman db has only `libssh`/`libssh2`) → no host keys, no key material. **[obs]**

## 2) SDDM / default target — BLOCKER [obs]

- `sddm-0.21.0-7` installed; `/usr/lib/systemd/system/sddm.service` exists; `[Install]` = `Alias=display-manager.service`.
- `/usr/lib/systemd/system/graphical.target` line 14: `Wants=display-manager.service`.
- `systemctl --root=/home/builder/imgroot get-default` → `graphical.target`; `/usr/lib/systemd/system/default.target -> graphical.target`. Default target is fine.
- **No `/etc/systemd/system/display-manager.service` symlink exists anywhere; `is-enabled sddm` → `disabled`** → systemd will never start SDDM; a live boot would land on `getty@tty1` (enabled), not Plasma.
- Session wiring is otherwise correct: `/etc/sddm.conf.d/autologin.conf` = `[Autologin] User=live Session=plasma` (37 bytes); `/usr/share/wayland-sessions/plasma.desktop` (Exec=`/usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland`); `/usr/share/xsessions/` empty (no session-name ambiguity); binaries present: `sddm`, `sddm-helper`, `startplasma-wayland`, `startplasma-x11`, `plasmashell`, `kwin_wayland`, `konsole`.
- Recommended fix (NOT applied): `arch-chroot /home/builder/imgroot systemctl enable sddm NetworkManager` — then rebuild squashfs + UKI + re-verify stick (any rootfs change invalidates current hashes).

## 3) NetworkManager — BLOCKER [obs]

- `networkmanager-1.58.1-2` installed, units present, but `is-enabled NetworkManager` → `disabled`; no `multi-user.target.wants/NetworkManager.service`. `/etc/NetworkManager/system-connections` empty (expected for a live image). ⇒ no network in the live session (M1 bar includes wired network).

## 4) `/etc/fstab`, WSL contamination, mounted leftovers — CLEAN [obs]

- `/etc/fstab`: header comments only, zero entries — correct for the archiso-style overlay boot; no 9p/drvfs/host-path traces.
- No WSL markers: no `/etc/wsl.conf`, no `/usr/bin/wslpath|wslvar`, no `/usr/lib/wsl`, no `/init`. `resolv.conf` is the stock 65-byte template file (not a dangling systemd/WSL symlink). Grep hits for "wsl" under `/etc` were only standard ca-certificates bundles (false positives).
- No mounted leftovers: imgroot `proc sys dev run tmp` are empty template dirs; builder shows no mounts under `/home/builder/imgroot`, no loop devices; no `*.mount` units in `/etc/systemd/system` (contents: only `autovt@.service`, `getty.target.wants/`, `multi-user.target.wants/` [remote-fs only], `sockets.target.wants/`).

## 5) Workspace / session files — PASS [obs]

- Plasma Wayland session + xdg autostart (plasmashell, kglobalacceld, powerdevil, polkit-kde agent, …) present; `plasma-dbus-run-session-if-needed` present; `/home/live` has no stale configs.

## 6) Kernel / DT / firmware paths vs DT

- Kernel `linux-cachyos-arm64-7.3.0rc3-1`; modules at `/usr/lib/modules/7.3.0-rc3/` (modules.dep 964 KB; `msm.ko.zst` present). `/boot`: `vmlinuz-linux-cachyos-arm64` (52,492,800 B) + `vmlinuz-cachyos-arm64.efi` (52,853,760 B ≈ Image+stub, no initrd). **No rootfs-local initramfs; `/etc/mkinitcpio.d` empty (no presets)** — acceptable for the planned archiso UKI path (initramfs is in the UKI), but there is no fallback and no preset for kernel updates. [obs]
- DT: `/boot/dtbs/linux-cachyos-arm64/x126100-lenovo-ideapad-slim3.dtb` (207,632 B) is the only DTB; source `.../ksrc/arch/arm64/boot/dts/qcom/x126100-lenovo-ideapad-slim3.dts` (33 KB) present in the build tree. [obs]
- DT firmware references (from DTB strings + DTS): exactly `qcom/x1p42100/LENOVO/83N3/{qcdxkmsucpurwa.mbn (gpu_zap_shader), qcadsp8380.mbn, qccdsp8380.mbn, adsp_dtbs.elf, cdsp_dtbs.elf}` → **all present** in `/usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3/` (10 files staged total; extras: `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`, `qcdxkmsuc8380.mbn`). Loader checks `updates/` first, so the `qcom/...` names resolve here. **DT ↔ staged paths: FULL MATCH.** [obs]
- WiFi: `ath12k/WCN7850` firmware present (`amss.bin`, `board-2.bin`, `m3.bin`). [obs]
- **Residual risk [hyp, needs runtime dmesg]:** the rootfs has **no `/usr/lib/firmware/qcom` directory at all** (linux-firmware split set has no qcom payload), and a tree-wide search found **no `*_sqe*`, `*gmu*`, `*gen70500*` files anywhere**. The msm/Adreno driver requests GPU core firmware under `qcom/` — `adreno_gpu.c` builds names as `kasprintf(GFP_KERNEL, "qcom/%s", fwname)` (lines 140, 544; catalog e.g. `gen70500_sqe.fw` + `gen70500_gmu.bin`, `a740_sqe.fw` + `gmu_gen70200.bin`). None exist → GPU init will likely fail (KWin/Plasma then has no accelerated GL). The DT-named zap shader is staged, but the zap is only part of the GPU firmware set. Check boot logs for `Direct firmware load for qcom/... failed`. (Display/DPU itself is separate from GPU; console may still come up.) [obs = absence; hyp = impact]

## 7) Live-mount chain (squashfs / archiso) — satisfiable [obs]

- archiso hook (builder `mkinitcpio-archiso 73-1`): with `archisolabel=KESTREL_A64` the device resolves via `/dev/disk/by-label/KESTREL_A64` (no search file needed); requires `/arch/aarch64/airootfs.sfs` (or `.erofs`); `airootfs.sha512` self-check runs **only** when `checksum=y` (not set) ⇒ the missing sha512 on the stick is NOT fatal.
- Module inventory: `loop`, `squashfs`, `vfat`, `nls_cp437`, `cdrom` are **built-in** in this kernel (`modules.builtin`); `overlay.ko` and `dm-snapshot.ko` exist as modules and are present in both the rootfs and the live initramfs. Mount chain loop→squashfs→overlay is satisfiable.
- Live initramfs contains `msm.ko` + qcom clk/phy modules (incl. `phy-qcom-edp`) but **no qcom firmware files** (staged fw lives only in the squashfs, available after switch_root).
- UKI cmdline source (builder `/home/builder/uki/live-cmdline`): `archisobasedir=arch archisolabel=KESTREL_A64 cow_spacesize=512M clk_ignore_unused pd_ignore_unused console=tty0 quiet`. Note `quiet` suppresses kernel messages (relevant to interpreting "blank screen" attempts); no `checksum=y`.

## 8) Artifact chain — verified [obs]

- `live-rootfs.squashfs` sha256 `8ade18708a65…ef81` == `D:/CachyOS-ARM64/live-staging/arch/aarch64/airootfs.sfs` == stick-verified `HASH_OK` (write-live-stick.log). Sizes 1,687,019,520 B match. Squashfs superblock created 2026-10-08 13:49 local (after last rootfs edits at 13:47); spot check inside squashfs: `etc/sddm.conf.d/autologin.conf`, `usr/share/wayland-sessions/plasma.desktop`, `home/live` (1000:1000) all present.
- `uki/vmlinuz-live.efi` sha256 `61093676c2de…3176` == staging `EFI/BOOT/BOOTAA64.EFI` == stick `HASH_OK`; size 227,974,144 B (= Image + live-initramfs + stub + DT).
- Stick layout (write-live-stick.ps1/log): MBR, single 16 GiB active FAT32 label `KESTREL_A64`; contains `EFI/BOOT/BOOTAA64.EFI` + `arch/aarch64/airootfs.sfs` (+ `SHA256SUMS`, `notes/capture.sh`, `notes/m1-checklist.md` copied by robocopy /E — harmless clutter on a boot medium).

## 9) Minor issues [obs]

- `/etc/hostname` missing → transient hostname at boot.
- `/etc/vconsole.conf`, `/etc/locale.conf`, `/etc/localtime` all missing → US console keymap, C.UTF-8, UTC.
- `/etc/machine-id` is a 33-byte static ID, mode 444 — not the empty/truncated live form; fine for one device, but stick copies will share an ID.
- `/etc/pacman.conf` retains `Server = file:///srv/cachyos-arm64/aarch64` — dead path in the live env (affects package ops only).
- Build-script cosmetics: duplicate `STEP 3` numbering; `useradd ... 2>/dev/null || true` masks failures; no enable/hostname/locale steps.

## 10) Not inspected (policy) / untouched

- `/etc/shadow`, `/etc/gshadow` contents, any key material — not read.
- No modifications made anywhere: rootfs, squashfs, staging, and media untouched; no files written inside CachyOSBuilder; Windows-side scratch only (helper scripts) + this report.
- EFI/stub/UKI internals and the actual hardware boot failure (blank `-` + restarts ×3) are the parent's audit; this report only covers the interface points (cmdline, artifacts, mount expectations).

---

### Suggested next steps (not applied)

1. In `build-live-rootfs.sh`, after the live-identity step add: `arch-chroot "$ROOT" systemctl enable sddm NetworkManager` (verify `display-manager.service` symlink appears).
2. Decide on qcom GPU firmware: add `linux-firmware` qcom payload (or stage the X1-class `*_sqe.fw`/`*_gmu.bin` from the Windows DriverStore like the other 10 files). Confirm against boot dmesg once the boot chain boots.
3. Optional polish: set `/etc/hostname`, `vconsole.conf`, `locale.conf`, `localtime`; truncate `machine-id` for clone hygiene.
4. Any rootfs change ⇒ rebuild squashfs, rebuild UKI, re-verify hashes, rewrite stick (current hash chain invalidates).
