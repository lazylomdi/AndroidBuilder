"""
romforge.customizer
=====================
Optional post-resolve, pre/post-build customization steps:

  - GApps: resolves the right package family for the chosen Android
    version + arch (config.GAPPS_CATALOG), and -- for the API range where
    NikGapps applies -- lets the person pick a VARIANT (core/basic/omni/
    stock/full, see config.NIKGAPPS_VARIANTS) rather than only a package
    family. NikGapps ships via a SourceForge file browser with no stable
    JSON API, so this points at the correct per-version folder URL and
    asks the person to confirm the exact filename rather than scraping
    HTML or guessing a binary link that will rot.

  - Custom apps / wallpapers: copies user-provided APKs and image files
    into the standard product overlay paths
    (vendor/<x>/overlay/... and product/etc/... ) BEFORE the build runs,
    since these need to be compiled into the system image.

  - Tweaks/mods: searches GitHub for Magisk/KernelSU module repos matching
    a free-text query (same search-and-pick pattern as device/kernel
    trees) and stages the chosen module(s) for inclusion, rather than
    bundling a fixed list of specific tweaks that would go stale.

  - init.d support: a LEGACY mechanism (see config.py notes) relevant
    mostly to Android 4-9-era CM/early-Lineage builds. Creates the
    /system/etc/init.d directory structure in the source tree and writes
    out the documented init.rc service snippet as a reference file --
    does NOT blindly patch an arbitrary boot image's ramdisk, since the
    exact patch point is kernel/device-specific.

  - Root: patches the *output* boot.img with Magisk AFTER the build
    completes. This is deliberately done post-build rather than via
    in-tree su addons -- it's far more reliable across Android versions
    and doesn't risk breaking the build for users who don't want root.
"""

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

from config import (GAPPS_CATALOG, MAGISK, NIKGAPPS_VARIANTS,
                     NIKGAPPS_SOURCEFORGE_BASE, INITD_SYSINIT_SERVICE_SNIPPET,
<<<<<<< HEAD
                     INITD_MAX_USEFUL_API, BOOT_ANIMATION_PATH, RADIO_NOTES,
                     SELINUX_NOTES, RECOVERY_SOURCES)
=======
                     INITD_MAX_USEFUL_API)
>>>>>>> 569c9bad1ff47876aa62b79a66e6b46ec3fba4a3


def resolve_gapps(api_level: int, arch: str) -> dict | None:
    for min_api, max_api, family, homepage, arches in GAPPS_CATALOG:
        if min_api <= api_level <= max_api and arch in arches:
            return {"family": family, "homepage": homepage, "arch": arch}
    return None


def nikgapps_folder_url(android_version_marketing: str) -> str:
    """
    Build the SourceForge folder URL for a given marketing Android version
    (e.g. "15" -> .../Releases/Android-15/). Verified real folder structure
    as of June 2026 (see config.py / README sourcing notes) -- NikGapps has
    no JSON API, so this points at the human-browsable folder rather than
    guessing today's exact dated filename, which changes every release.
    """
    return f"{NIKGAPPS_SOURCEFORGE_BASE}/Android-{android_version_marketing}/"


