# Kernel command line for the FroodzOS ARM64 test stick

Target: Lenovo IdeaPad Slim 3 15Q8X10 (83N3), Snapdragon X1-26-100, kernel 7.3.0-rc3, systemd 262,
Arch Linux ARM live USB. Every entry here is for the **private test stick**. The public image keeps its
normal verbosity unless an entry explicitly adds `fz_record=full` or `fz_debug=...`.

Sources: W1 sections 3, 6, 7.2 and phase 0/2/4/5; W5 sections 5, 6.6 and 7; the repository's
`builder/public-image/make-menu-public.py` and `builder/build-live-uki.sh`.

## 0. Boot-line rules

- The current public menu uses `kestrel_log=1 rd.log=console rd.log=file ... console=tty1 loglevel=4
  panic=0 ...`. Replace `rd.log=console` with `rd.log=kmsg`; keep `rd.log=file`. `rd.log=kmsg` is
  accepted by this initramfs's mkinitcpio and puts initramfs messages into the kernel ring (W1 3.2).
- The current UKI embeds `debug loglevel=7 ignore_loglevel` in its own `.cmdline` (W1 3.2 note,
  7.1). GRUB can add `loglevel=8`, but it **cannot remove** `ignore_loglevel`; the screen will stay
  flooded until a UKI rebuild drops `debug` and `ignore_loglevel` from the embedded baseline. The
  ring buffer is unaffected. Do not add `ignore_loglevel` to GRUB as well.
