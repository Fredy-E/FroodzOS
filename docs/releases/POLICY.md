# FroodzOS release and support policy

## Authority and version namespaces

`CODENAMES.md` is the owner's selected naming authority, not release approval.
All25 pairings remain selected, including **1.0 Sherman** and **1.5 Super Sherman**.
No 4.1+ codename is assigned. Scope recommendations in `ROADMAP.md` are not
owner-promised features or dates. `release/current.json` is development identity,
not an admission receipt, build manifest or physical-delivery grant.

- Product: `0.1.0-dev`, Maverick; advancement follows demonstrated OS progress.
- Component: Hermes setup `1.1.2`, workspace v2, packager v2/v3; these do not mean
  product Mustang, Abrams or Blackbird.
- Fixture/review: R5/R2; these are evidence revisions, not OS versions.
- Board/build identifiers and legacy boot/persistence generation strings remain
  independent. Preserve their exact bytes until a separately tested migration.
- A patch retains its series codename: product `1.0.1` is Sherman, product
  `1.5.1` is Super Sherman. Never parse a component version as a product release.

For a future qualified first alpha, `v0.1.0-alpha.1` is a proposed tag format,
not a created tag. The corresponding intended display is exactly
**FroodzOS 0.1 Maverick — ARM64 Alpha**. The current dev target is not silently
promoted to that prerelease. More tests, helper edits or successful copying do
not advance the OS version. Beta/RC/stable describe evidence-backed release
classes, not elapsed time or aesthetic maturity. Major versions require a
justified approved platform change and migration/recovery qualification.

## Promotion gates

Every proposed release must bind its exact source/config/component/artifact
bytes and explicitly declared support scope. All applicable gates must pass:

1. **Safety/source admission:** original-spec Stage1, then Stage2 only after a
   Stage1 PASS. Implementation/self-review is not independent approval. Source
   approval, inert fixture safety and genuine privileged cleanup are separate.
2. **Native/behavioral qualification:** exact-candidate native boot, usable
   supported input/network workflow, power/thermal limits, final safe shutdown
   and recovery; test results must name their real evidence class and board.
3. **Integration/persistence:** declared persistent features survive the required
   reboot; preserve accepted HOME evidence instead of repeating its challenge.
   Advertising Hermes requires actual bounded privileged lifetime, approved
   source/package/integration and owner-native install/auth/tool acceptance.
   Dropping that scope needs an explicit owner decision, not a silent bypass.
4. **Artifact and supply-chain integrity:** actual artifact formats, cryptographic
   pins, matching sources, provenance, project-controlled authentication and
   an explicitly tested update/recovery path appropriate to the release scope.
5. **Rights/security:** license obligations, upstream repository/branding terms,
   firmware redistribution rights, secret scanning and source-availability
   requirements. Local extracted vendor firmware is not public redistribution
   permission. Do not import upstream binary repos into an image without rights.
6. **Owner authorization:** exact publication/delivery scope and separately
   gated physical target identity. Neither a naming choice nor general
   continuation grants commit/tag/push, media installation or public binaries.

Stop promotion on a failed/unknown gate. Preserve raw rejected/failed outcomes,
source pins and history; do not normalize malformed identifiers, restamp a
changed source into an old approval, backdate records or turn UNKNOWN into PASS.
Root self-expiry is containment, not cleanup proof. Missing identity is unknown.

## Support and delivery

AArch64 is an architecture, not a universal compatibility promise. First stable
means a maintained baseline on **explicitly qualified hardware/configurations**,
with known limitations and maintenance/security/recovery obligations. Each new
board, SoC variant or VM needs independent qualification; shared SoC identity
and green unit fixtures are insufficient.

A future compressed raw live image may be named
`froodzos-0.1.0-alpha.1-maverick-aarch64-lenovo-83n3-live.img.xz` only if that is
its actual content. A source ZIP or EFI executable is not a full disk image.
No such image is built or qualified by these documents. A fresh alpha label
cannot be applied to old binaries without rebuilding/requalifying their exact
identity. Signing a file does not itself establish readiness or redistribution
rights. No release dates are assigned here.
