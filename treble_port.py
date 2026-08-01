"""
treble_port.py — Treble / non-Treble porting assistant for Android 8+.

Verified against XDA guides and AOSP source (July 2026):

  CRITICAL FACT: You CANNOT enable Treble by setting ro.treble.enabled in
  build.prop. It does nothing. Treble requires a separate /vendor partition
  with OEM-provided HAL implementations compiled against the VNDK. Flipping
  a property flag risks a bootloop or brick.
  Source: xdaforums.com/t/enable-treble-support-for-unsupported-device.4000391

  32-bit armv7 CAN run Android 8+. The Samsung Galaxy Note 4 (armv7, non-
  Treble) successfully ran LineageOS 15.1 (Android 8.1). The key is building
  with PRODUCT_FULL_TREBLE_OVERRIDE := false so vendor blobs stay in
  /system/vendor rather than requiring a separate partition.
  Source: xdaforums.com/t/guide-future-news-and-build-oreo-oreo-go-older-oreo-device.3709936

  BoardConfig.mk flags for 32-bit armv7 (non-Treble) verified against:
  xdaforums.com/t/guide-how-to-make-a-device-tree-for-your-phone.3698419

  Treble enablement (64-bit, existing vendor partition) requires:
  PRODUCT_FULL_TREBLE_OVERRIDE := true + TARGET_COPY_OUT_VENDOR := vendor
  + matching kernel that mounts /vendor as a separate partition.
  Source: android.googlesource.com/platform/build (treble_common_32.mk etc.)

Two modes are generated:

  NON-TREBLE (32-bit armv7 or older 64-bit without vendor partition):
    - Vendor blobs stay in /system/vendor (symlinked at build time)
    - PRODUCT_FULL_TREBLE_OVERRIDE := false
    - TARGET_COPY_OUT_VENDOR := system/vendor  (pre-Treble layout)
    - Full set of 32-bit arch flags
    - system.prop properties for 32-bit ART/Dalvik behaviour
    - Known working on: Note 4, Galaxy S3, various MTK armv7 devices

  TREBLE-COMPATIBLE (64-bit, removing broken vendor enforcement):
    - Correct for devices that have a /vendor partition but need VNDK
      version pinning, or where the device tree sets Treble incorrectly
    - PRODUCT_FULL_TREBLE_OVERRIDE := true
    - BOARD_VNDK_VERSION := current
    - TARGET_COPY_OUT_VENDOR := vendor
"""

from pathlib import Path


# ── Known working build.prop / system.prop values ─────────────────────────────
# Sourced from real XDA device trees for armv7 Android 8+ builds.
# Each entry is (property, value, comment).

SYSTEM_PROP_32BIT_NON_TREBLE = [
    # ART / Dalvik — tell the runtime we are 32-bit only
    ("ro.zygote",                       "zygote32",
     "32-bit Zygote only. zygote64_32 or zygote64 will fail on armv7."),
    ("dalvik.vm.isa.arm.variant",       "cortex-a9",
     "Set to your CPU variant: cortex-a7, cortex-a9, cortex-a15, etc."),
    ("dalvik.vm.isa.arm.features",      "default",
     "Leave as default unless you know your CPU extensions (lpae,div)."),
    # Memory / heap — conservative values for older devices
    ("dalvik.vm.heapsize",              "256m",
     "Max heap per app. Reduce if your device has <2GB RAM."),
    ("dalvik.vm.heapstartsize",         "8m",     ""),
    ("dalvik.vm.heapgrowthlimit",       "128m",   ""),
    ("dalvik.vm.heapminfree",           "512k",   ""),
    ("dalvik.vm.heapmaxfree",           "8m",     ""),
    ("dalvik.vm.heaptargetutilization", "0.75",   ""),
    # dex2oat — limit threads on low-core/low-RAM devices
    ("dalvik.vm.dex2oat-threads",       "2",
     "Set to half your core count. More threads = more RAM pressure."),
    ("dalvik.vm.boot-dex2oat-threads",  "4",      ""),
    # Non-Treble: vendor files live in /system/vendor
    ("ro.treble.enabled",               "false",
     "Informational only. Cannot be used to enable Treble — see module header."),
    ("ro.vndk.lite",                    "false",  ""),
    # SF / HWC — older devices typically use HWC 1.x
    ("debug.sf.hw",                     "1",      "Enable HW composer acceleration."),
    ("debug.egl.hw",                    "1",      ""),
    ("persist.sys.ui.hw",               "1",      ""),
    # Audio
    ("af.resampler.quality",            "4",      "Resampler quality 1-8."),
    # Media
    ("media.stagefright.enable-player", "true",   ""),
    ("media.stagefright.enable-meta",   "true",   ""),
    ("media.stagefright.enable-scan",   "true",   ""),
    ("media.stagefright.enable-http",   "true",   ""),
    ("media.stagefright.enable-rtsp",   "true",   ""),
    ("media.stagefright.enable-record", "true",   ""),
]

