"""
romforge.config
================
Static + user-editable data tables that drive the rest of the pipeline:

  - ANDROID_VERSIONS   : version -> branch/manifest info, build viability notes
  - GAPPS_CATALOG       : (version range, arch) -> gapps package family
  - ARCHES              : known device architectures and their quirks
  - DEVICE_TREE_ORGS    : GitHub orgs/search templates used to *find* device
                          trees (NOT a hardcoded list of devices -- device
                          trees rot too fast to hardcode, so we search)
  - MAGISK              : where to fetch root patching tooling

Everything here is data on purpose. If a branch goes EOL or a GApps mirror
moves, edit this file -- you should not need to touch pipeline logic.

--------------------------------------------------------------------------
VERIFIED AGAINST SOURCE (checked June 2026, re-check periodically):

- AOSP changed its release model in 2026: source is now published twice a
  year (Q2/Q4) under a trunk-stable model. The documented branch for
  building/contributing is the ROLLING `android-latest-release` branch,
  not a per-version numbered tag. Official command:
    repo init --partial-clone --no-use-superproject \\
        -b android-latest-release -u https://android.googlesource.com/platform/manifest
  Source: https://source.android.com/docs/setup/download
          https://source.android.com/docs/setup/reference/repo
  Numbered historical tags (android-12.1.0_r10 etc.) still exist in the
  git history for older versions and are kept below for that reason, but
  they are NOT the currently-documented path for a fresh AOSP build.

- LineageOS officially maintains builds for only the two most recent
  major versions at any time; older branches go EOL and stop receiving
  even AOSP security backports through official channels. As of the
  "Changelog 31" project update, the current branches are lineage-23.2
  (newly promoted to stable) and lineage-21 (still accepting forks but no
  longer accepting NEW device submissions). Confirmed EOL: lineage-18.1
  (deprecated 2024-03-05, 52 devices dropped that day).
  Source: https://lineageos.org/Changelog-31/
          https://wiki.lineageos.org/faq
          https://endoflife.date/lineageos

- Android 12+ diverged GSI and emulator lunch targets: emulator targets
  are `lineage_sdk_$arch`, GSI targets are `lineage_gsi_$arch`. This tool
  still defaults to a device-specific `lineage_<codename>-userdebug`
  target for real-device builds; the GSI/emulator naming only matters if
  you pass --codename gsi or similar, which is out of scope for the
  per-device flow this tool automates.
  Source: https://lineageos.org/Changelog-31/

Branch names rot. Re-verify against the sources above (or
https://github.com/LineageOS/android/branches) before relying on an
exact tag for anything beyond the last ~2 LineageOS versions, which are
the only ones still officially built.
--------------------------------------------------------------------------
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class VersionInfo:
    api_level: int
    aosp_tag_or_branch: str           # legacy numbered tag, for `repo init -b` on old source
    lineage_branch: Optional[str]      # LineageOS branch, if one still exists/existed
    lineage_eol: bool                  # True if LineageOS no longer officially builds this
    viability: str                     # "good" | "fragile" | "archival-only"
    notes: str


# Android version (marketing major) -> build info.
# "viability" is an honest signal, not a guess at convenience:
#   good            = modern toolchains, active source, reasonably reliable
#   fragile          = builds, but expect manual patching (old deps, EOL repos)
#   archival-only    = source/toolchain largely rotted; treat as a research
#                      exercise, not a "flash this on my phone" task
#
# "lineage_eol=True" means: LineageOS itself no longer produces official
# builds for this branch (per their 2-version support policy). The branch
# ref may still exist in git history and could be buildable manually, but
# expect no further upstream fixes and likely missing newer device support.
ANDROID_VERSIONS: dict[str, VersionInfo] = {
    "4": VersionInfo(15, "android-4.4_r1", "cm-11.0", True, "archival-only",
        "KitKat-era, pre-dates LineageOS (this was CyanogenMod). GCC "
        "toolchains from this era often fail on modern Ubuntu/glibc. Most "
        "device trees for this era are dead. Expect to need an old "
        "Ubuntu 14.04/16.04 container just to get repo sync to finish."),
    "5": VersionInfo(22, "android-5.1.1_r38", "cm-12.1", True, "archival-only",
        "Lollipop, CyanogenMod era. Similar toolchain rot to Android 4. "
        "Treat as research, not a flashable goal."),
    "6": VersionInfo(23, "android-6.0.1_r81", "cm-13.0", True, "archival-only",
        "Marshmallow, last major CyanogenMod branch before the LineageOS "
        "fork. Some community device trees still exist and build with "
        "patching. 32-bit-only devices common here."),
    "7": VersionInfo(25, "android-7.1.2_r39", "lineage-14.1", True, "fragile",
        "Nougat. First LineageOS-branded branch. Long EOL -- no official "
        "builds or upstream fixes; treat any tree as a frozen snapshot."),
    "8": VersionInfo(27, "android-8.1.0_r81", "lineage-15.1", True, "fragile",
        "Oreo. Treble introduced here -- GSIs become an alternative to a "
        "full source build if device trees are unavailable. EOL upstream."),
    "9": VersionInfo(28, "android-9.0.0_r61", "lineage-16.0", True, "fragile",
        "Pie. EOL upstream; was the last branch where LineageOS's in-tree "
        "root addon was supported (later versions push you to Magisk/KernelSU)."),
    "10": VersionInfo(29, "android-10.0.0_r47", "lineage-17.1", True, "fragile",
        "EOL upstream as of LineageOS's 2-version support policy."),
    "11": VersionInfo(30, "android-11.0.0_r48", "lineage-18.1", True, "fragile",
        "Confirmed EOL 2024-03-05 (52 devices dropped that day per the "
        "LineageOS blog). No official builds or backports anymore."),
    "12": VersionInfo(32, "android-12.1.0_r10", "lineage-19.1", True, "fragile",
        "EOL upstream. Also the version where LineageOS split GSI "
        "(lineage_gsi_$arch) and emulator (lineage_sdk_$arch) lunch "
        "targets apart from device-specific targets."),
    "13": VersionInfo(33, "android-13.0.0_r75", "lineage-20", True, "fragile",
        "EOL'd as part of LineageOS's 2-version support policy once 23.x "
        "stabilized, but still has a healthy device tree ecosystem from "
        "its time as a supported branch."),
    "14": VersionInfo(34, "android-14.0.0_r41", "lineage-21", False, "good",
        "Still accepting forked device submissions as of LineageOS "
        "Changelog 31, but no longer accepting brand-new device submissions "
        "directly -- check the wiki for current status before relying on this."),
    "15": VersionInfo(35, "android-15.0.0_r20", "lineage-23.2", False, "good",
        "Current LineageOS stable branch as of Changelog 31. Best-supported "
        "option in this table. Requires the most RAM/disk/build time."),
}

# For a from-scratch AOSP (not LineageOS) build of the *newest* tree, Google
# now documents a single rolling branch rather than per-version tags. Use
# this instead of ANDROID_VERSIONS[...].aosp_tag_or_branch when the user
# wants "latest AOSP", not a pinned historical release.
AOSP_LATEST_BRANCH = "android-latest-release"
AOSP_REPO_INIT_EXTRA_FLAGS = ["--partial-clone", "--no-use-superproject"]

# Architectures we plan for. "primary" arches are what 99% of real devices
# use; "legacy" still shows up on Android 4-7 tablets/budget phones.
ARCHES = {
    "arm64": {"bitness": 64, "family": "arm", "common_for": "9-15", "tier": "primary"},
    "armv7": {"bitness": 32, "family": "arm", "common_for": "4-9", "tier": "primary"},
    "x86_64": {"bitness": 64, "family": "x86", "common_for": "emulators/tablets", "tier": "secondary"},
    "x86": {"bitness": 32, "family": "x86", "common_for": "4-7 emulators/tablets", "tier": "legacy"},
}

# GApps package families by era. URLs are *patterns* / known project home
# pages, not pinned binary links -- direct mirrors die constantly. The
# customizer prints these and lets the person confirm/browse the current
# listing rather than scraping an HTML file index (NikGapps distributes
# via a SourceForge file browser with no JSON API -- see notes below).
GAPPS_CATALOG = [
    # (min_api, max_api, package_family, homepage, arches)
    (15, 23, "OpenGApps (legacy mirror, may be offline)",
        "https://opengapps.org", ["armv7", "x86"]),
    (24, 25, "OpenGApps", "https://opengapps.org", ["armv7", "arm64", "x86", "x86_64"]),
    (26, 29, "OpenGApps / NikGApps", "https://nikgapps.com", ["armv7", "arm64", "x86_64"]),
    (30, 35, "MindTheGapps / NikGApps", "https://github.com/MindTheGapps", ["arm64", "x86_64"]),
]

# NikGapps variants -- verified against nikgapps.com/build docs and the
# nikgapps.config format (PackageName=0/1/2 per-app overrides build on top
# of one of these as a starting point). Picking a variant here just
# determines WHICH SourceForge folder/filename pattern to point at; this
# tool does not scrape or guess a binary URL, since NikGapps ships via a
# SourceForge file browser with no stable JSON API. Per-app overrides
# (editing nikgapps.config / PackageName=0/1/2) are a manual step the
# README documents -- the variant picker is the supported entry point here.
NIKGAPPS_VARIANTS = {
    "core": "Minimal -- just enough to run the Play Store.",
    "basic": "Core + a handful of commonly-used Google apps.",
    "omni": "Most Google apps most people want, no extras like Assistant routines.",
    "stock": "Closest to a stock Pixel app set.",
    "full": "Everything NikGapps offers, including less-common apps.",
}
NIKGAPPS_SOURCEFORGE_BASE = "https://sourceforge.net/projects/nikgapps/files/Releases"

# GitHub orgs/users commonly hosting device trees, vendor blobs, and
# kernels. The resolver SEARCHES these (and general GitHub code search)
# rather than assuming any specific repo exists -- device tree availability
# varies wildly by device and rots over time.
DEVICE_TREE_ORGS = [
    "LineageOS",
    "TheMuppets",        # vendor blob dumps, paired with LineageOS trees
    "PixelExperience",
    "crdroidandroid",
    "AOSP-Krypton",
]

# Search query templates. {codename} is substituted at run time.
DEVICE_TREE_SEARCH_TEMPLATES = [
    "device_{vendor}_{codename}",
    "android_device_{vendor}_{codename}",
    "{codename} device tree",
]

# Search query templates specifically for KERNEL trees (separate from
# device trees because kernel repos use different naming conventions and
# a device can have multiple competing community kernel forks worth
# choosing between, unlike the device tree itself which is usually 1:1).
KERNEL_SEARCH_TEMPLATES = [
    "kernel_{vendor}_{codename}",
    "android_kernel_{vendor}_{codename}",
    "{codename} kernel",
]

# Tweak/mod module sources. These are Magisk/KernelSU module REPOSITORIES
# to search -- not a hardcoded list of specific modules, for the same
# reason device trees aren't hardcoded: specific module availability and
# trustworthiness changes constantly. Modules are searched for and
# presented for the person to pick, same pattern as device/kernel trees.
TWEAK_MODULE_ORGS = [
    "Magisk-Modules-Repo",
    "Magisk-Modules-Alt-Repo",
]
TWEAK_SEARCH_TEMPLATES = [
    "{query} magisk module",
]

# init.d support is a LEGACY mechanism, relevant almost entirely to the
# CyanogenMod/early-LineageOS era (Android 4-9ish) -- modern setups use
# Magisk modules instead. The standard method patches init.rc INSIDE THE
# BOOT IMAGE RAMDISK (adds a `sysinit` service running `busybox run-parts
# /system/etc/init.d`), not the system/vendor tree this tool's customizer
# otherwise touches. This is genuinely kernel/device-specific -- some
# kernels need it compiled in -- so this tool documents the standard
# init.rc snippet and creates the /system/etc/init.d directory structure
# in the source tree, but does NOT attempt to blindly patch an arbitrary
# boot image's ramdisk, for the same reason the Magisk root patch step
# doesn't guess magiskboot flags per device.
# Source: multiple corroborating XDA guides for the init.rc snippet below.
INITD_SYSINIT_SERVICE_SNIPPET = (
    "service sysinit /system/bin/logwrapper /system/xbin/busybox run-parts /system/etc/init.d\n"
    "    disabled\n"
    "    oneshot\n"
)
INITD_MAX_USEFUL_API = 25  # Nougat-ish; not meaningful to offer above this

MAGISK = {
    "repo": "topjohnwu/Magisk",
    "release_api": "https://api.github.com/repos/topjohnwu/Magisk/releases/latest",
    "patch_method": "boot_image",  # preferred: patch boot.img post-build, not in-tree su
}

# Custom recovery images. Verified sources as of June 2026.
# TWRP (Team Win Recovery Project) -- largest device coverage, oldest
# Source: https://twrp.me/Devices/
# OrangeFox -- modern UI, active development, good Android 12+ support
# Source: https://orangefox.download/
# SKYHAWK (SHRP) -- feature-rich, also supports A/B devices
# Source: https://skyhawkrecovery.github.io/
# These are fetched as device-specific .img files then flashed via
# `fastboot flash recovery <img>` (older A-only devices) or embedded
# in the ROM zip's vendor_boot partition (A/B devices, Android 10+).
# The tool searches TWRP's device index and GitHub for matching recovery
# images, same search-and-pick pattern as device/kernel trees.
RECOVERY_SOURCES = {
    "twrp": {
        "name": "TWRP (Team Win Recovery Project)",
        "device_list_url": "https://twrp.me/Devices/",
        "github_orgs": ["TeamWin"],
        "search_template": "android_device_{vendor}_{codename} TWRP recovery",
    },
    "orangefox": {
        "name": "OrangeFox Recovery",
        "device_list_url": "https://orangefox.download/",
        "github_orgs": ["OrangeFoxRecovery"],
        "search_template": "android_device_{vendor}_{codename} orangefox",
    },
    "skyhawk": {
        "name": "SKYHAWK Recovery (SHRP)",
        "device_list_url": "https://skyhawkrecovery.github.io/",
        "github_orgs": ["SHRP"],
        "search_template": "android_device_{vendor}_{codename} shrp recovery",
    },
}

# Radio/modem firmware. This is COMPLETELY SEPARATE from the ROM build --
# it lives in its own partition (radio/modem) and is shipped by the
# carrier/OEM, not compiled from AOSP source. It is typically flashed as
# a separate .img or included in a full OTA package. This tool does NOT
# attempt to manage radio images (wrong partition, wrong tooling), but
# surfaces this information so the person isn't surprised when they
# discover their build has no baseband.
# Source: XDA University "Building Your Own Android ROM" (2013, still
# accurate for the partition/firmware model).
RADIO_NOTES = (
    "Radio (baseband/modem) firmware is NOT part of the ROM build. "
    "It lives in its own partition, is shipped by carrier/OEM, and must "
    "be flashed separately as a .img or extracted from a stock OTA. "
    "Without a matching radio image your device will have no cellular, "
    "GPS, or Wi-Fi. Source your device's radio from the stock firmware "
    "for your carrier/region -- DO NOT mix radio images across carriers "
    "or regions, as incompatible radio images can cause permanent damage."
)

# SELinux: surfaced as a build-step concern because SELinux denials are
# one of the most common causes of a 'build succeeds, device bootloops or
# crashes certain apps' outcome on custom ROMs. Setting SELinux permissive
# is the quick-and-dirty fix XDA posts suggest, but it's a security
# regression. The right fix is to add allow rules to the device's sepolicy
# -- the build system has audit2allow integration to help with this.
# The tool warns when a user picks an archival/fragile version since those
# are most likely to have incomplete sepolicy for a modern base.
SELINUX_NOTES = (
    "SELinux policy mismatches are a common cause of 'builds but won't "
    "boot or has broken apps'. Avoid setting SELinux=permissive in "
    "production builds (security regression). Use `adb logcat | grep "
    "avc` to find denials, then add allow rules to the device's sepolicy "
    "directory and rebuild. The build system's audit2allow can generate "
    "draft rules from a denial log."
)

# Boot animation: a .zip file placed at /system/media/bootanimation.zip.
# Structure is: desc.txt (dimensions/framerate) + part0/, part1/ etc.
# subdirectories containing PNG frames. This tool's customizer can stage
# a user-provided bootanimation.zip to that path before build -- no
# special compilation needed, just a correctly-structured zip.
BOOT_ANIMATION_PATH = "system/media/bootanimation.zip"

# Disk/RAM sanity thresholds the tool checks before attempting a build.
MIN_FREE_DISK_GB = 150
MIN_RAM_GB = 16
