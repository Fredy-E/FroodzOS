# Phase 1 results — CachyOSBuilder bootstrap (2026-10-08)

All gates: **G0b preliminary PASS, G1 PASS.** Nothing outside `D:\CachyOS-ARM64` + the new `CachyOSBuilder` WSL distro was modified. Kali untouched (verified stopped, `wsl --list --verbose`).

## Task 1.1 — rootfs fetch + verification (PASS)

- TLS anomaly: `os.archlinuxarm.org` serves a cert for `archlinuxarm.org/www` only (SAN gap; Windows schannel rejects). Used official mirror `fl.us.mirror.archlinuxarm.org` over valid TLS.
- `ArchLinuxARM-aarch64-latest.tar.gz` — 829,367,415 bytes
- SHA256 `42a4eeaa038994ffd31fa173256ef2f0ef511358eeb41b9ea1f8626391b9b319`
- GPG: **Good signature** from `Arch Linux ARM Build System <builder@archlinuxarm.org>`, RSA key `68B3537F39A313B3E574D06777193F152BDBE6A6` (fingerprint matches the documented key, design [29]). Verified in isolated keyring `D:\CachyOS-ARM64\keys\verify-gpg`.

## Task 1.2 — WSL import (PASS)

- `wsl --import CachyOSBuilder D:\CachyOS-ARM64\builder … --version 2` → `uname -m = aarch64`.
- Note: `.wslconfig` uses a custom kernel (`C:\wsl-kernel\Image`, running as `6.18.26.3-microsoft-standard-WSL2+`) with `CONFIG_HYPERV_NET=y` — not the cause of the network issue.

## Task 1.3 — configuration (PASS, with fixes)

- `builder` user (uid 1001, wheel), passwordless sudo; default WSL user = builder.
- `MAKEFLAGS="-j4"`; 6 GiB `/swapfile` (total 8 GiB with WSL's 2 GiB).
- Full `pacman -Syu` + `base-devel git debugedit sudo qemu-system-aarch64`:
  - makepkg (pacman) 7.1.0, git 2.56.0, QEMU 11.1.2, sudo OK.

### Network forensics (corporate FortiGate network — worth remembering)

1. First boot had **no eth0**: WSL service was in a stuck state (`wsl --shutdown` → `E_UNEXPECTED` "Catastrophic failure"); a shutdown/restart cycle cleared it and the NIC attached.
2. **WSL DHCP never hands out a lease** on this host and an unmanaged service wipes manual config mid-boot. Fix: `systemd-networkd` is now the authoritative owner of eth0 with static config:
   - `/etc/systemd/network/20-eth0.network`: `Address=192.0.2.12/20`, `Gateway=192.0.2.11`, `DNS=192.0.2.10`.
   - Fragility note: the `172.29.192.0/20` subnet belongs to the WSL vSwitch (`vEthernet (WSL (Hyper-V firewall))` = 192.0.2.11). If Windows ever recreates the switch with a different subnet, edit that one file.
3. DNS: WSL's own tunnel stub `192.0.2.10` answers (Windows resolver forwarding). `systemd-resolved` masked (its stub hijack was broken); static `/etc/resolv.conf` = `192.0.2.10` + `96.45.45.45`. `generateResolvConf=false` + `generateHosts=false` in `/etc/wsl.conf`.
4. Mirrors pinned in `/etc/pacman.d/mirrorlist`: `fl.us` (https), `de3` (https), geo-redirect last (its targets 404'd). `/etc/hosts` also pins fl.us/de3 as DNS-independent backup.
5. Persistence verified: `wsl --terminate` + cold start → user, swap, IP, route, DNS all intact.

## Task 1.4 — G0b ARMv8-A baseline (PASS, preliminary)

- `/etc/makepkg.conf`: `CARCH="aarch64"`, `CFLAGS="-march=armv8-a …"` — explicit ARMv8-A baseline for everything we build.
- `gcc -Q --help=target`: `-march=armv8-a` toolchain default.
- Binaries carry `aeabi_feature_and_bits` BTI/PAC/GCS = 0 (no ARMv8.3+ mandatory features).
- Final confirmation deferred to Task 2.4: `qemu-system-aarch64 -cpu cortex-a53` rootfs boot.

## Task 1.5 — G1 first signed package (PASS)

- Key: ed25519 `Builder <builder@local>` (build key; real ADR-7 offline master key comes in Phase 3).
- Built + signed `cachyos-arm64-hello-0.1.0-1` (aarch64) from `D:\CachyOS-ARM64\pkgs\cachyos-arm64-hello\PKGBUILD`.
- Imported + `pacman-key --lsign` the build key; `LocalFileSigLevel = Required` in pacman.conf.
- `pacman -U` completed with **"checking keyring… checking package integrity…"** and installed; binary runs.

### Deviations from plan (documented, gate-equivalent)

- Task 1.5 uses a self-authored minimal package instead of cloning ALARM's whole PKGBUILDs tree (avoids a large clone; same G1 gate).
- Task 1.4 probe = gcc default + makepkg CFLAGS + feature bits instead of `readelf Tag_CPU_arch` (modern gcc emits feature-bit subsections instead).
- Extra hardening beyond plan: mirrorlist/hosts pinning, resolver masking, networkd static config — all forced by the corporate network.

## Phase 1 state: COMPLETE. Builder ready for Phase 2 (kernel + DT + stubble UKI).
