# Firmware: what the image does not contain

The FroodzOS development image is **firmware-free for this laptop**. It does not contain the Lenovo 83N3 firmware files that
were extracted from a Windows installation (`qcadsp8380.mbn`, `qccdsp8380.mbn`, `adsp_dtbs.elf`, `*.jsn`, and similar). Those
files carry no redistribution grant. The image does contain the generic firmware that Arch Linux ARM ships in its
`linux-firmware-qcom`, `linux-firmware-atheros` and `linux-firmware-realtek` packages under their own licences
(see `/usr/share/licenses/linux-firmware-*` inside the image).

## What was tested without it (2026-11-11, one laptop)

On the Lenovo 83N3 the firmware-free build booted to the desktop; **Wi-Fi and the touchpad work**. The kernel log of that boot
shows the same hardware bring-up, firmware-load messages and battery/power messages as the earlier boot that did include the vendor
files, so nothing seen so far depends on them. The brightness keys change the on-screen indicator but not the panel brightness.
Battery level and power management were not checked and were not working in the earlier boot either (the battery interface
never attached). Audio, camera, USB-C power delivery, suspend and GPU acceleration are not claimed.

## How to stage your own firmware (optional)

Only from your own Windows installation on the same laptop, and only for your own use:

```
sudo tools/setup-local-firmware.sh --dry-run          # shows what would be copied
sudo tools/setup-local-firmware.sh                    # copies into /usr/lib/firmware/updates/qcom/x1p42100/LENOVO/83N3
```

The script reads the Windows DriverStore read-only and never uploads or redistributes anything. Do not share the copied files.

## Sound from the image (0.1.0-dev.5 and later)

The speakers need the audio DSP restarted with this laptop's own firmware. The image ships the command that does it:

```
sudo fz-sound-setup --dry-run     # shows which files it would copy and from where
sudo fz-sound-setup               # copy, restart the audio DSP and the audio session, report the sound card and sink
```

It copies six files (`qcadsp8380.mbn`, `adsp_dtbs.elf`, `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`) into `/usr/lib/firmware/updates/` in the live system's memory,
from `--source <folder>`, from a folder `FroodzOS-firmware` on the boot stick, or from this machine's own Windows partition (NTFS, mounted read-only; a
BitLocker-encrypted partition cannot be read). Nothing is written to Windows or to the boot stick and nothing leaves the machine; the files vanish at power-off,
so run it again after every boot, or add `fz_sound=1` to the kernel options to run it once automatically 45 seconds after boot. There is also a
"Set up sound (laptop firmware)" launcher in the application menu. Do not share the copied files.