def stage_gapps(workdir: Path, api_level: int, arch: str,
                 android_version_marketing: str | None = None,
                 variant: str | None = None, dry_run: bool = False) -> bool:
    info = resolve_gapps(api_level, arch)
    if info is None:
        print(f"  No known GApps package for API {api_level} / {arch}. "
              f"Skipping -- you can flash a compatible GApps zip manually "
              f"after installing the ROM.")
        return False

    print(f"  GApps family: {info['family']}")
    gapps_dir = workdir / "vendor" / "gapps"
    instructions = (
        f"Package family: {info['family']}\n"
        f"Arch: {arch}, API level: {api_level}\n"
        f"Homepage: {info['homepage']}\n"
    )

    if variant and android_version_marketing:
        folder_url = nikgapps_folder_url(android_version_marketing)
        variant_desc = NIKGAPPS_VARIANTS.get(variant, "")
        print(f"  NikGapps variant: {variant} -- {variant_desc}")
        print(f"  Browse current builds for Android {android_version_marketing} here: {folder_url}")
        print(f"  Look for a filename like NikGapps-{variant}-{arch}-"
              f"{android_version_marketing}-<date>-signed.zip and download it manually -- "
              f"NikGapps has no stable API, so this tool won't guess today's exact "
              f"dated filename for you.")
        instructions += (
            f"\nNikGapps variant: {variant} ({variant_desc})\n"
            f"Browse and download from: {folder_url}\n"
            f"Expected filename pattern: NikGapps-{variant}-{arch}-"
            f"{android_version_marketing}-<date>-signed.zip\n"
            f"\nWant to cherry-pick individual apps within this variant? Edit "
            f"nikgapps.config after extracting the zip -- each line is "
            f"PackageName=0 (skip), =1 (include), or =2 (include, keep AOSP "
            f"equivalent too). See https://github.com/nikgapps/config\n"
        )
    else:
        print(f"  Check current download links here: {info['homepage']}")

    if dry_run:
        print(f"  [dry-run] would create {gapps_dir} and stage GApps package there "
              f"for inclusion as a vendor overlay")
        return True

    gapps_dir.mkdir(parents=True, exist_ok=True)
    readme = gapps_dir / "DOWNLOAD_THIS_GAPPS_MANUALLY.txt"
    readme.write_text(
        instructions +
        "\nDirect binary mirrors for GApps move/die often enough that this "
        "tool deliberately does not hardcode one. Download the matching "
        "package, place the zip in this folder, and flash it manually "
        "after installing the built ROM (or wire it into a vendor overlay "
        "if you want it baked into the build).\n"
    )
    print(f"  Wrote instructions to {readme}")
    return True


def stage_custom_assets(workdir: Path, apks: list[Path], wallpapers: list[Path],
                          codename: str, dry_run: bool = False) -> bool:
    """
    Copies user-supplied APKs into a product overlay dir and wallpapers
    into the standard wallpaper resource path. These get picked up by the
    build automatically as long as they exist before `mka bacon` runs.
    """
    overlay_apps = workdir / "vendor" / "extra" / "proprietary" / "app"
    overlay_wallpapers = workdir / "vendor" / "extra" / "proprietary" / "wallpapers"

    if dry_run:
        print(f"  [dry-run] would copy {len(apks)} APK(s) into {overlay_apps}")
        print(f"  [dry-run] would copy {len(wallpapers)} wallpaper(s) into {overlay_wallpapers}")
        return True

    ok = True
    overlay_apps.mkdir(parents=True, exist_ok=True)
    overlay_wallpapers.mkdir(parents=True, exist_ok=True)
    for apk in apks:
        if not apk.exists():
            print(f"  APK not found: {apk}")
            ok = False
            continue
        shutil.copy2(apk, overlay_apps / apk.name)
    for wp in wallpapers:
        if not wp.exists():
            print(f"  Wallpaper not found: {wp}")
            ok = False
            continue
        shutil.copy2(wp, overlay_wallpapers / wp.name)

    print(f"  Staged assets under {workdir / 'vendor' / 'extra'}. "
          f"Remember: these need a matching product makefile entry "
          f"(PRODUCT_PACKAGES / PRODUCT_COPY_FILES) to actually be included "
          f"in the build -- this tool stages the files, the device tree's "
          f"makefile still has to reference them.")
    return ok


def stage_tweak_modules(workdir: Path, modules: list, dry_run: bool = False) -> bool:
    """
    modules: list of device_resolver.RepoCandidate (or anything with
    .full_name / .clone_url) chosen by the user from search_tweak_modules
    results. Clones each into vendor/tweaks/<repo-name> -- these are
    Magisk/KernelSU modules, which are typically flashed post-install
    rather than baked into the build, so this stages them for the person
    to flash alongside the ROM rather than trying to compile them in.
    """
    if not modules:
        return True
    tweaks_dir = workdir / "vendor" / "tweaks"
    ok = True
    for m in modules:
        dest = tweaks_dir / Path(m.full_name).name
        if dry_run:
            print(f"  [dry-run] would clone tweak module {m.full_name} -> {dest}")
            continue
        tweaks_dir.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"  {dest} already exists, skipping clone.")
            continue
        try:
            subprocess.run(["git", "clone", "--depth", "1", m.clone_url, str(dest)], check=True)
        except subprocess.CalledProcessError:
            print(f"  Failed to clone tweak module from {m.clone_url}")
            ok = False
    if not dry_run and modules:
        print(f"  Staged {len(modules)} tweak module(s) under {tweaks_dir}. "
              f"These are typically Magisk/KernelSU modules -- flash the "
              f"resulting zip(s) after installing the ROM rather than "
              f"expecting them compiled into the system image. Read each "
              f"module's README before flashing; module quality and intent "
              f"vary a lot, same caution as vendor blob repos.")
    return ok


