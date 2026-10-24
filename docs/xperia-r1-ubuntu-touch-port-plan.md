# Sony Xperia R1 (G2199) — Ubuntu Touch port investigation

Last reviewed: 2026-10-24  
Working branch: `feature/desktop-ui`  
Status: **Research checkpoint — no device-specific Ubuntu Touch image has been built or tested.**

## Target and known baseline

The target is the **Sony Xperia R1, model G2199**. Do not treat Xperia R1 Plus (G2299) as interchangeable without checking hardware and firmware differences.

The Sony product specification identifies the MSM8937 platform (Snapdragon 430 family), 720 × 1280 display, and Android 7.0 at launch. The previously captured device inspection for the user's handset reported Android 8.0.0 and Linux kernel `3.18.71-perf-g83c241e`. These are separate facts: launch OS specifications do not identify the exact installed firmware or prove which source tree matches the handset.

Official hardware reference: https://www-support-downloads.sonymobile.com/g2299/whitepaper_EN_G2199_G2299.pdf

## Initial findings

- No independently verified, functional Ubuntu Touch port for G2199 is recorded in AndroidBuilder's device catalog.
- Initial public-source searches did not establish a confirmed G2199-specific kernel repository or Android device tree. This is **not proof that no source exists**; source discovery remains open.
- MSM8937-family kernel/device trees from other manufacturers may help with chipset-level understanding, but are not drop-in device trees for the Xperia R1.
- The Android 8.0 userspace reported on this phone and its 3.18.71 kernel require source and compatibility investigation before selecting a Halium base. Do not choose a base solely from the chipset or kernel version.
- Bootloader unlock eligibility is unknown. A reported locked state and the presence/absence of a single Android property are not enough to establish unlockability.
- Do not flash, unlock, repartition, or erase the phone during this investigation.

## Porting components to establish

1. **Exact firmware:** complete build fingerprint, build number, security patch level, product/device identifiers, ABI, and active slot/partition layout where applicable.
2. **Kernel:** matching source revision, defconfig, device tree, kernel command line, modules, and boot image format.
3. **Android device configuration:** device and vendor trees, init configuration, fstab, SELinux policy, proprietary HAL/vendor blobs, and their licensing/source provenance.
4. **Boot/recovery path:** verified bootloader mode access, bootloader unlock eligibility, recovery availability, and a device-specific recovery route.
5. **Ubuntu Touch base:** choose a Halium/Android base only after the firmware and required vendor components are understood. Follow the current UBports porting guide.
6. **Build and validation:** reproducible build, artifact hashes, image/partition compatibility checks, then staged boot and hardware validation before considering installation.

UBports reference: https://docs.ubports.com/en/latest/porting/introduction/Intro.html

## Read-only data collection

Connect only the Xperia R1 to ADB, unlock the screen, accept the USB debugging authorization prompt, and run these commands from a computer with Android Platform Tools installed. These commands query properties and partition metadata; they do not write to the phone.

```bash
adb devices -l
adb -s 1823f425 shell getprop ro.product.manufacturer
adb -s 1823f425 shell getprop ro.product.model
adb -s 1823f425 shell getprop ro.product.device
adb -s 1823f425 shell getprop ro.product.name
adb -s 1823f425 shell getprop ro.build.fingerprint
adb -s 1823f425 shell getprop ro.build.version.release
adb -s 1823f425 shell getprop ro.build.version.sdk
adb -s 1823f425 shell getprop ro.build.id
adb -s 1823f425 shell getprop ro.build.version.security_patch
adb -s 1823f425 shell getprop ro.product.cpu.abi
adb -s 1823f425 shell getprop ro.product.cpu.abilist
adb -s 1823f425 shell uname -a
adb -s 1823f425 shell cat /proc/cmdline
adb -s 1823f425 shell cat /proc/partitions
adb -s 1823f425 shell getprop ro.boot.slot_suffix
adb -s 1823f425 shell getprop ro.boot.verifiedbootstate
adb -s 1823f425 shell getprop ro.boot.flash.locked
adb -s 1823f425 shell getprop ro.oem_unlock_supported
```

The serial above is the previously observed serial for this handset; verify it using `adb devices -l` and replace it if it differs. Redact serials and other identifiers before sharing logs publicly. Some commands may return blank values or permission errors; retain those results as unknown rather than guessing.

## Next acceptance gates

- [ ] Capture and review the exact firmware fingerprint and read-only device metadata.
- [ ] Locate and verify a kernel source matching G2199 and its installed firmware.
- [ ] Locate device-specific configuration and compatible vendor components.
- [ ] Confirm the official bootloader-unlock status/procedure for this exact variant without changing device state.
- [ ] Select and document a viable Halium/Ubuntu Touch base with evidence.
- [ ] Build a first image in a host-side workspace.
- [ ] Validate image format, kernel/DTB compatibility, partition assumptions, and recovery plan before any flash attempt.
- [ ] Only then plan controlled boot testing, with the user explicitly approving any device-modifying step.

## Current decision

**Proceed with source/firmware discovery and read-only collection. Do not generate a flashable image or claim port readiness yet.**
