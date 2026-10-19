## 1. Progress percentage

| Goal | My current estimate |
|---|---:|
| First usable live desktop on your Lenovo | **About 65%** |
| Full, maintainable public FroodzOS distribution with general ARM64 support | **About 35%** |

These are **rough engineering estimates**, not measured percentages of code or time remaining. Native interactive text boot is achieved; graphics/Plasma, required peripheral checks, thermals and confirmed safe shutdown still remain. The full distro also needs release infrastructure, updates, licensing and broader hardware validation.

## 2. Publishing as FroodzOS

**FroodzOS is now recorded as the public project name.** Existing Kestrel boot/logger identifiers remain unchanged to protect the working build.

Yes, you can publish your own Linux distribution. But the kernel and bundled components retain their licenses—you cannot apply one new license to everything simply by renaming the OS.[1][2]

The practical route is:

1. **Own branding:** FroodzOS name, original logo, website and accurate upstream credits. Present it as an independent, unofficial distribution. The name is chosen; trademark/domain clearance has not been done.
2. **Clean source repository:** publish reviewed build scripts, kernel patches, configurations and documentation. Preserve licenses/notices and provide the complete corresponding source required for shipped GPL-covered binaries—not only our patches.[2]
3. **Resolve firmware first:** our current development image contains Windows-extracted firmware that has not been cleared for redistribution. **Do not upload the current image.** Ship only approved redistributable firmware, with a local provisioning/extraction workflow where necessary.
4. **Own packages and trust:** independently build/host the ARM64 package delta, with FroodzOS public keys, signed packages and signed repository databases. This avoids relying on CachyOS's restricted binary-repository infrastructure; reusable source still follows each component's actual license.[3]
5. **Release a limited alpha:** a proposed first label is **FroodzOS 0.1 Alpha — ARM64 / Lenovo 83N3**. Publish a reviewed live image with checksums, signatures, matching sources, build instructions, known issues and a hardware-support table. GitHub Releases can distribute tagged releases and downloadable assets.[4]
6. **Expand support gradually:** validate additional ARM64 boards before advertising them. One Lenovo boot does not establish universal ARM64 compatibility.

**We can publish reviewed source before the desktop is finished; public binary images must wait for firmware/license clearance.** I saved the name and publication path locally. Nothing was uploaded or renamed in the working boot files.

## Sources

[1] https://www.kernel.org/doc/html/latest/process/license-rules.html
[2] https://www.gnu.org/licenses/gpl-faq.html
[3] https://wiki.cachyos.org/policy/repository_policy
[4] https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
