# Builder and diagnostic source archive

These are recipes and investigation tools from a dedicated ARM64 builder, not
an installer for the host running them. The original workspace conventions are
`/home/builder`, `/mnt/d/CachyOS-ARM64`, and the isolated `CachyOSBuilder` WSL2
distribution. Such absolute paths are historical conventions, not a guarantee
that the scripts are portable or safe to run elsewhere.

- Read [reproducibility boundaries](../reproducibility/README.md) before building.
- The original kernel PKGBUILD packages an already-built tree; its empty
  `source=()` is not a clean from-source recipe.
- `fetch-sources.sh` historically resolves a moving branch head. Use the fixed
  accepted pins in the reproducibility document for auditing this snapshot.
- `net-*.sh` / `setup-1.3b.sh` are retired site-network reproducers. Their public
  copies redact site addresses to documentation values and refuse by default;
  they are not working current setup instructions.
- `build-live-rootfs.sh` is an edited public derivative requiring a new local
  live password before effects. It still provisions an experimental live user,
  passwordless sudo and local-only firmware. It must not be used to claim a
  distributable or secure production image.
- Key-generation/signing recipes do not supply any keys or establish a public
  trusted update service. Keep secrets offline/private; no keys are uploaded.
- `kestrel-efilog-loop.sh` is a retired marker; the bounded checkpoint and USB
  logger sources preserve old compatibility contracts, not permission to write
  firmware. Runtime opt-in and separately reviewed owned-scope controls matter.

The source-only publication did not run these build/network/media/firmware
workflows or change the native-tested USB. Portable integrity checks and selected
controlled fixture tests are the documented verification path.
