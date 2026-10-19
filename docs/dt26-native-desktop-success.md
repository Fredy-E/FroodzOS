# dt26 native desktop milestone — 2026-10-19

The owner reported: **“Goal achieved Desktop loaded!”** and proposed running Hermes Agent directly on native Linux. This establishes user-observed desktop pixels; it does not establish keyboard/pointer, networking, persistence, or which of the two recovered boots the observation belongs to.

## Evidence recovered, USB read-only

Archive: `testing/boot-failure/native-dt26-desktop-20261019T051414117233Z/`.

- Both native boot IDs archived independently: `54368727-c22b-4b6c-91b6-428b39dd2cbe` and `7f05d7e0-f801-4316-b55c-8daa08d353c5`.
- 25 original files, 1,015,936 bytes total; every copy hash matched the source before/after. No USB writes, firmware access, filesystem repair or deletion.
- On-device dt26a3 UKI, dt25b/default fallback, dt24 recovery, menu and shared SFS still match the verified handoff bytes.
- Both boots requested graphics and passed the real 20-type CPU/cpuss + DRM preflight: character device `card0`, driver `simple-framebuffer`, connected output `1920x1200`.
- Both accepted the real live user's Wayland session. Journal shows SDDM selecting `plasma.desktop`, `startplasma-wayland`, and KWin using DRM. Xwayland reports software fallback; no accelerated GPU support is claimed.

### Per-boot outcomes

| Boot | Complete valid 20-type samples | Observed CPU range | Cleanup evidence |
|---|---:|---|---|
| `54368727…` | 142 / 142 | 38.5–48.7 C | Deadline reached; private SDDM stopped, owned session absent, tty2 getty active. One redundant terminate-session call returned 1 after the session was already gone. |
| `7f05d7e0…` | 67 / 67 | 36.9–46.3 C | Captured service stopping before the full window; no saved 09 cleanup snapshot. Do not infer a hang or completed cleanup from that absence. |

These captures establish temperature visibility and bounded-run monitoring, not fan/cooling or sustained-load safety. KWin framebuffer/EDID and Xwayland warnings remain recorded; the user's visible desktop observation must not be erased because of nonfatal warning text. Final physical poweroff remains unproven.

The initial collector wrote `user_observed_desktop: true` per boot. That field is too strong: the owner's observation was not uniquely correlated to either boot. `parent-verdict.json` explicitly supersedes only those per-boot pixel attributions; the raw archives and measured results remain unchanged.

## Hermes directly on native Linux

Official platform documentation lists Linux/WSL2 aarch64 and the source installer as supported:
- https://hermes-agent.nousresearch.com/docs/getting-started/platform-support
- https://hermes-agent.nousresearch.com/docs/getting-started/installation

The native CLI is an appropriate next target; **no native Hermes installation has been performed yet**. This chat's tools currently run on Windows, not inside the native boot. Installing into the WSL builder is not a substitute for a native installation.

Two prerequisites remain:
1. **Connectivity.** Both recovered NetworkManager captures enumerate only loopback `lo`. No usable Wi-Fi/Ethernet or Internet connection is proven. A USB Ethernet adapter or phone tethering is a candidate test path, not a promise that an untested adapter works.
2. **Persistent workspace and a suitable session.** The current image uses a volatile 512 MiB live overlay and a hard 180-second graphical diagnostic. A source installation there may run out of space and would not survive reboot. Prepare a separately scoped persistent USB work environment before installing; do not write Windows/internal storage, format the stick, copy Windows credentials, or silently remove the thermal/deadline safeguards.

Owner follow-up confirms **keyboard and external mouse work; the built-in touchpad does not**. Wi-Fi was not usable. A USB-C Ethernet adapter and Android USB-tethering option are available. These are owner observations, not newly logged device tests.

A read-only kernel/SFS check (`native-network-prereqs-20261019T052527331246Z.json`) finds `r8152`, ASIX (`asix`, `ax88179_178a`), `usbnet`, CDC Ethernet/NCM and RNDIS-host modules compiled and present for the exact 7.3.0-rc3 kernel in the frozen live SFS. Python, nmcli, curl, ip, getent, sudo and timeout are present; Git is absent. The earlier prerequisites receipt misclassified the Python symlink as absent by reading its link target instead of its path; the fresh receipt corrects that without changing the old file. Driver presence does not establish adapter-chipset support, link, DHCP, DNS or TLS.

**Next owner-executed test:** connect the USB-C Ethernet adapter to the router with a cable before booting the existing entry 4. Check wired connectivity; Android tethering is the alternative. No kernel/DTB/image change is needed merely to try these already-shipped drivers. This remains the 180-second diagnostic, not an unlimited work session. Hermes is not installed yet; persistent workspace, Internet and its missing Git prerequisite remain required. Keep the native-tested dt26 diagnostic and both text recoveries intact.