def enable_initd_support(workdir: Path, codename: str, api_level: int,
                          dry_run: bool = False) -> bool:
    """
    init.d is a LEGACY mechanism, relevant almost entirely to the
    CyanogenMod/early-LineageOS era -- see config.py header for sourcing.
    This creates the conventional /system/etc/init.d directory inside the
    device tree's root-fs overlay and writes the documented init.rc
    service snippet as a reference file. It does NOT patch a boot image's
    ramdisk automatically: the exact init.rc patch point is kernel/device-
    specific enough (some kernels need it compiled in) that guessing would
    risk an unbootable image, the same reasoning as the Magisk root step.
    """
    if api_level > INITD_MAX_USEFUL_API:
        print(f"  Note: init.d is a legacy mechanism rarely relevant above "
              f"~API {INITD_MAX_USEFUL_API} (Nougat-ish) -- modern setups "
              f"use Magisk modules instead. Proceeding anyway since you "
              f"asked, but this may have no effect on a modern base.")

    rootfs_dir = workdir / "device" / "extra" / codename / "rootdir" / "etc" / "init.d"
    readme = workdir / "device" / "extra" / codename / "INITD_SETUP.txt"

    if dry_run:
        print(f"  [dry-run] would create {rootfs_dir}")
        print(f"  [dry-run] would write {readme} with the init.rc service snippet")
        return True

    rootfs_dir.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        "init.d support -- manual step required\n"
        "========================================\n"
        "This tool created the /system/etc/init.d directory structure, but "
        "actually ENABLING init.d requires adding a service entry to "
        "init.rc INSIDE YOUR BOOT IMAGE'S RAMDISK, which is kernel/device-"
        "specific. The standard, widely-documented snippet is:\n\n"
        f"{INITD_SYSINIT_SERVICE_SNIPPET}\n"
        "Add this near the end of init.rc after unpacking boot.img (e.g. "
        "with the Android Image Kitchen tool), then repack. Some kernels "
        "already support init.d natively -- check before patching.\n"
        "This tool does not patch the ramdisk automatically: guessing the "
        "wrong insertion point in init.rc can produce an unbootable image, "
        "so this is left as a manual, verifiable step.\n"
    )
    print(f"  Created init.d directory structure and wrote setup notes to {readme}")
    return True


