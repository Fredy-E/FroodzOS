# FroodzOS — Military Release Codenames from 0.1 to 4.0

> **Built for ARM64. Engineered to Conquer.**

**Project:** [FroodzOS](https://github.com/Fredy-E/FroodzOS)  
**Architecture:** ARM64 / AArch64  
**Naming theme:** American military tanks, tank destroyers, armored vehicles, fighters, attack aircraft, helicopters, and legendary aviation call signs  
**Document purpose:** Record the complete **selected** codename sequence for future FroodzOS releases, from `0.1` through `4.0`  
**Status:** **Naming roadmap selected by the project owner** — not a claim that these releases are already available  
**Release dates:** Not assigned

> [!IMPORTANT]
> **All 25 version–codename pairings in this document have been selected for the FroodzOS naming roadmap.** They are not merely suggestions or a reserve list. Actual features, dates, supported devices, build availability, and release readiness must be established independently through engineering and testing. The naming plan does not authorize publishing a release or modifying a working boot environment.

---

## Contents

1. [Official codename roadmap — all 25 releases](#1-official-codename-roadmap--all-25-releases)
2. [Release families and their identities](#2-release-families-and-their-identities)
3. [Individual release profiles](#3-individual-release-profiles)
4. [Official display names](#4-official-display-names)
5. [Versioning, naming, and tagging rules](#5-versioning-naming-and-tagging-rules)
6. [GitHub and Linux release metadata examples](#6-github-and-linux-release-metadata-examples)
7. [Release-management and hardware-compatibility policy](#7-release-management-and-hardware-compatibility-policy)
8. [Complete quick-reference tree](#8-complete-quick-reference-tree)

---

## 1. Official codename roadmap — all 25 releases

**Every entry below is part of the selected future naming sequence.** The stage column describes the *intended* position in the release lifecycle, rather than an independently verified build status.

| Version | **Selected codename** | Military origin / inspiration | Intended release class | Theme |
|:--|:--|:--|:--|:--|
| **0.1** | **Maverick** | American fighter-pilot call-sign tradition | Alpha | The Beginning |
| **0.2** | **Chaffee** | M24 Chaffee light tank | Alpha | The Scout |
| **0.3** | **Hellcat** | M18 Hellcat tank destroyer | Alpha | The Agile Striker |
| **0.4** | **Viper** | F-16 Fighting Falcon's “Viper” nickname | Alpha | The Quick Response |
| **0.5** | **Raptor** | F-22 Raptor fighter aircraft | Beta | The Leap Forward |
| **0.6** | **Pershing** | M26 Pershing tank | Beta | The Heavy Advance |
| **0.7** | **Apache** | AH-64 Apache attack helicopter | Beta | The Precision Platform |
| **0.8** | **Wolverine** | M10 Wolverine tank destroyer | Beta | The Endurance Test |
| **0.9** | **Nighthawk** | F-117 Nighthawk stealth aircraft | Release candidate | The Final Approach |
| **1.0** | **Sherman** | M4 Sherman medium tank | First stable generation | **The Foundation** |
| **1.1** | **Mustang** | P-51 Mustang fighter aircraft | Stable feature release | The Reach |
| **1.2** | **Bulldog** | M41 Walker Bulldog light tank | Stable feature release | The Resilient Core |
| **1.3** | **Corsair** | Vought F4U Corsair fighter aircraft | Stable feature release | The Versatile Wing |
| **1.4** | **Phantom** | F-4 Phantom II fighter aircraft | Stable feature release | The Multirole Evolution |
| **1.5** | **Super Sherman** | Upgraded Sherman tanks in Israeli service; historical “Super Sherman” nickname | **Enhanced stable release** | **The Evolution** |
| **2.0** | **Abrams** | M1 Abrams main battle tank | Second major generation | **The Powerhouse** |
| **2.1** | **Thunderbolt** | A-10 Thunderbolt II attack aircraft | Stable feature release | The Durable Force |
| **2.2** | **Bradley** | M2 Bradley infantry fighting vehicle | Stable feature release | The Integrated Platform |
| **2.3** | **Stryker** | Stryker wheeled armored vehicle family | Stable feature release | The Mobility Upgrade |
| **2.4** | **Paladin** | M109 Paladin self-propelled howitzer | Stable feature release | The Long-Range Vision |
| **3.0** | **Blackbird** | SR-71 Blackbird reconnaissance aircraft | Third major generation | **The Next Frontier** |
| **3.1** | **Spectre** | AC-130 Spectre gunship | Stable feature release | The Deep Capability |
| **3.2** | **Hornet** | F/A-18 Hornet fighter/attack aircraft | Stable feature release | The Versatile Performer |
| **3.3** | **Valkyrie** | XB-70 Valkyrie experimental aircraft | Stable feature release | The Experimental Edge |
| **4.0** | **Banshee** | McDonnell F2H Banshee naval fighter | Fourth major generation | **Beyond the Horizon** |

**Scope:** 9 pre-1.0 releases + 6 in the 1.x family + 5 in the 2.x family + 4 in the 3.x family + 1 in the 4.x family = **25 selected names**. The additional 1.x entry is **1.5 Super Sherman**; no original pairing was removed or renumbered.

### Vehicle-category clarification

Not all inspirations are technically *tanks*: Hellcat and Wolverine are tank destroyers; Bradley is an infantry fighting vehicle; Stryker is a wheeled armored vehicle family; Paladin is self-propelled artillery. Their inclusion is intentional because the FroodzOS identity spans the **broader American military**, not tanks alone. Likewise, Maverick is a call-sign-style name rather than an aircraft model.

---

## 2. Release families and their identities

### The 0.x family — **The Proving Ground**

**Selected range:** `0.1 Maverick` through `0.9 Nighthawk`  
**Intended lifecycle:** Alpha → Beta → release candidate

This is the experimental sequence: early boot and bring-up, progressively broader functionality, validation, and preparation for the first stable generation. The names intentionally alternate between ground forces and aviation to give each milestone a distinct identity. **A version number is not proof that the milestone has passed**; for example, calling a build `0.9 Nighthawk` does not automatically make it release-ready.

### The 1.x family — **The Foundation**

**Selected range:** `1.0 Sherman` through `1.5 Super Sherman`  
**Flagship:** **FroodzOS 1.0 Sherman — ARM64**

Sherman represents the first intended stable generation: practical, maintainable, and built to serve as the base for future improvements. Mustang, Bulldog, Corsair, and Phantom are selected names for subsequent 1.x feature releases. **Super Sherman is the selected 1.5 enhanced stable release**, bridging the foundational Sherman 1.0 generation and the more substantially renewed Abrams 2.0 generation.

This pairing is deliberately historical and symbolic: the original M4 Sherman established a practical foundation, while later Israeli-service Sherman variants were substantially modified. The label “Super Sherman” has been used inconsistently across historical and enthusiast contexts, so the codename is an **inspiration**, not a claim that there was one universally defined Super Sherman model. **The Evolution** expresses an upgraded and more capable 1.x family without implying that particular operating-system features have already been built.

### The 2.x family — **The Powerhouse**

**Selected range:** `2.0 Abrams` through `2.4 Paladin`  
**Flagship:** **FroodzOS 2.0 Abrams — ARM64**

Abrams symbolizes a new major generation with an emphasis on capability and maturity. Thunderbolt, Bradley, Stryker, and Paladin extend the theme toward toughness, integration, mobility, and reach. These are **branding themes**, not promises about speed, benchmarks, security, or hardware support.

### The 3.x family — **The Next Frontier**

**Selected range:** `3.0 Blackbird` through `3.3 Valkyrie`  
**Flagship:** **FroodzOS 3.0 Blackbird — ARM64**

Blackbird evokes advanced engineering, precision, and ambition. Spectre, Hornet, and Valkyrie build on that identity through powerful specialized aircraft, versatile aviation, and experimental design.

### The 4.x family — **Beyond the Horizon**

**Selected release:** `4.0 Banshee`  
**Flagship:** **FroodzOS 4.0 Banshee — ARM64**

Banshee is already selected as the name for the fourth major generation. Future `4.1+` names are **not assigned in this document**; they should be added only after an explicit project naming decision.

---

## 3. Individual release profiles

The following descriptions explain the *symbolic intent* of each selected name. They are **not committed feature lists**.

### Alpha releases — 0.1 to 0.4

#### 0.1 — Maverick
- **Official label:** `FroodzOS 0.1 Maverick — ARM64 Alpha`
- **Origin:** A bold, independent aviation call-sign-style name.
- **Identity:** **The Beginning.** The first experimental release identity: independent, exploratory, and willing to challenge the limits of ARM64 desktop support.
- **Release meaning:** The starting point of the FroodzOS public version story, subject to real-world boot, safety, and hardware testing before distribution.

#### 0.2 — Chaffee
- **Official label:** `FroodzOS 0.2 Chaffee — ARM64 Alpha`
- **Origin:** The American **M24 Chaffee** light tank.
- **Identity:** **The Scout.** Compact, exploratory, and focused on discovering the capabilities and constraints of supported machines.
- **Release meaning:** An early development milestone after Maverick; no specific driver or device functionality is implied by the name.

#### 0.3 — Hellcat
- **Official label:** `FroodzOS 0.3 Hellcat — ARM64 Alpha`
- **Origin:** The American **M18 Hellcat** tank destroyer.
- **Identity:** **The Agile Striker.** Speed, nimbleness, and rapid iteration.
- **Release meaning:** Another experimental step with a name that emphasizes responsiveness rather than a guaranteed performance level.

#### 0.4 — Viper
- **Official label:** `FroodzOS 0.4 Viper — ARM64 Alpha`
- **Origin:** **Viper**, a well-known nickname associated with the F-16 Fighting Falcon.
- **Identity:** **The Quick Response.** Agility and responsiveness under increasingly demanding test conditions.
- **Release meaning:** A selected late-alpha codename, without a fixed launch date or feature promise.

### Beta releases — 0.5 to 0.8

#### 0.5 — Raptor
- **Official label:** `FroodzOS 0.5 Raptor — ARM64 Beta`
- **Origin:** The **F-22 Raptor** fighter aircraft.
- **Identity:** **The Leap Forward.** Precision and the ambition to move from proof-of-concept toward a more cohesive platform.
- **Release meaning:** The first *planned* beta identity; use the Beta label only once a build genuinely satisfies beta criteria.

#### 0.6 — Pershing
- **Official label:** `FroodzOS 0.6 Pershing — ARM64 Beta`
- **Origin:** The American **M26 Pershing** tank.
- **Identity:** **The Heavy Advance.** Greater solidity and a stronger foundation for continued development.
- **Release meaning:** A beta-stage codename representing maturity and robustness as goals, not verified achievements.

#### 0.7 — Apache
- **Official label:** `FroodzOS 0.7 Apache — ARM64 Beta`
- **Origin:** The **AH-64 Apache** attack helicopter.
- **Identity:** **The Precision Platform.** Coordinated systems and deliberate refinement.
- **Release meaning:** A beta-stage name; capabilities and supported hardware must be documented separately.

#### 0.8 — Wolverine
- **Official label:** `FroodzOS 0.8 Wolverine — ARM64 Beta`
- **Origin:** The **M10 Wolverine** tank destroyer.
- **Identity:** **The Endurance Test.** Persistence, hardening, and resilience under testing.
- **Release meaning:** A late-beta naming milestone leading into release-candidate evaluation when ready.

### Release candidate — 0.9

#### 0.9 — Nighthawk
- **Official label:** `FroodzOS 0.9 Nighthawk — ARM64 RC`
- **Origin:** The **F-117 Nighthawk** stealth attack aircraft.
- **Identity:** **The Final Approach.** Careful validation, focused refinement, and disciplined preparation.
- **Release meaning:** Reserved for the intended release-candidate milestone. `RC` is a quality/readiness designation, **not a label to apply solely because the chosen number is 0.9**.

### Sherman generation — 1.0 to 1.5

#### 1.0 — Sherman
- **Official label:** `FroodzOS 1.0 Sherman — ARM64`
- **Origin:** The **M4 Sherman** medium tank.
- **Identity:** **The Foundation.** Practicality, maintainability, and a stable basis for the distribution's development.
- **Release meaning:** **Selected first stable flagship.** It should only be released as Stable after the project's actual acceptance, maintenance, and compatibility requirements are met.

#### 1.1 — Mustang
- **Official label:** `FroodzOS 1.1 Mustang — ARM64`
- **Origin:** The **P-51 Mustang** fighter aircraft.
- **Identity:** **The Reach.** Extending what the Sherman-generation platform can achieve.
- **Release meaning:** A selected 1.x feature-release name, distinct from a `1.0.1` patch to Sherman.

#### 1.2 — Bulldog
- **Official label:** `FroodzOS 1.2 Bulldog — ARM64`
- **Origin:** The **M41 Walker Bulldog** light tank.
- **Identity:** **The Resilient Core.** Reliability, discipline, and confidence in the base system.
- **Release meaning:** A planned 1.x follow-on release, not a guarantee of any specific resilience or test result.

#### 1.3 — Corsair
- **Official label:** `FroodzOS 1.3 Corsair — ARM64`
- **Origin:** The **F4U Corsair** fighter aircraft.
- **Identity:** **The Versatile Wing.** Adaptability and an expanding set of supported use cases.
- **Release meaning:** A selected feature-release identity within the Sherman major-version family.

#### 1.4 — Phantom
- **Official label:** `FroodzOS 1.4 Phantom — ARM64`
- **Origin:** The **F-4 Phantom II** fighter aircraft.
- **Identity:** **The Multirole Evolution.** Flexibility and evolution of the first stable generation.
- **Release meaning:** A selected late-1.x feature-release identity leading toward the enhanced Super Sherman 1.5 milestone.

#### 1.5 — Super Sherman
- **Official label:** `FroodzOS 1.5 Super Sherman — ARM64`
- **Origin:** The historical **“Super Sherman”** nickname, associated with upgraded Sherman tanks in Israeli service. Usage of the term is not perfectly uniform: it has been applied to 76 mm-armed Shermans and, in some modern accounts, more broadly to upgraded M-50/M-51 Shermans. The release name references this **lineage of improvement**, not one uniquely specified tank variant.
- **Identity:** **The Evolution.** Preserve the trusted foundations of Sherman while modernizing and strengthening the first major FroodzOS generation.
- **Position in the roadmap:** The **enhanced stable 1.x milestone** after `1.4 Phantom` and **before** `2.0 Abrams`. It is an additional, independently named release—not a replacement for `1.0 Sherman` or a renamed patch.
- **Symbolic engineering direction:** Consolidation, refinement, reliability, maintenance maturity, and preparation for the architectural leap suggested by the Abrams generation. These are **thematic aspirations**, not promises of delivered functionality, benchmark improvements, or expanded hardware support.
- **Versioning examples:** The initial planned version may be tagged `v1.5.0` once qualified; `v1.5.1` would be a Super Sherman patch and retains the same codename.
- **Release meaning:** A substantial feature/update release in the existing stable generation, with its own release notes, build evidence, compatibility matrix, and validation before public use.

> **Why keep both names?** `Sherman 1.0` is the first stable foundation; `Super Sherman 1.5` is its upgraded evolution. Together they tell a coherent story before `Abrams 2.0` begins the second major generation. Both names and every other selected codename remain in the official roadmap.

### Abrams generation — 2.0 to 2.4

#### 2.0 — Abrams
- **Official label:** `FroodzOS 2.0 Abrams — ARM64`
- **Origin:** The **M1 Abrams** main battle tank.
- **Identity:** **The Powerhouse.** A second major generation associated with strength and mature engineering.
- **Release meaning:** **Selected second-generation flagship**, contingent on the capabilities and testing achieved by that time.

#### 2.1 — Thunderbolt
- **Official label:** `FroodzOS 2.1 Thunderbolt — ARM64`
- **Origin:** The **A-10 Thunderbolt II** attack aircraft.
- **Identity:** **The Durable Force.** Toughness and consistent operation.
- **Release meaning:** A selected follow-on release under the Abrams 2.x family.

#### 2.2 — Bradley
- **Official label:** `FroodzOS 2.2 Bradley — ARM64`
- **Origin:** The **M2 Bradley** infantry fighting vehicle.
- **Identity:** **The Integrated Platform.** Coordination, modularity, and bringing capabilities together.
- **Release meaning:** A future 2.x feature-release identity; Bradley is an IFV, **not** a main battle tank.

#### 2.3 — Stryker
- **Official label:** `FroodzOS 2.3 Stryker — ARM64`
- **Origin:** The American **Stryker** wheeled armored vehicle family.
- **Identity:** **The Mobility Upgrade.** Adaptability across changing environments.
- **Release meaning:** A selected 2.x feature-release codename; it does not itself assert device portability.

#### 2.4 — Paladin
- **Official label:** `FroodzOS 2.4 Paladin — ARM64`
- **Origin:** The **M109 Paladin** self-propelled howitzer family.
- **Identity:** **The Long-Range Vision.** Capability, reach, and planning for what comes next.
- **Release meaning:** The final currently selected Abrams-family codename before Blackbird 3.0.

### Blackbird generation — 3.0 to 3.3

#### 3.0 — Blackbird
- **Official label:** `FroodzOS 3.0 Blackbird — ARM64`
- **Origin:** The **SR-71 Blackbird** high-speed reconnaissance aircraft.
- **Identity:** **The Next Frontier.** Technological ambition, precision, and advanced platform engineering.
- **Release meaning:** **Selected third-generation flagship.** Any future performance claims require measured, published evidence.

#### 3.1 — Spectre
- **Official label:** `FroodzOS 3.1 Spectre — ARM64`
- **Origin:** The **AC-130 Spectre** gunship.
- **Identity:** **The Deep Capability.** Purpose-built sophistication and specialized capability.
- **Release meaning:** A selected post-Blackbird 3.x feature-release codename.

#### 3.2 — Hornet
- **Official label:** `FroodzOS 3.2 Hornet — ARM64`
- **Origin:** The **F/A-18 Hornet** fighter/attack aircraft.
- **Identity:** **The Versatile Performer.** Flexibility and broad capability.
- **Release meaning:** A selected 3.x release identity, independent of any specific performance guarantee.

#### 3.3 — Valkyrie
- **Official label:** `FroodzOS 3.3 Valkyrie — ARM64`
- **Origin:** The **XB-70 Valkyrie** experimental bomber.
- **Identity:** **The Experimental Edge.** Fearless engineering and exploration beyond established boundaries.
- **Release meaning:** The final currently selected 3.x codename before the Banshee 4.0 flagship.

### Banshee generation — 4.0

#### 4.0 — Banshee
- **Official label:** `FroodzOS 4.0 Banshee — ARM64`
- **Origin:** The **F2H Banshee** naval jet fighter.
- **Identity:** **Beyond the Horizon.** A fourth major generation signaling the next chapter of FroodzOS.
- **Release meaning:** **Selected fourth-generation flagship**. The `4.1` and later codenames remain intentionally undecided.

---

## 4. Official display names

Use these strings in release announcements, documentation, GitHub release titles, and branded materials **when the corresponding build is ready to announce**.

```text
FroodzOS 0.1 Maverick — ARM64 Alpha
FroodzOS 0.2 Chaffee — ARM64 Alpha
FroodzOS 0.3 Hellcat — ARM64 Alpha
FroodzOS 0.4 Viper — ARM64 Alpha
FroodzOS 0.5 Raptor — ARM64 Beta
FroodzOS 0.6 Pershing — ARM64 Beta
FroodzOS 0.7 Apache — ARM64 Beta
FroodzOS 0.8 Wolverine — ARM64 Beta
FroodzOS 0.9 Nighthawk — ARM64 RC
FroodzOS 1.0 Sherman — ARM64
FroodzOS 1.1 Mustang — ARM64
FroodzOS 1.2 Bulldog — ARM64
FroodzOS 1.3 Corsair — ARM64
FroodzOS 1.4 Phantom — ARM64
FroodzOS 1.5 Super Sherman — ARM64
FroodzOS 2.0 Abrams — ARM64
FroodzOS 2.1 Thunderbolt — ARM64
FroodzOS 2.2 Bradley — ARM64
FroodzOS 2.3 Stryker — ARM64
FroodzOS 2.4 Paladin — ARM64
FroodzOS 3.0 Blackbird — ARM64
FroodzOS 3.1 Spectre — ARM64
FroodzOS 3.2 Hornet — ARM64
FroodzOS 3.3 Valkyrie — ARM64
FroodzOS 4.0 Banshee — ARM64
```

> **Important:** The intended Alpha/Beta/RC labels in this naming document are part of the roadmap. If the actual engineering lifecycle differs, public-facing release status must be accurate, even while preserving the selected codename–version mapping.

---

## 5. Versioning, naming, and tagging rules

### 5.1 Name format

- **Canonical product capitalization:** Always use `FroodzOS`.
- **Canonical release format:** `FroodzOS <major.minor> <Codename> — ARM64`.
- **Pre-release variant:** Add `Alpha`, `Beta`, or `RC` where applicable, e.g. `FroodzOS 0.1 Maverick — ARM64 Alpha`.
- **Codename capitalization:** Title case in prose (`Sherman`), lowercase in machine-readable tokens (`sherman`).
- **One-to-one assignment:** Every selected `major.minor` version has exactly one corresponding codename in Section 1.
- **Codename preservation:** Don't reuse an assigned codename for an unrelated version, and don't silently replace a selected name.

### 5.2 Release families and patch releases

A named **feature release** and a **patch release** are different:

| Example | Correct codename | Meaning |
|---|---|---|
| `1.0.0` | Sherman | Initial 1.0 feature release |
| `1.0.1` | Sherman | Patch to the 1.0 Sherman release |
| `1.0.2` | Sherman | Another Sherman patch |
| `1.1.0` | Mustang | New 1.1 feature release |
| `1.1.1` | Mustang | Patch to 1.1 Mustang |
| `1.5.0` | Super Sherman | Enhanced stable 1.x feature release |
| `1.5.1` | Super Sherman | Patch to 1.5 Super Sherman |
| `2.0.0` | Abrams | Initial 2.0 feature release |
| `2.0.1` | Abrams | Patch to 2.0 Abrams |
| `3.3.0` | Valkyrie | Initial 3.3 feature release |
| `4.0.0` | Banshee | Initial 4.0 feature release |

**Rule:** A third-number patch change (`X.Y.Z`) keeps the codename of `X.Y`. The next selected codename applies when moving to the next entry in the official roadmap, e.g. `1.0 Sherman` → `1.1 Mustang` → `1.2 Bulldog` → `1.3 Corsair` → `1.4 Phantom` → `1.5 Super Sherman` → `2.0 Abrams`.

### 5.3 Suggested Git tag format

Use ordinary lowercase semantic-style tags. Examples:

```text
v0.1.0-alpha.1  # Maverick early alpha build 1
v0.1.0-alpha.2  # Maverick early alpha build 2
v0.5.0-beta.1   # Raptor first beta build
v0.9.0-rc.1     # Nighthawk first release candidate
v1.0.0          # Sherman stable feature release
v1.0.1          # Sherman patch release
v1.1.0          # Mustang feature release
v1.4.0          # Phantom feature release
v1.5.0          # Super Sherman enhanced stable release
v1.5.1          # Super Sherman patch release
v2.0.0          # Abrams major release
v3.0.0          # Blackbird major release
v4.0.0          # Banshee major release
```

These are **illustrative tag patterns**, not a statement that the tags exist. Do not create a Git tag until it points to the correct, approved release commit.

### 5.4 Intended stages versus actual status

- **Alpha:** Experimental, possibly incomplete, and appropriate only for clearly documented testing environments.
- **Beta:** A broader, testable system whose remaining limitations are explicitly stated.
- **RC:** A candidate for stable release that has entered focused qualification.
- **Stable:** A release that satisfies documented support, safety, maintenance, and acceptance criteria.

**Do not declare a release stable simply because its selected version is `1.0` or higher.** Equally, an internal or source-only milestone must not be advertised as a verified bootable image.

---

## 6. GitHub and Linux release metadata examples

### 6.1 GitHub Release example — Maverick

```text
Release title: FroodzOS 0.1 Maverick — ARM64 Alpha
Git tag:       v0.1.0-alpha.1
Version:       0.1.0-alpha.1
Codename:      Maverick
Architecture:  ARM64 / AArch64
Channel:       Alpha
```

### 6.2 GitHub Release example — Sherman

```text
Release title: FroodzOS 1.0 Sherman — ARM64
Git tag:       v1.0.0
Version:       1.0.0
Codename:      Sherman
Architecture:  ARM64 / AArch64
Channel:       Stable (only after qualification)
```

### 6.3 GitHub Release example — Super Sherman

```text
Release title: FroodzOS 1.5 Super Sherman — ARM64
Git tag:       v1.5.0
Version:       1.5.0
Codename:      Super Sherman
Architecture:  ARM64 / AArch64
Channel:       Enhanced Stable (only after qualification)
Release theme: The Evolution
```

The release title and tag are **reserved naming examples**, not proof of an existing public build or release. A patch would retain the same codename, e.g. `v1.5.1`.

### 6.4 Example `/etc/os-release` — Maverick

The following shows **possible future metadata**. It is *not* a request to edit the live operating system, a current root filesystem, or any boot partition.

```ini
NAME="FroodzOS"
PRETTY_NAME="FroodzOS 0.1 Maverick (ARM64 Alpha)"
VERSION="0.1 (Maverick)"
VERSION_ID="0.1"
VERSION_CODENAME=maverick
ID=froodzos
HOME_URL="https://github.com/Fredy-E/FroodzOS"
```

`ID=froodzos` is a **proposed identifier**, which should be used only after confirming that it is compatible with the actual distribution lineage and tooling. A real `/etc/os-release` may need `ID_LIKE`, `BUILD_ID`, and other fields that correctly reflect the final system rather than branding aspirations.

### 6.5 Suggested image filename structure

```text
froodzos-0.1.0-alpha.1-maverick-aarch64.img.xz
froodzos-1.0.0-sherman-aarch64.img.xz
froodzos-1.5.0-super-sherman-aarch64.img.xz
froodzos-2.0.0-abrams-aarch64.img.xz
froodzos-3.0.0-blackbird-aarch64.img.xz
froodzos-4.0.0-banshee-aarch64.img.xz
```

These are **naming examples only**. Actual release assets must indicate supported boards or devices where necessary; architecture alone does not establish boot compatibility.

---

## 7. Release-management and hardware-compatibility policy

This document governs **codename identity**, not the engineering release gate. Before publicly distributing any named version:

1. **Verify its actual status.** Confirm the boot, device support, installation/live-environment behavior, known limitations, and recovery path against the claimed stage.
2. **Publish a hardware matrix.** ARM64 / AArch64 is an architecture family, not a promise that an image supports every ARM64 laptop, tablet, board, or SoC. A machine-specific build must be described as such.
3. **Use a reviewed release process.** Tags, image artifacts, checksums, release notes, and test records must correspond to the same commit/build.
4. **Check redistribution rights.** Review licenses, corresponding source requirements, trademarks, firmware redistribution, and repository/package hosting permissions before sharing binaries.
5. **Never publish development secrets.** Exclude signing keys, credentials, private backups, firmware extracted without redistribution permission, and sensitive raw logs from release assets.
6. **Maintain changelogs and support notes.** Explain what actually changed, which devices were validated, what remains experimental, and how users can report defects.
7. **Preserve boot and recovery safety.** Changing branding or codenames must not unintentionally rename boot identifiers, slot labels, logging markers, or other operational values that existing workflows depend on.
8. **Keep names stable.** All 25 codenames listed here are selected for their corresponding version numbers. If project circumstances eventually require a change, record it as an explicit, dated project decision rather than silently editing the historical mapping.

> No publication date, public image, package repository, performance claim, general ARM64 support promise, or GitHub Release is created or announced by this document.

---

## 8. Complete quick-reference tree

```text
FroodzOS — Military Release Codenames
│
├── 0.x  THE PROVING GROUND
│   ├── 0.1  Maverick      Alpha    The Beginning
│   ├── 0.2  Chaffee       Alpha    The Scout
│   ├── 0.3  Hellcat       Alpha    The Agile Striker
│   ├── 0.4  Viper         Alpha    The Quick Response
│   ├── 0.5  Raptor        Beta     The Leap Forward
│   ├── 0.6  Pershing      Beta     The Heavy Advance
│   ├── 0.7  Apache        Beta     The Precision Platform
│   ├── 0.8  Wolverine     Beta     The Endurance Test
│   └── 0.9  Nighthawk     RC       The Final Approach
│
├── 1.x  THE FOUNDATION
│   ├── 1.0  SHERMAN       Flagship The Foundation
│   ├── 1.1  Mustang                The Reach
│   ├── 1.2  Bulldog                The Resilient Core
│   ├── 1.3  Corsair                The Versatile Wing
│   ├── 1.4  Phantom                The Multirole Evolution
│   └── 1.5  SUPER SHERMAN  Enhanced The Evolution
│
├── 2.x  THE POWERHOUSE
│   ├── 2.0  ABRAMS        Flagship The Powerhouse
│   ├── 2.1  Thunderbolt            The Durable Force
│   ├── 2.2  Bradley                The Integrated Platform
│   ├── 2.3  Stryker                The Mobility Upgrade
│   └── 2.4  Paladin                The Long-Range Vision
│
├── 3.x  THE NEXT FRONTIER
│   ├── 3.0  BLACKBIRD     Flagship The Next Frontier
│   ├── 3.1  Spectre                The Deep Capability
│   ├── 3.2  Hornet                 The Versatile Performer
│   └── 3.3  Valkyrie               The Experimental Edge
│
└── 4.x  BEYOND THE HORIZON
    └── 4.0  BANSHEE       Flagship Beyond the Horizon
```

### Flagship and enhanced milestone release identities

| Flagship | Official name | Symbolic identity |
|---|---|---|
| Experimental flagship | **FroodzOS 0.1 Maverick — ARM64 Alpha** | The Beginning |
| First stable flagship | **FroodzOS 1.0 Sherman — ARM64** | The Foundation |
| Enhanced 1.x milestone | **FroodzOS 1.5 Super Sherman — ARM64** | The Evolution |
| Second major flagship | **FroodzOS 2.0 Abrams — ARM64** | The Powerhouse |
| Third major flagship | **FroodzOS 3.0 Blackbird — ARM64** | The Next Frontier |
| Fourth major flagship | **FroodzOS 4.0 Banshee — ARM64** | Beyond the Horizon |

---

**FroodzOS** — *Built for ARM64. Engineered to Conquer.*  
**Source project:** https://github.com/Fredy-E/FroodzOS

*Document scope: The complete, selected FroodzOS version/codename naming roadmap from 0.1 through 4.0, now including **1.5 Super Sherman** alongside **1.0 Sherman**. It preserves naming decisions without asserting that a corresponding software release exists.*