SYSTEM_PROP_64BIT_TREBLE = [
    ("ro.zygote",                        "zygote64_32",
     "64-bit primary, 32-bit secondary. Needed for 32-bit app compat."),
    ("ro.treble.enabled",                "true",
     "Informational only — Treble requires a real vendor partition, "
     "not just this flag."),
    ("ro.vndk.version",                  "current",
     "VNDK version. Must match BOARD_VNDK_VERSION in BoardConfig.mk."),
    ("ro.vendor.build.security_patch",   "2024-01-01",
     "Update to your vendor's actual security patch date."),
]

# ── BoardConfig.mk blocks ──────────────────────────────────────────────────────

BOARDCONFIG_32BIT_NON_TREBLE = """\
# ── Architecture (32-bit armv7, non-Treble) ───────────────────────────────────
# Verified against XDA device tree guide and Note 4 / Galaxy S3 working builds.
TARGET_BOARD_SUFFIX        := _32
TARGET_ARCH                := arm
TARGET_ARCH_VARIANT        := armv7-a-neon
TARGET_CPU_ABI             := armeabi-v7a
TARGET_CPU_ABI2            := armeabi
TARGET_CPU_VARIANT         := {cpu_variant}
# Replace cortex-a9 with your SoC: cortex-a7, cortex-a9, cortex-a15,
# cortex-a53 (32-bit mode), krait, etc.

# ── Non-Treble: vendor blobs live in /system/vendor ───────────────────────────
# This is the correct layout for all devices that shipped pre-Oreo without
# a dedicated /vendor partition. Do NOT add PRODUCT_FULL_TREBLE_OVERRIDE := true
# unless your device actually has a separate /vendor partition with HAL
# implementations compiled against the VNDK.
PRODUCT_FULL_TREBLE_OVERRIDE := false
TARGET_COPY_OUT_VENDOR     := system/vendor

# ── 32-bit secondary arch: none ───────────────────────────────────────────────
# On a pure 32-bit device there is no secondary arch.
# Remove or comment TARGET_2ND_* completely.

# ── Filesystem ────────────────────────────────────────────────────────────────
TARGET_USERIMAGES_USE_EXT4      := true
BOARD_SYSTEMIMAGE_PARTITION_TYPE := ext4

# ── Kernel ────────────────────────────────────────────────────────────────────
# Your 32-bit kernel must NOT have CONFIG_ARM64 set.
# Verify with: grep CONFIG_ARM64 out/target/product/{codename}/obj/KERNEL_OBJ/.config
TARGET_KERNEL_ARCH         := arm
TARGET_KERNEL_HEADER_ARCH  := arm

# ── Linker namespace (non-Treble) ─────────────────────────────────────────────
# Non-Treble devices use the legacy flat namespace. Setting this avoids
# "dlopen failed: library not found" errors from the Treble namespace enforcer.
PRODUCT_TREBLE_LINKER_NAMESPACES := false
"""

