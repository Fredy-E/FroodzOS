# Native dt20: console transcript versus recovered checkpoints

## Scope and provenance

Comparison uses the owner's pasted screen transcript, not inspected image
pixels: `C:/Users/USER/AppData/Local/hermes/composer-pastes/pasted_content_2026-10-17_09-38-05-989_64c367.txt`.
Read-only native firmware export:
`testing/boot-failure/firmware-recovery-20261017T093917639Z/`.
Boot ID: `2e6c8caa-5649-4be1-a007-2cb1268df794`, distinct from the preceding
dt19 ID `c0fede4e-027f-44a3-a71e-3d6814f9b9bd`.

All four recovered records pass the Windows reader and independent Python
CRC32/SHA256 checks. USB UKI/menu still match the dt20 update manifest.
`E:/Logs` exists but contains **zero files**. Recovery performed zero firmware
writes and did not clear any slots. These newly occupied slots will disarm
another firmware capture until separately approved rearming.

## Same failure, different capture channels

| Evidence | Screen transcript | Recovered firmware |
|---|---|---|
| Missing KESTREL_A64 device | Full initramfs error says device did not show up after 30 seconds | Slots 2/3: `label=missing` and `initramfs_boot_device_timeout=seen` |
| Late USB checkpoint | `KESTREL_FW_SAVED slot=2 reason=late-usb` | CRC-valid slot 2, `reason=late-usb`, kernel uptime 20.997 s |
| Final checkpoint | `KESTREL_FW_SAVED slot=3 reason=timeout` | CRC-valid slot 3, `reason=timeout`, kernel uptime 64.010 s |
| Logger completion | `KESTREL_RAM_CAPTURE_STOPPED v2` | Not a full console mirror; the slot is saved before this later status print |
| `sync_state()` tail | Numerous I2C/clock/interconnect pending messages at 19.566270..19.589852 | Deliberately filtered out of the bounded selected-evidence payload |
| USB files | No claim from the screen | Host readback confirms E:/Logs has zero files; persistence here was firmware, not USB |

The visible last timestamp 19.589852 belongs to the last displayed kernel
message, not the later untimestamped logger prints. The recovered slot 3 proves
the logger executed at 64.010 seconds; the screen did not establish a kernel
freeze at 19.589852.

## What persisted beyond the visible screen tail

All three later records say `usb_roots=2 external_usb=0 label=missing`.
`a600000.usb` is bound; a200000/a400000/a800000 remain unbound with deferred
probe messages. Thus the screen and firmware agree on the boot failure, and
native external USB/live-root success has **not** been achieved by dt20.
The emergency `[rootfs ~]#` is not the requested USB-backed Bash shell.

A newly retained warning appears in slot 1:

`qcom_pmic_glink pmic-glink: Failed to create device link (0x180) with supplier a600000.usb for /pmic-glink/connector@0`

The old `failed to initialize pdr` line is absent from these selected snapshots.
Absence in a small filtered payload does not prove the full PDR/Type-C path is
fixed; the new link warning is an investigation lead, not a confirmed root
cause. Similarly, `sync_state() pending` lines alone do not identify the
supplier that blocks the I2C/USB path.

## Result

- Console and firmware are **consistent, not byte-identical logs**.
- Firmware persistence and late capture worked again on real hardware.
- There is no full raw boot log recovered from the USB in this attempt.
- The dt20 packaging-only candidate did not achieve native USB/live-root boot.
- Keep this evidence intact; no additional build, media change or firmware
  deletion is authorized by this comparison request alone.
