# dt25-guard-v2 simpledrm sysfs driver note (synthetic audit, no native claim)

Pinned kernel source: `/home/builder/src/linux_ms_dev_kit-3f0d8691afa098ba378d7d5a3968f03219887719`
(source pin `3f0d8691afa098ba378d7d5a3968f03219887719`; `ksrc` is a Linux symlink
inaccessible via Windows UNC, so the real tree path above was used from WSL).

- `drivers/gpu/drm/sysfb/simpledrm.c:37`: `#define DRIVER_NAME "simpledrm"`
- `drivers/gpu/drm/sysfb/simpledrm.c:893`: `.name = DRIVER_NAME` (DRM driver name `simpledrm`)
- `drivers/gpu/drm/sysfb/simpledrm.c:959-961`: `static struct platform_driver simpledrm_platform_driver`
  with `.name = "simple-framebuffer"` (connects to sysfb)
- `include/drm/drm_ioctl.h:72`: `#define DRM_MAJOR 226`

Guard policy kept: `DRIVERS = {'simple-framebuffer', 'simpledrm'}` accepts either
sysfs `device/driver` symlink target name, since the platform binding reports
`simple-framebuffer` while the DRM driver name is `simpledrm`. Both names were
observed in the pinned source above; no other driver is accepted.

DRM device identity: `/sys/class/drm/cardN/dev` (`major:minor`) must match the
`/dev/dri/cardN` node `st_rdev`, and the major must equal `DRM_MAJOR` (226).
Symlinks, regular files, `/dev/null` (1:3), missing/mismatched `dev` files, and
symlink loops all fail closed (`character_device=False`).