BOARDCONFIG_64BIT_TREBLE = """\
# ── Architecture (64-bit arm64, Treble-compatible) ────────────────────────────
TARGET_ARCH                := arm64
TARGET_ARCH_VARIANT        := armv8-a
TARGET_CPU_ABI             := arm64-v8a
TARGET_CPU_VARIANT         := {cpu_variant}

# 32-bit secondary for app compatibility
TARGET_2ND_ARCH            := arm
TARGET_2ND_ARCH_VARIANT    := armv8-a
TARGET_2ND_CPU_ABI         := armeabi-v7a
TARGET_2ND_CPU_ABI2        := armeabi
TARGET_2ND_CPU_VARIANT     := {cpu_variant}

# ── Treble: separate /vendor partition required ────────────────────────────────
# Your device MUST have a real /vendor partition (check fstab).
# If it does not, use the non-Treble BoardConfig instead.
PRODUCT_FULL_TREBLE_OVERRIDE := true
TARGET_COPY_OUT_VENDOR     := vendor
BOARD_VNDK_VERSION         := current

# ── Filesystem ────────────────────────────────────────────────────────────────
TARGET_USERIMAGES_USE_EXT4       := true
BOARD_SYSTEMIMAGE_PARTITION_TYPE := ext4
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4

# ── Linker namespace (Treble) ─────────────────────────────────────────────────
PRODUCT_TREBLE_LINKER_NAMESPACES := true
"""

# ── Product makefile additions ─────────────────────────────────────────────────

PRODUCT_MK_NON_TREBLE = """\
# Non-Treble product flags
PRODUCT_FULL_TREBLE_OVERRIDE := false

# 32-bit only — no 64-bit native bridge
PRODUCT_PROPERTY_OVERRIDES += \\
    ro.zygote=zygote32

# Inform the build system this is a 32-bit-only product
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_32.mk)
"""

PRODUCT_MK_TREBLE = """\
# Treble product flags
PRODUCT_FULL_TREBLE_OVERRIDE := true
PRODUCT_SHIPPING_API_LEVEL   := {api_level}

# VNDK
PRODUCT_EXTRA_VNDK_VERSIONS  := {api_level}

$(call inherit-product, $(SRC_TARGET_DIR)/product/handheld_system.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/telephony_system.mk)
"""


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_port_files(
    workdir: Path,
    codename: str,
    vendor: str,
    arch: str,           # "armv7" | "arm64"
    treble: bool,        # True = Treble-compatible, False = non-Treble
    cpu_variant: str,    # e.g. "cortex-a9", "cortex-a53", "kryo"
    android_api: int,    # e.g. 27 for Android 8.1
    dry_run: bool = False,
) -> dict[str, str]:
    """
    Generate BoardConfig.mk additions, system.prop, and device makefile
    fragments for porting Android 8+ to a device.

    Returns a dict of {filename: content} — files that should be merged
    into the device tree. Writes them to workdir/treble_port/ unless
    dry_run=True (in which case they're only returned, not written).

    The caller (romforge.py) is responsible for telling the user which
    lines to add to their actual device tree files, since the full device
    tree context is not available here.
    """
    out = {}

    if arch == "armv7" and treble:
        print(
            "\n  ⚠ armv7 + Treble requested. This combination is extremely rare\n"
            "  and only works if your device physically has a separate /vendor\n"
            "  partition AND you have HAL implementations compiled against VNDK.\n"
            "  For most 32-bit devices, non-Treble is the correct choice.\n"
            "  Generating Treble config anyway as requested.\n"
        )

    # 1. BoardConfig.mk additions
    if not treble:
        board = BOARDCONFIG_32BIT_NON_TREBLE.format(
            cpu_variant=cpu_variant, codename=codename)
    else:
        board = BOARDCONFIG_64BIT_TREBLE.format(cpu_variant=cpu_variant)
    out["BoardConfig_additions.mk"] = board

    # 2. system.prop
    props = SYSTEM_PROP_32BIT_NON_TREBLE if not treble else SYSTEM_PROP_64BIT_TREBLE
    lines = [f"# system.prop — generated by romforge treble_port for {codename}\n",
             f"# {'Non-Treble' if not treble else 'Treble'} {arch} build\n",
             f"# Android API {android_api}\n\n"]
    for prop, val, comment in props:
        if comment:
            lines.append(f"# {comment}\n")
        lines.append(f"{prop}={val}\n\n")
    out["system.prop"] = "".join(lines)

    # 3. Product makefile fragment
    if not treble:
        out["device_treble.mk"] = PRODUCT_MK_NON_TREBLE
    else:
        out["device_treble.mk"] = PRODUCT_MK_TREBLE.format(api_level=android_api)

    # 4. README with integration instructions
    out["PORTING_README.txt"] = _build_readme(
        codename, vendor, arch, treble, cpu_variant, android_api)

    if dry_run:
        print(f"\n  [dry-run] would write {len(out)} file(s) to "
              f"{workdir / 'treble_port'}/")
        for fname, content in out.items():
            print(f"    {fname} ({len(content.splitlines())} lines)")
        return out

    out_dir = workdir / "treble_port"
    out_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in out.items():
        (out_dir / fname).write_text(content)
        print(f"  Wrote {out_dir / fname}")

    return out


