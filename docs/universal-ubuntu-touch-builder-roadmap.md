# Universal Ubuntu Touch ROM Builder — product and engineering roadmap

Updated: 2026-10-24  
Development branch: `feature/desktop-ui`

## Product goal

Build AndroidBuilder into a reusable, evidence-driven Ubuntu Touch porting/build tool that can support **many Android devices over time**, rather than hard-coding a single handset. "Universal" means a shared workflow, common validation/build orchestration, and pluggable device definitions/backends. It does **not** mean every Android device can be automatically supported from ADB properties alone.

A device-specific port still needs compatible kernel sources, device configuration, vendor components, a supported Android/Halium base, and a safe boot/recovery path. Unknown or missing prerequisites must stop the flashable-image workflow and be reported explicitly; the tool must never manufacture device support claims.

## Architecture direction

### 1. Shared platform core

- Device discovery through ADB, with explicit serial selection for multiple devices.
- Read-only device fingerprint collection and normalized device profile.
- Source discovery/indexing for kernel, device tree, vendor tree, firmware, and existing ports.
- Compatibility/evidence engine that separates observed, inferred, externally sourced, and unknown values.
- Host preflight for operating system, disk/RAM, required tools, network and build dependencies.
- Reproducible build orchestration, logs, resumable stages, artifact manifests and hashes.
- Validation of outputs and build metadata; no assertion that an artifact boots until device testing provides evidence.
- Safety gates for unlock/flash actions, exact variant checks, backups, recovery procedure and explicit user confirmation.

### 2. Device profile schema

Each device profile should describe at least:

- manufacturer, marketing model, exact model IDs, codename(s), board/platform, SoC and architecture;
- firmware build fingerprint, Android release/API, vendor security patch, kernel version and source provenance;
- boot chain and partition scheme (A/B status, boot/vendor_boot/init_boot/recovery/dtbo/vbmeta where relevant), image format and verified-boot state;
- source repositories and pinned revisions for kernel, device tree, vendor tree, proprietary blobs and any firmware packages;
- proposed Ubuntu Touch/Halium base and why it is compatible;
- known working peripherals, known limitations, port status, evidence links, last review and reviewer;
- verified installation and recovery instructions for the exact variant.

Missing values must remain unknown. Device-reported properties must not be presented as independent verification.

### 3. Pluggable port/build strategies

Do not assume one build method fits every phone. Implement strategy adapters selected only after the evidence engine identifies a viable path, for example:

- an existing UBports port with documented device-specific build instructions;
- a Halium-based port where compatible sources and integration are available;
- a future explicitly supported alternative strategy if the Ubuntu Touch ecosystem changes.

A strategy must declare its inputs, host dependencies, source revisions, build steps, output artifacts, validation checks and unsupported conditions. Unknown strategy or unsupported base means research-only status, not a generic build attempt.

### 4. Device lifecycle states

Use a conservative progression:

`UNIDENTIFIED → PROFILED → SOURCES_FOUND → COMPATIBILITY_REVIEWED → BUILD_CONFIGURED → BUILT → ARTIFACT_VALIDATED → BOOT_TESTED → HARDWARE_TESTED`

Failures should be explicit and stage-specific. A successful compile is not equivalent to a bootable image; a bootable image is not equivalent to a functional daily-driver port.

### 5. Desktop and CLI workflow

The desktop UI and CLI should share the same core APIs. The user should be able to:

1. discover/select a device or create a profile without connecting a phone;
2. inspect what is known, unknown, conflicting, and required next;
3. run source discovery and host preflight;
4. generate a reproducible build plan;
5. build in a host-side workspace with logs and cancellation;
6. inspect the artifacts and validation report;
7. follow a separately gated, device-specific test/installation procedure only when evidence and recovery checks are sufficient.

## First device: Sony Xperia R1 (G2199)

Previously observed values from the connected handset:

- Product/model/device: `G2199`
- Build fingerprint: `Sony/G2199/G2199:8.0.0/OPR1.170623.032/G2199_USR_S0014_180327_Q:user/release-keys`
- Android: 8.0.0, API 26; security patch 2018-03-05
- ABI list: `arm64-v8a,armeabi-v7a,armeabi`
- Kernel: `3.18.71-perf-g83c241e`, AArch64
- `/proc/cmdline` access was denied; do not infer its contents.
- Partition list was readable but partition names/mount roles are not yet mapped to verified flash targets.
- `ro.boot.slot_suffix` returned `1`; this is not enough on its own to conclude that the device uses modern A/B slots.
- `ro.boot.flash.locked` returned `false`. Preserve the raw value; verify bootloader status using reliable device-specific documentation and a non-destructive bootloader query before any write operation.
- `ro.oem_unlock_supported` returned `false`; do not treat one property as conclusive proof of all unlock possibilities.

This profile is enough to guide source research, not to select a Halium base or authorize flashing.

## Milestones

### M1 — Core universal profile and readiness contract
- Normalize ADB observations into a versioned profile.
- Preserve raw values, source and confidence/provenance for every field.
- Add tests for missing, contradictory, malformed and inaccessible properties.
- Keep device support status independent of build completion.

### M2 — Source discovery
- Search configured public repositories and authoritative port indexes.
- Record candidate URLs, branches/tags/commits and evidence.
- Do not automatically trust a repository because its name contains a codename.
- Provide a human review step before pinning sources.

### M3 — Build-plan generation
- Generate a dry-run plan with prerequisites, commands, estimated disk requirements, outputs and stop conditions.
- Pin source revisions and capture tool versions.
- Do not run destructive or device-connected commands as part of a build.

### M4 — Build executor and artifact validation
- Run approved build steps in an isolated workspace.
- Capture logs, exit codes, checksums, source provenance and artifact metadata.
- Validate format and expected contents; label boot compatibility as unverified until tested.

### M5 — Xperia R1 proof of concept
- Verify exact firmware and find a matching kernel source/configuration and device/vendor trees.
- Establish whether required vendor components can be obtained lawfully.
- Determine a viable Ubuntu Touch/Halium base from evidence.
- If prerequisites cannot be found, report a concrete blocker instead of generating a fake ROM.

### M6 — Controlled device validation
- Document exact-variant unlock, backup and recovery evidence.
- Require explicit user approval before any unlock, flash, erase, or repartition action.
- Stage boot tests and hardware-function checks; record failures and known limitations.

### M7 — Expand device coverage
- Add more devices through profiles and strategies, not device-specific conditionals in the shared core.
- Require a test profile and source/evidence review for every newly supported device.

## Definition of "supported"

A device is not labeled buildable merely because ADB detects it, its chipset is known, a kernel compiles, or an image file exists. Minimum status labels should distinguish:

- `RESEARCH_ONLY`
- `SOURCES_INCOMPLETE`
- `CONFIGURABLE`
- `BUILD_SUCCEEDED`
- `ARTIFACT_VALIDATED`
- `BOOT_VERIFIED`
- `HARDWARE_PARTIALLY_VERIFIED`
- `FUNCTIONAL_PORT`

Each status must have explicit acceptance criteria and evidence. Never imply universal compatibility or recommend flashing when the exact device/variant, installation path, and recovery path have not been verified.