- Only one `console=` is needed for this test: `console=tty0` (W1's baseline). The private menu's
  `kestrel_console=tty1` is a separate variable and can stay.
- A kernel command line is not a log store. `log_buf_len` only keeps more in RAM until the USB
  reader/journald reads it; it does not itself write to the stick.

## 1. BASE debug additions (owner's test entry)

Append these to the existing test entry, or use them as the new entry's tail. If the entry already has
`rd.log=console`, remove that word and keep one `rd.log=kmsg rd.log=file` pair.

```text
rd.log=kmsg rd.log=file
console=tty0 earlycon=efifb,ram efi=debug
loglevel=8 printk.time=1 printk.devkmsg=on log_buf_len=16M
systemd.log_level=debug systemd.log_target=journal-or-kmsg systemd.log_ratelimit_kmsg=0 systemd.show_status=1
systemd.journald.forward_to_kmsg=1 systemd.journald.max_level_kmsg=debug
udev.log_level=debug rd.udev.log_level=debug
panic=0 efi_pstore.pstore_disable=1
fz_record=full
```

A ready-to-paste `linux` line (keep the image's own `kestrel_log`, archiso and platform words):

```text
linux /EFI/Linux/froodzos-maverick-tp.efi kestrel_log=1 rd.log=kmsg rd.log=file archisobasedir=froodzos archisolabel=KESTREL_A64 copytoram=n cow_spacesize=1G console=tty0 earlycon=efifb,ram efi=debug loglevel=8 printk.time=1 printk.devkmsg=on log_buf_len=16M systemd.log_level=debug systemd.log_target=journal-or-kmsg systemd.log_ratelimit_kmsg=0 systemd.show_status=1 systemd.journald.forward_to_kmsg=1 systemd.journald.max_level_kmsg=debug udev.log_level=debug rd.udev.log_level=debug panic=0 efi_pstore.pstore_disable=1 clk_ignore_unused pd_ignore_unused fz_record=full
```

Why each word, and what it costs:

| Word | Why | Cost / risk |
|---|---|---|
| `log_buf_len=16M` | Ring is 256 KiB (`CONFIG_LOG_BUF_SHIFT=18`); debug output wraps it before the USB reader starts. | 16 MiB RAM, one early allocation; low risk. |
| `printk.devkmsg=on` | Removes the kernel's rate limit on userspace `/dev/kmsg` writes (default `ratelimit`). | A runaway writer can add CPU/ring pressure; no lines are dropped by the ratelimit. |
| `loglevel=8` | Prints every kernel level to the console, including debug. Chosen instead of `ignore_loglevel`. | Slower framebuffer output, timing changes; no extra ring overflow by itself. W5 says never add `ignore_loglevel`. |
| `printk.time=1` | Explicit timestamps; the config already defaults on. | Harmless. |
| `rd.log=kmsg` | Initramfs messages enter the same ring the USB streamer/journald read. | Small duplicate if `rd.log=console` is also present; keep only `file`. |
| `rd.log=file` | Keeps `/run/initramfs/init.log`, used by `02-initramfs-console.log`. | Negligible. |
| `earlycon=efifb,ram efi=debug` | Only output before initramfs: early console on the EFI framebuffer and EFI-stub diagnostics. | Screen only; mapping and visibility on the 83N3 are UNVERIFIED (W1 open question 1/2); could garble. Test one boot. |
| `systemd.log_level=debug` | PID1 debug into journal/kmsg. | 0.5–2 MB/min estimated; timing changes. Test entry only. |
| `systemd.log_target=journal-or-kmsg` | Early PID1 falls back to kmsg; later goes through journal forwarding. | Low; better than forcing kmsg (W1 3.2). |
| `systemd.log_ratelimit_kmsg=0` | Removes systemd's own 5 s / 200-message kmsg limit. | More ring traffic. |
| `systemd.journald.forward_to_kmsg=1` | Userspace journal messages also enter the ring. | More ring traffic. |
| `systemd.journald.max_level_kmsg=debug` | Default is `notice`; without this, forwarded debug is silently dropped. | Required companion to the word above. |
| `udev.log_level=debug rd.udev.log_level=debug` | Device-manager debug in userspace and initramfs. | 1–5 MB/boot estimated; timing. |
| `panic=0` | Keep a panic on screen instead of rebooting. Use a separate pstore entry for warm reset. | No automatic pstore cycle. |
| `efi_pstore.pstore_disable=1` | Keep EFI-variable pstore off; NVRAM writes are a firmware risk. | The module is `efi_pstore`; the old `efi-pstore.` hyphen spelling is UNVERIFIED. Check `/sys/module/efi_pstore/parameters/pstore_disable`. |
| `fz_record=full` | The switch: raises journald/`printk` at runtime, arms the sleep hook, and tells terminal/UI capture workers to record. | Journald restart and debug volume; all other settings apply only with this word. |
| `clk_ignore_unused pd_ignore_unused` | Existing platform words; keep them. | Unused clocks/power domains stay on (power). |

Not in BASE: `initcall_debug`, `rd.debug`, `keep_bootcon`, broad `dyndbg`, `boot_delay`, `oops=panic`,
`hung_task_panic`, `pstore.backend`; those belong to deep-debug or pstore entries.

## 2. DEEP-DEBUG set (separate menu entry only)

Start from BASE, then replace/add:

```text
log_buf_len=64M
earlycon=efifb,ram efi=debug keep_bootcon
initcall_debug rd.debug
dyndbg="file drivers/usb/dwc3/* +p; file drivers/usb/host/* +p; file drivers/phy/qualcomm/* +p; file drivers/interconnect/qcom/* +p; file drivers/remoteproc/* +p; file drivers/soc/qcom/* +p"
dwc3.dyndbg=+p xhci_hcd.dyndbg=+p
```

- `initcall_debug` traces every initcall; `rd.debug` sets `set -x` in the initramfs and implies a
  console logger. Both change timing and can hide the race being studied.
- The single `dyndbg=` query is processed at boot for built-in code. Modules loaded later need the
  per-module words (`dwc3.dyndbg=+p`, `xhci_hcd.dyndbg=+p`; add `mhi.dyndbg=+pm
  qrtr_mhi.dyndbg=+pm` for the Wi-Fi resume test). A bare `dyndbg=` is not re-run for new modules.
- Volume can be hundreds of MB and can still wrap a 64 MiB ring. Use for one diagnostic boot and
  return to BASE. `boot_delay=1000` is only for photographing the screen (10x slowdown).
- Keep `panic=0` here; a panic should remain visible. Use the pstore entry for a warm reset.
- Do not ship this entry, do not make it default.

## 3. pstore / ramoops test entry (disposable stick)

```text
linux /EFI/Linux/froodzos-maverick-tp.efi kestrel_log=1 rd.log=kmsg rd.log=file archisobasedir=froodzos archisolabel=KESTREL_A64 copytoram=n cow_spacesize=1G console=tty0 earlycon=efifb,ram efi=debug loglevel=8 printk.time=1 printk.devkmsg=on log_buf_len=32M systemd.log_level=debug systemd.log_target=journal-or-kmsg systemd.journald.forward_to_kmsg=1 systemd.journald.max_level_kmsg=debug udev.log_level=debug rd.udev.log_level=debug panic=10 oops=panic hung_task_panic=1 printk.always_kmsg_dump=1 pstore.backend=ramoops efi_pstore.pstore_disable=1 clk_ignore_unused pd_ignore_unused
```

This is deliberately aggressive: `oops=panic`, `hung_task_panic=1` and `panic=10` convert an oops or
hang into a warm reset so the kernel can reach `kmsg_dump()`; it can boot-loop. Test only with a
disposable stick and a QEMU run first.

Important limits:

- The current kernel has `CONFIG_PSTORE_RAM=m` and no ramoops reserved-memory node, so this entry
  will **not capture a pre-init dump** until a test kernel/DT rebuild sets `CONFIG_PSTORE_RAM=y` and
  adds the ramoops node (W1 4.4). The entry itself boots; it just has nowhere to store the dump.
- The suggested address `0x91400000` in W1 is UNVERIFIED. A wrong region can corrupt firmware or
  kernel memory. Check `/proc/iomem`, `/sys/kernel/debug/memblock/reserved` and the EFI memory map
  before using it, and keep a rollback UKI.
- `reserve_mem=16M:1M:ramoops ramoops.mem_name=ramoops` is an easier first test, but the address is
  best-effort and not stable across boots; not for production.
- The default pstore `kmsg_bytes` is 10 KiB; raise `CONFIG_PSTORE_DEFAULT_KMSG_BYTES` or mount
  pstore with `kmsg_bytes=4M`, otherwise only the tail is saved.
- ramoops is DRAM: it may survive a warm reset/panic reboot, never a long-press power-off.

## 4. fz_record=full and fz_debug= usage

```text
fz_record=full
```

- `fz-record-on` exits 0 only for this whole word; `fz-record-on --print` prints `full` or `off`.
  Terminal, UI/Android and other capture workers call it instead of parsing `/proc/cmdline`.
- `fz-record-journald.service` (ConditionKernelCommandLine=fz_record=full) writes
  `/run/systemd/journald.conf.d/95-froodzos-record.conf` and restarts journald: `Storage=volatile`,
  `RateLimitIntervalSec=0`, `RateLimitBurst=0`, `MaxLevelStore=debug`, `MaxLevelSyslog=debug`,
  `MaxLevelKMsg=debug`, `ForwardToKMsg=yes`, `RuntimeMaxUse=512M`, `RuntimeKeepFree=128M`,
  `RuntimeMaxFileSize=64M`, `SyncIntervalSec=1s`. The shipped `/etc` drop-in is comments only.
- `fz-record-kernel.service` (same condition) writes `kernel.printk = 8 4 1 7` and
  `kernel.printk_devkmsg = on` at runtime.
- `/usr/lib/systemd/system-sleep/90-fz-record` records suspend state before/after, and does nothing
  when the word is absent. Sleep is still disabled by the dev.9 drop-ins.
- Runtime sysctl cannot change `log_buf_len`, `printk.time`, `earlycon`, `rd.log=`, `ignore_loglevel`,
  `systemd.log_*`, `udev.log_level`, `trace_buf_size`, `panic=`, `pstore.backend` or ramoops memory.
  Add those to the GRUB entry when wanted.
- No `system.conf.d` drop-in is needed or shipped: W1 section 6 is journald policy only, and it is
  applied through the runtime journald drop-in above.

```text
fz_debug=wifi,audio
```

- `fz-debug-boot.service` runs `fz-debug --from-cmdline` once, ordered `Before=NetworkManager.service`,
  only when `fz_debug` is present. Profiles: `wifi`, `audio`, `usbc`, `gpu`, `nvme`, `all`.
- Runtime: `sudo fz-debug on wifi`, `sudo fz-debug on all`, `sudo fz-debug off`, `sudo fz-debug status`.
  `FZ_DEBUG_DRY=1` (or `--dry-run`) prints every intended write and changes nothing.
- `fz-debug` writes only `/sys/kernel/debug/dynamic_debug/control`, tracefs `enable`/`buffer_size_kb`/
  `tracing_on`, and `drm.debug`/`msm.dumpstate`. It refuses the hazardous paths from W5 section 5
  (regmap registers, `/sys/kernel/debug/gpio`, `gpioinfo gpiochip9`, pinctrl pinconf, SoundWire
  unbind/bind/registers, UCSI command writes, remoteproc `state`, `/sys/power/pm_test`, kexec).
- There is no auto-expiry: run `fz-debug off` when the test is done.

## 5. Never add, never do

| Do not add / do | Why |
|---|---|
| `ignore_loglevel` | Redundant with `loglevel=8`, floods the only console, slows and perturbs boot, and cannot be undone at runtime (W5). |
| `tp_printk` | Sends every trace event to the console; floods it. Read tracefs instead. |
| Global `dyndbg=+p` | Enables every `pr_debug` in the kernel; enormous volume and timing change. Scope by file/module. |
| `initcall_debug` on the default entry | 0.1–0.3 MB and 1–5 s, changes probe timing; diagnostic boots only. |
| `fw_devlink=permissive` permanently | Hides missing-supplier bugs and changes probe order; A/B boot only. |
| `pm_async=off` permanently | Serializes device resume and changes the bug being studied; A/B boot only. |
| `pcie_ports=native` | Firmware/service conflict risk (kernel docs); only if ownership is suspected. |
| `pci=earlydump` | x86-only; it does nothing on arm64. |
| `debug` | Sets both kernel and systemd debug; use explicit `systemd.log_*` and `loglevel=8`. It is already embedded in the current UKI. |
| `ath12k.debug_mask=...` | No-op in this kernel: `CONFIG_ATH12K_DEBUG` is not set. Needs a test kernel rebuild. |
| `pstore.backend=efi` / arming efi-pstore | Writes variable-size records to NVRAM in crash context; firmware hang/full-NVRAM risk. Keep `efi_pstore.pstore_disable=1`. |
| Any `kexec` / `fz-kexec-uki --exec` | Project rule: arm64 kexec loses the framebuffer and the session. |
| Reading `/sys/kernel/debug/regmap/*/registers` | Confirmed whole-system hang on X1 (TZ/secure registers). |
| Reading `/sys/kernel/debug/gpio`, running `gpioinfo gpiochip9` | GPIO registers owned by TrustZone; the project already crashed on gpiochip9. |
| Reading pinctrl `pinconf-groups` / `pinmux-pins` / `pinconf-pins` | Same TZ-owned-pin class; treat as unsafe. |
| Unbind/bind SoundWire, or write SoundWire `command`/`go`, UCSI `command`/`message_out` | Audio loss/crash, arbitrary bus commands, PD wedge; project rule. |
| Writing `/sys/class/remoteproc/*/state` or `/sys/power/pm_test` | Stops the ADSP (battery/USB-C/audio) or runs a partial suspend that can hang. |
| `mem=` / an unverified ramoops address | Reserves memory the firmware or kernel may use; corruption/boot failure. |
| `log_buf_len` via `sysctl` | Not a sysctl; allocated at boot only. |

Known benign noise on this platform (do not chase, W5/W8): the QMI DMA fallback in ath12k,
`qcom_pmic_glink ... Failed to create device link ... -517`, `arm-scmi ... opps_by_lvl ... -16`,
`qcom-bwmon: failed to add OPP table`, PCIe "dummy regulator" lines, the `sddm-helper` poweroff
crash, KWin software-rendering errors, `iio-sensor-proxy` stop-timeout failures, and the udev worker
storm that follows an oops.
