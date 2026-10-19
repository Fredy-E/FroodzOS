# FroodzOS — progress estimate and future publication

> **Historical record retained.** For the accepted 19 October native desktop milestone and current limits, see [STATUS.md](STATUS.md) and [dt26 native report](dt26-native-desktop-success.md). Earlier pending gates, menu numbers, estimates and publication pauses below describe their original date, not current instructions. The owner requested this source/history upload on 19 October; no firmware-bearing binary release is authorized or included.


Updated 2026-10-18. The user has chosen **FroodzOS** as the public project name. This records a naming decision, not authorization to publish, register accounts/domains, change licenses, or rename working boot components.

## Progress estimate

| Scope | Rough engineering estimate |
|---|---:|
| First usable native Lenovo 83N3 live desktop (original M1) | **About 65%** |
| Full maintainable, public general-ARM64 distribution goal | **About 35%** |

These are subjective milestone-weighted estimates, not measured percentages of code, effort or time remaining. The native interactive text-boot milestone itself has passed. Graphics/Plasma, thermal observation, remaining required input/network checks and confirmed final safe shutdown still block full M1. The public distro goal additionally includes clean build/release inputs, signed packages and repository databases, update/recovery policies, installer work if offered, rights clearance, security maintenance and a broader verified support matrix. A source-only preview can precede a complete OS release.

The explicit judgment-based weights and arithmetic are preserved in `research/evidence/froodzos-publication-20261018/progress-estimate.json`. Reassess when a milestone changes; do not treat these estimates as a release date prediction.

## Can it be published?

**Verdict:** Partially true — an independently branded Linux distribution can be published under its components' licenses; "Linux is open source" is not blanket permission to redistribute everything in this development workspace.

**Evidence:**
- Linux's own documentation identifies the kernel's GPL version 2 licensing and per-file license rules.[1]
- GNU's FAQ says that distributing binaries generally requires distributing complete corresponding source too.[2]
- CachyOS publishes a separate restrictive repository usage policy. Its wording is broader than a simple bandwidth courtesy; do not assume that copying its binary package service into a derivative is approved.[3]

**Confidence:** High on the general licensing/source and infrastructure distinction; unresolved for the redistribution rights of individual vendor firmware files and any not-yet-audited component. No trademark or domain clearance is claimed for FroodzOS.

## Recommended publication path

1. **Establish the FroodzOS identity.** Use original branding and an accurate unofficial status statement, crediting the actual upstream projects and contributors. Later migrate visible names, `os-release`, package names and documentation through a tested candidate. Keep legacy Kestrel logger GUIDs, slot names, capture markers and USB labels compatible until a separately tested migration is authorized. Naming is not hardware support.

2. **Prepare a clean source release first.** Stage only reviewed build scripts, patches, configuration, board profiles and documentation in a fresh publication copy. Preserve third-party notices and licenses; explicitly choose terms for genuinely original code without relicensing inherited code. GitHub's terms distinguish public repository access/fork rights from additional rights granted through an adopted license.[5] Never upload the entire D: workspace, raw native logs, credentials, private signing keys, firmware exports, private backups or existing firmware-bearing images. Exact repository, visibility, license decisions and artifacts still need owner approval.

3. **Provide corresponding source with binary releases.** Preserve the exact source revisions, patches, configuration and required build/install scripts for shipped GPL-covered binaries. Arrange complete, version-matched source availability for bundled upstream packages too; a patch folder or a link to a moving upstream branch is not a complete source release.[1][2] Keep component-specific license texts and notices rather than claiming one new license covers the entire OS.

4. **Keep vendor firmware out until rights are cleared.** The current development image contains Windows-extracted firmware and remains local-only under the project safety rules. Publish only firmware whose redistribution permission has been established. Where needed, document a lawful local extraction/provisioning workflow using the user's own installed OS instead of hosting these blobs. A public image must accurately document whether this preparation is required before the target hardware works.

5. **Operate an independent ARM64 package/update path.** Build and host the project's ARM64 package delta with its own public keyring, signed packages and signed repository databases; keep signing secrets offline/private. Do not point FroodzOS at CachyOS binary mirrors or ship their packages on the assumption that an open-source license authorizes the hosted service. Reuse source only under each component's actual terms, and obtain upstream clarification/permission if any repository-policy conflict remains.[3] A source license, an infrastructure policy and trademark rights are different questions.

6. **Publish an explicitly limited alpha.** A proposed initial label is **FroodzOS 0.1 Alpha — ARM64 / Lenovo 83N3**; it is not an existing release. Ship a reviewed live image, machine-readable checksums and signatures, source bundle/index, licenses/notices, reproducible build instructions and tested boot/recovery documentation. GitHub Releases supports tagged releases, release notes and downloadable binary assets; separate suitable hosting can serve larger images and package repositories.[4] Describe exactly what is tested, experimental or unsupported. Do not advertise universal ARM64 compatibility from one physical laptop. A disk installer is not required for a non-installing live alpha and must not be implied if not implemented.

7. **Expand support and maintenance incrementally.** Add board-specific boot/DT/firmware profiles and real device acceptance. Publish security/support/update policies and a verified hardware matrix. Native desktop success on this Lenovo is separate from general ARM64 compatibility.

## Current boundary

No remote repository, release, domain, upstream contact or public upload was created for this request. No runtime branding, USB payloads, firmware records, partition labels, account configuration or signing keys were modified. The working dt24 fallback retains its legacy Kestrel identifiers.

## Source review record

Primary kernel/GNU licensing documentation and current CachyOS repository policy were checked on 2026-10-18. GitHub Terms of Service and release documentation were also reviewed. A search for evidence against unrestricted derivative redistribution returned the restrictive repository policy and community discussion; the official policy, not forum interpretation, governs the infrastructure recommendation. The local direct GNU HTML fetch failed; GNU FAQ evidence was successfully retrieved through the web extraction tool instead. Extracted pages can omit sections even below the requested size budget, so only recovered literal passages support the citation evidence. No individual firmware license clearance was performed.

## Sources

[1] https://www.kernel.org/doc/html/latest/process/license-rules.html
[2] https://www.gnu.org/licenses/gpl-faq.html
[3] https://wiki.cachyos.org/policy/repository_policy
[4] https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
[5] https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
