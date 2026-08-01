"""
config.py — static data tables for romforge.

All branch names, API levels, GApps info, and org lists live here.
Nothing in this file makes network calls or touches the filesystem.
Update this file when branches go EOL or new versions release.

Verification sources (checked July 2026):
  - AOSP branch model: source.android.com/docs/setup/download
  - LineageOS branches: lineageos.org/Changelog-31, wiki.lineageos.org/faq
  - NikGapps variants: nikgapps.com/build
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AndroidVersion:
    api: int
    aosp_tag: str           # historical pinned tag, still valid for old builds
    lineage_branch: str     # LineageOS branch name
    lineage_eol: bool       # True = no longer officially built by LineageOS
    viability: str          # "good" | "fragile" | "archival"
    note: str


VERSIONS = {
    "4":  AndroidVersion(15,  "android-4.4_r1",       "cm-11.0",       True,  "archival",
          "CyanogenMod era. GCC toolchains from this period don't build on modern Ubuntu without an old container (14.04/16.04)."),
    "5":  AndroidVersion(22,  "android-5.1.1_r38",    "cm-12.1",       True,  "archival",
          "Lollipop, CyanogenMod era. Same toolchain rot as Android 4."),
    "6":  AndroidVersion(23,  "android-6.0.1_r81",    "cm-13.0",       True,  "archival",
          "Last major CyanogenMod branch. Some device trees still exist but expect patching."),
    "7":  AndroidVersion(25,  "android-7.1.2_r39",    "lineage-14.1",  True,  "fragile",
          "First LineageOS-branded branch. EOL — no upstream fixes."),
    "8":  AndroidVersion(27,  "android-8.1.0_r81",    "lineage-15.1",  True,  "fragile",
          "Treble introduced here. EOL upstream."),
    "9":  AndroidVersion(28,  "android-9.0.0_r61",    "lineage-16.0",  True,  "fragile",
          "Last branch where LineageOS in-tree su addon was supported."),
    "10": AndroidVersion(29,  "android-10.0.0_r47",   "lineage-17.1",  True,  "fragile",
          "EOL upstream."),
    "11": AndroidVersion(30,  "android-11.0.0_r48",   "lineage-18.1",  True,  "fragile",
          "EOL 2024-03-05, 52 devices dropped from official LineageOS builds."),
    "12": AndroidVersion(32,  "android-12.1.0_r10",   "lineage-19.1",  True,  "fragile",
          "EOL upstream. GSI/emulator lunch targets split from device targets here."),
    "13": AndroidVersion(33,  "android-13.0.0_r75",   "lineage-20",    True,  "fragile",
          "EOL'd when lineage-23.x became stable."),
    "14": AndroidVersion(34,  "android-14.0.0_r41",   "lineage-21",    False, "good",
          "Still receiving device submissions as of Changelog 31."),
    "15": AndroidVersion(35,  "android-15.0.0_r20",   "lineage-23.2",  False, "good",
          "Current LineageOS stable. Best-supported option."),
}

# For fresh AOSP builds (not LineageOS), Google now recommends a rolling
# branch rather than a pinned tag. Verified: source.android.com/docs/setup/download
AOSP_ROLLING_BRANCH = "android-latest-release"
AOSP_EXTRA_INIT_FLAGS = ["--partial-clone", "--no-use-superproject"]

ARCHS = ["arm64", "armv7", "x86_64", "x86"]

# NikGapps variant → description.
# SourceForge folder: sourceforge.net/projects/nikgapps/files/Releases/Android-{ver}/
# Filename pattern: NikGapps-{variant}-{arch}-{ver}-{date}-signed.zip
# NikGapps has no JSON API; the tool points at the folder and expected pattern.
# Per-app overrides: edit nikgapps.config (PackageName=0/1/2) in the zip.
NIKGAPPS_VARIANTS = {
    "core":  "Play Store + Play Services only. Smallest possible GApps.",
    "basic": "Core + Gmail, Maps, Chrome, Calendar.",
    "omni":  "Basic + most Google apps people expect.",
    "stock": "Closest to a stock Pixel experience.",
    "full":  "Everything NikGapps offers.",
}
NIKGAPPS_SF_BASE = "https://sourceforge.net/projects/nikgapps/files/Releases"

# GApps package families by API range, for older versions where NikGapps
# either doesn't build or only partially supports the arch.
GAPPS_BY_API = [
    # (min_api, max_api, family, homepage, supported_arches)
    (15, 23, "OpenGApps (legacy, mirrors may be offline)",
     "https://opengapps.org", ["armv7", "x86"]),
    (24, 28, "OpenGApps / NikGApps",
     "https://nikgapps.com", ["armv7", "arm64", "x86_64"]),
    (29, 35, "NikGApps / MindTheGapps",
     "https://nikgapps.com", ["arm64", "x86_64"]),
]

# GitHub orgs that host device/vendor/kernel trees.
# Searched in order; results from named orgs are trusted higher than
# general search results.
DEVICE_ORGS = [
    "LineageOS",
    "TheMuppets",       # vendor blobs
    "PixelExperience",
    "crdroidandroid",
]

RECOVERY_ORGS = {
    "twrp":      ["TeamWin"],
    "orangefox": ["OrangeFoxRecovery"],
    "skyhawk":   ["SHRP"],
}

<<<<<<< HEAD
# Magisk — fetched from GitHub releases API.
MAGISK_RELEASES_API = "https://api.github.com/repos/topjohnwu/Magisk/releases/latest"

# Build sanity thresholds.
MIN_DISK_GB  = 150
MIN_RAM_GB   = 16
=======
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
>>>>>>> 7c5254ed76103d9d10fe40261c9f03411338ffd6