def _build_readme(codename, vendor, arch, treble, cpu_variant, android_api) -> str:
    mode = "Non-Treble" if not treble else "Treble-compatible"
    return f"""\
romforge treble_port — {mode} {arch} port for {vendor} {codename}
Android API {android_api}
{'='*70}

CRITICAL: read this before touching anything.

{'NON-TREBLE MODE' if not treble else 'TREBLE MODE'}
{'-'*40}
{'Vendor blobs stay in /system/vendor — NO separate vendor partition needed.' if not treble
 else 'Requires a real /vendor partition in your device fstab.'}

WHAT ro.treble.enabled DOES (and does not do)
  Setting ro.treble.enabled=true in build.prop does NOTHING.
  Treble requires actual partition-level implementation.
  Sources: XDA, AOSP build system source.
  Do NOT add it expecting it to enable anything.

HOW TO INTEGRATE THESE FILES
  1. BoardConfig_additions.mk
     Copy the relevant lines into your device's BoardConfig.mk.
     Do NOT replace the whole file — merge the sections.

  2. system.prop
     Either:
     (a) Merge into your existing device/vendor/codename/system.prop, or
     (b) Add to BoardConfig.mk: TARGET_SYSTEM_PROP := $(DEVICE_PATH)/system.prop

  3. device_treble.mk
     Add to your device's main product makefile:
       $(call inherit-product, $(DEVICE_PATH)/device_treble.mk)

  4. CPU variant
     Replace '{cpu_variant}' with your actual SoC CPU core:
       Snapdragon 200/400: cortex-a7
       Snapdragon 600/800: krait
       Snapdragon 808/810: cortex-a57
       Exynos 5 Octa:      cortex-a15
       Exynos 7 (32-bit):  cortex-a53
       MediaTek MT6580:    cortex-a7
     Check your SoC datasheet or kernel defconfig (CONFIG_ARM_CORTEX_*).

{'NON-TREBLE SPECIFIC STEPS' if not treble else 'TREBLE-SPECIFIC STEPS'}
{'-'*40}
{ """
  - Your kernel MUST NOT have CONFIG_ARM64. Verify:
      grep CONFIG_ARM64 out/target/product/{codename}/obj/KERNEL_OBJ/.config
    It must say: # CONFIG_ARM64 is not set

  - Do NOT add a BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE line — there is no
    vendor image in non-Treble builds.

  - If you see linker namespace errors at boot, check that
    PRODUCT_TREBLE_LINKER_NAMESPACES is set to false in BoardConfig.

  - The /system/vendor directory must contain your proprietary blobs.
    Extract them with extract-utils from a stock dump.
""" if not treble else f"""
  - Verify your device has a real /vendor partition:
      adb shell cat /proc/mounts | grep vendor
    If nothing appears, your device does NOT have a vendor partition
    and non-Treble mode is the correct choice.

  - Your kernel must mount /vendor at boot. Check your device fstab for:
      /dev/block/... /vendor ext4 ...

  - BOARD_VNDK_VERSION := current must match PRODUCT_EXTRA_VNDK_VERSIONS.

  - SELinux denials will appear after flashing — use:
      adb logcat | grep avc
    then add allow rules in device/vendor/codename/sepolicy/.
    Do NOT set SELinux permissive in production.
