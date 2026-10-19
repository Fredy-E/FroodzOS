# Phase 0 control test — status and handoff (2026-10-08)

## Prepared
- `stonking-desktop-arm64+x1e.iso` — 4,645,531,648 bytes, SHA256 `0c4888195c693977ad65c74f5b516d1ce69b5e56e8aacfc7f4eacf3af18b145b` (no upstream checksum published; HTTPS + our recorded hash is the provenance).
- ISO inspected: hybrid GPT (dd-bootable), `EFI\BOOT\BOOTAA64.EFI` present, largest file 3.59 GB (< 4 GiB), grub.cfg has **no CDLABEL dependency** and carries the Snapdragon `cutmem`/`arm64.nopauth` workaround, `.disk/casper-uuid-generic` present (label-independent casper boot).
- USB stick (Kingston DataTraveler 3.0, Disk 2): raw sector writes are blocked on this managed host even elevated (endpoint policy; "Access denied" then "Incorrect function" after 3.3 GB). Fallback used: 16 GB FAT32 partition (label `UBUNTU-ARM`) + full ISO file copy. Copy completion + per-file verification running (`copy-complete.out` / `copy-complete.log`).
- `capture.sh` — run this inside the live session to gather evidence.

## Your boot steps (this is the part only you can do)
1. When `USB_READY` is confirmed (ask me; I will have verified every file), eject the stick and plug it into the Lenovo 83N3.
2. Power on and press **F12** for the one-time boot menu. Do NOT change boot order, Secure Boot, or BIOS settings.
3. Choose the USB entry (UEFI: Kingston DataTraveler). You should get GRUB with "Try or Install Ubuntu".
4. Select **Try or Install Ubuntu** (live session; do NOT install — no installer, no internal-disk mounts).
5. Once at the desktop, open a terminal and run:
   `sudo bash /path/to/capture.sh` (copy capture.sh to the stick or run from `D:\` via a second USB)
6. Watch thermals; power off at any sign of fan failure or heat: `systemctl poweroff`.

## Success criteria for this control session (record in this file)
- [ ] GRUB menu appears (HWID message absent or non-fatal)
- [ ] Desktop renders (note: software rendering acceptable for control)
- [ ] Keyboard works; touchpad: yes/no
- [ ] Wi-Fi sees networks (5 GHz too?): yes/no
- [ ] Wired USB network: yes/no
- [ ] Audio + mic: yes/no
- [ ] Battery % visible: yes/no
- [ ] USB storage mounts: yes/no
- [ ] Fan audible / temperatures sane: yes/no
- [ ] Clean shutdown: yes/no

These results feed the firmware-staging list and the M1 acceptance for our own image.