def fetch_latest_magisk(dest: Path, dry_run: bool = False) -> Path | None:
    if dry_run:
        print(f"  [dry-run] would query {MAGISK['release_api']} and download "
              f"the latest Magisk APK to {dest}")
        return dest / "magisk-latest.apk"
    try:
        req = urllib.request.Request(MAGISK["release_api"],
                                      headers={"User-Agent": "romforge"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            release = json.loads(resp.read().decode())
        asset = next((a for a in release.get("assets", [])
                      if a["name"].endswith(".apk")), None)
        if asset is None:
            print("  Could not find an .apk asset in the latest Magisk release.")
            return None
        dest.mkdir(parents=True, exist_ok=True)
        out_path = dest / asset["name"]
        urllib.request.urlretrieve(asset["browser_download_url"], out_path)
        return out_path
    except Exception as e:
        print(f"  Failed to fetch Magisk release info: {e}")
        return None


def patch_boot_image_with_magisk(boot_img: Path, magisk_apk: Path, dry_run: bool = False) -> bool:
    """
    Magisk's APK contains the actual patching binaries, but driving its
    in-app boot patcher headlessly requires unzipping the APK's native libs
    and invoking magiskboot -- which is architecture- and version-specific
    enough that we don't fake reliability here. This wraps the official,
    well-documented manual route and tells the user exactly what's
    happening rather than pretending a one-liner handles every device.
    """
    print("  Root requested: boot image patching method.")
    if dry_run:
        print(f"  [dry-run] would extract magiskboot from {magisk_apk} and "
              f"patch {boot_img} -> {boot_img.stem}_magisk_patched.img")
        return True

    if not boot_img.exists():
        print(f"  boot.img not found at {boot_img}. Locate it under "
              f"out/target/product/<codename>/boot.img after a successful build.")
        return False

    print(
        "  Automated headless patching varies by device/arch enough that "
        "this tool does not attempt it blindly. Recommended manual route "
        "(well-documented and reliable across devices):\n"
        f"    1. Copy {boot_img} to your device, or use an Android emulator/VM.\n"
        f"    2. Install {magisk_apk.name} on that device.\n"
        "    3. In the Magisk app: Install > Select and Patch a File > "
        "choose boot.img.\n"
        "    4. Pull the resulting magisk_patched-*.img back off the device.\n"
        "  This keeps root patching correct per-architecture without this "
        "tool guessing at magiskboot invocation flags for your specific device."
    )
    return True
<<<<<<< HEAD


def stage_boot_animation(workdir: Path, animation_zip: Path,
                          dry_run: bool = False) -> bool:
    """
    Copy a user-provided bootanimation.zip to the correct location in the
    source tree before build. Structure of a valid bootanimation.zip:
      desc.txt   -- width height fps / p <loop> <pause> <partN>
      part0/     -- PNG frames numbered 0000.png, 0001.png, ...
      part1/     -- (optional further parts)
    The build system picks it up from system/media/bootanimation.zip
    automatically -- no makefile entry needed for this one.
    Source: AOSP frameworks/base/cmds/bootanimation/
    """
    if not animation_zip.exists():
        print(f"  Boot animation zip not found: {animation_zip}")
        return False
    dest = workdir / BOOT_ANIMATION_PATH
    if dry_run:
        print(f"  [dry-run] would copy {animation_zip} -> {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(animation_zip, dest)
    print(f"  Staged boot animation: {dest}")
    print(f"  Note: your zip must contain desc.txt + numbered PNG frames in "
          f"part*/ subdirectories. If the animation is garbled or missing, "
          f"verify the zip structure against AOSP's bootanimation format.")
    return True


def surface_radio_notes() -> None:
    """Print a clear reminder that radio firmware is out of scope for a
    ROM build and must be handled separately."""
    print(f"\n  [RADIO/MODEM NOTE] {RADIO_NOTES}")


def surface_selinux_notes(viability: str) -> None:
    """Print SELinux guidance, louder on archival/fragile builds where
    sepolicy mismatches are most common."""
    if viability in ("archival-only", "fragile"):
        print(f"\n  [SELINUX WARNING] {SELINUX_NOTES}")


def search_recovery_trees(codename: str, vendor: str | None,
                            recovery: str = "twrp") -> list:
    """
    Search GitHub for a recovery device tree for the chosen recovery
    project (twrp/orangefox/skyhawk) using the same search pattern as
    device trees. Returns a list of RepoCandidate objects, same as
    search_device_trees(). Imported lazily to avoid circular imports.
    """
    from device_resolver import _search_repos
    src = RECOVERY_SOURCES.get(recovery, RECOVERY_SOURCES["twrp"])
    orgs = src["github_orgs"]
    queries = [f"org:{org} {codename} in:name" for org in orgs]
    vendor_str = vendor or ""
    queries.append(f"{codename} {recovery} recovery android")
    queries.append(f"android_device_{vendor_str}_{codename} recovery")
    return _search_repos(
        queries, match_token=codename, vendor_token=vendor,
        kind_keywords={"recovery": ["recovery", "twrp", "orangefox", "shrp"]},
    )
=======
>>>>>>> 569c9bad1ff47876aa62b79a66e6b46ec3fba4a3