"""}

COMMON BOOTLOOP CAUSES
  - Wrong cpu_variant: causes illegal instruction crashes in native code.
  - ro.zygote=zygote64 on a 32-bit device: instant bootloop.
  - PRODUCT_FULL_TREBLE_OVERRIDE=true without a /vendor partition: bootloop.
  - Missing proprietary blobs in /system/vendor (non-Treble): missing HAL
    errors, usually camera/audio/modem won't work.
  - Dalvik heap too large for available RAM: OOM at boot.

TESTING ORDER
  1. Boot to recovery first — confirms kernel/ramdisk are correct.
  2. Boot system — expect several reboots on first boot (dex2oat).
  3. If bootloop: check /proc/last_kmsg (or adb logcat -b kernel) for
     the last line before reboot.
  4. If "linker: CANNOT LINK EXECUTABLE": a blob is missing or in the
     wrong path. Check /system/vendor/lib vs /vendor/lib.
"""


def detect_treble_status(codename: str) -> dict:
    """
    Try to detect Treble status from a connected ADB device.
    Read-only — never writes to the device.
    Returns a dict with keys: treble_enabled, vndk_version, zygote, arch, vendor_partition
    """
    import shutil, subprocess
    result = {
        "treble_enabled":   None,
        "vndk_version":     None,
        "zygote":           None,
        "arch":             None,
        "vendor_partition": None,
        "error":            None,
    }
    if not shutil.which("adb"):
        result["error"] = "adb not found"
        return result
    def prop(p):
        try:
            r = subprocess.run(["adb", "shell", "getprop", p],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        except Exception:
            return ""
    try:
        subprocess.run(["adb", "start-server"], capture_output=True, timeout=10)
        result["treble_enabled"]   = prop("ro.treble.enabled")
        result["vndk_version"]     = prop("ro.vndk.version")
        result["zygote"]           = prop("ro.zygote")
        result["arch"]             = prop("ro.product.cpu.abi")
        # Check if /vendor is a real separate mount
        mounts = subprocess.run(
            ["adb", "shell", "cat", "/proc/mounts"],
            capture_output=True, text=True, timeout=10).stdout
        result["vendor_partition"] = any(
            "/vendor" in line and "/system/vendor" not in line
            for line in mounts.splitlines()
        )
    except Exception as e:
        result["error"] = str(e)
    return result


def print_treble_status(status: dict) -> None:
    if status.get("error"):
        print(f"  Could not read device status: {status['error']}")
        return
    print(f"  ro.treble.enabled   : {status['treble_enabled']}")
    print(f"  ro.vndk.version     : {status['vndk_version'] or '(not set)'}")
    print(f"  ro.zygote           : {status['zygote']}")
    print(f"  CPU ABI             : {status['arch']}")
    print(f"  /vendor is separate : {'yes' if status['vendor_partition'] else 'NO (system/vendor symlink)'}")
    print()
    if status['treble_enabled'] == 'true' and not status['vendor_partition']:
        print("  ⚠ ro.treble.enabled=true but no separate /vendor partition detected.")
        print("  This device may report Treble support incorrectly.")
    if status['vendor_partition'] and status['treble_enabled'] == 'false':
        print("  ℹ Separate /vendor partition exists but Treble is marked false.")
        print("  Treble builds may work if the vendor HALs are VNDK-compatible.")


CPU_VARIANT_HINTS = {
    # SOC keyword → likely CPU variant
    "snapdragon 200":  "cortex-a7",
    "snapdragon 400":  "cortex-a7",
    "snapdragon 600":  "krait",
    "snapdragon 800":  "krait",
    "snapdragon 808":  "cortex-a57",
    "snapdragon 810":  "cortex-a57",
    "snapdragon 820":  "kryo",
    "exynos 3":        "cortex-a9",
    "exynos 4":        "cortex-a9",
    "exynos 5":        "cortex-a15",
    "exynos 7580":     "cortex-a53",
    "mt6580":          "cortex-a7",
    "mt6592":          "cortex-a7",
    "mt6752":          "cortex-a53",
    "mt6795":          "cortex-a53",
    "helio p":         "cortex-a53",
}

def suggest_cpu_variant(soc_hint: str) -> str:
    """Given a partial SoC name, return the most likely CPU variant string."""
    hint = soc_hint.lower()
    for key, variant in CPU_VARIANT_HINTS.items():
        if key in hint:
            return variant
    return "cortex-a9"   # safe conservative default
