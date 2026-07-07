#!/usr/bin/env python3
"""
romforge.py
=============
CLI entrypoint orchestrating: version selection -> device tree resolution
-> source sync -> optional GApps/custom assets/root -> build (local/docker/
github-actions).

This tool is an ORCHESTRATOR around existing toolchains (repo, lunch, mka,
Magisk, GitHub's API). It removes manual toil; it does not remove the
underlying realities of AOSP builds (disk/RAM/time requirements, dead
branches on old Android versions, inconsistent device tree quality).

Usage examples:
  python3 romforge.py list-versions
  python3 romforge.py find-device --codename angler
  python3 romforge.py detect-device
  python3 romforge.py build --version 12 --codename angler --vendor google \\
      --backend local --gapps --root --dry-run
"""

import argparse
import sys
from pathlib import Path

from config import ANDROID_VERSIONS, ARCHES, NIKGAPPS_VARIANTS
from device_resolver import (detect_connected_device, search_device_trees,
                               search_kernel_trees, search_tweak_modules, print_candidates)
from source_manager import SourceManager
from builder import get_backend
from customizer import (stage_gapps, stage_custom_assets, stage_tweak_modules,
                          enable_initd_support, fetch_latest_magisk, patch_boot_image_with_magisk)

try:
    import questionary
except ImportError:
    questionary = None


def run_tui():
    """
    Interactive arrow-key menu mode, built on questionary. Walks through
    the same parameters the `build` CLI subcommand takes, then hands off
    to the exact same cmd_build() function used by the CLI path -- the
    TUI is a front-end for argument collection, not a separate pipeline.
    """
    if questionary is None:
        print("The TUI mode needs the 'questionary' package: pip install questionary")
        print("Falling back to --help. Use CLI flags directly, e.g.:")
        print("  python3 romforge.py build --version 12 --codename angler --dry-run")
        sys.exit(1)

    print("=== romforge interactive mode ===\n")

    action = questionary.select(
        "What do you want to do?",
        choices=["Build a ROM", "Find device trees on GitHub",
                 "Detect connected device", "List supported Android versions", "Quit"],
    ).ask()
    if action is None or action == "Quit":
        return

    if action == "List supported Android versions":
        cmd_list_versions(None)
        return

    if action == "Detect connected device":
        cmd_detect_device(None)
        return

    if action == "Find device trees on GitHub":
        codename = questionary.text("Device codename (e.g. angler):").ask()
        if not codename:
            return
        vendor = questionary.text("Vendor hint (optional, e.g. google):", default="").ask()
        ns = argparse.Namespace(codename=codename, vendor=vendor or None)
        cmd_find_device(ns)
        return

    # --- Build a ROM ---
    version = questionary.select(
        "Android version to build:",
        choices=[f"{v} (API {info.api_level}, {info.viability})"
                  for v, info in ANDROID_VERSIONS.items()],
    ).ask()
    if version is None:
        return
    version = version.split(" ")[0]
    info = ANDROID_VERSIONS[version]
    if info.viability == "archival-only":
        proceed = questionary.confirm(
            f"Android {version} is rated archival-only -- expect manual "
            f"toolchain repair regardless. Continue?", default=False).ask()
        if not proceed:
            return

    source = questionary.select(
        "Source to build from:",
        choices=["lineage (most device trees target this)", "aosp (raw AOSP)"],
    ).ask()
    if source is None:
        return
    source = "lineage" if source.startswith("lineage") else "aosp"

    use_latest_aosp = False
    if source == "aosp":
        use_latest_aosp = questionary.confirm(
            "Use Google's current rolling android-latest-release branch "
            "instead of the historical numbered tag for this version?",
            default=True).ask()

    detected = detect_connected_device()
    codename = None
    vendor = None
    if detected:
        use_detected = questionary.confirm(
            f"Detected connected device '{detected['codename']}' "
            f"({detected['vendor']}, {detected['arch']}). Use it?", default=True).ask()
        if use_detected:
            codename = detected["codename"]
            vendor = detected["vendor"]
            arch = detected["arch"]
    if codename is None:
        codename = questionary.text("Device codename:").ask()
        if not codename:
            return
        vendor = questionary.text("Vendor hint (optional):", default="").ask() or None
        arch = questionary.select("Device architecture:", choices=list(ARCHES.keys())).ask()
        if arch is None:
            return

    backend = questionary.select(
        "Build backend:",
        choices=["local", "docker", "github-actions"],
    ).ask()
    if backend is None:
        return

    extras = questionary.checkbox(
        "Optional add-ons (space to toggle, enter to confirm):",
        choices=["Stage GApps", "Patch root (Magisk)", "Select a kernel tree",
                 "Tweak/mod modules", "init.d support (legacy, mostly Android 4-9)"],
    ).ask()
    if extras is None:
        extras = []
    gapps = "Stage GApps" in extras
    root = "Patch root (Magisk)" in extras
    kernel = "Select a kernel tree" in extras
    want_tweaks = "Tweak/mod modules" in extras
    initd = "init.d support (legacy, mostly Android 4-9)" in extras

    gapps_variant = None
    if gapps:
        choices = [f"{name} -- {desc}" for name, desc in NIKGAPPS_VARIANTS.items()]
        pick = questionary.select("GApps variant:", choices=choices).ask()
        if pick:
            gapps_variant = pick.split(" -- ")[0]

    tweak_queries = []
    if want_tweaks:
        print("Enter tweak/mod search terms one at a time (e.g. 'viper4android', "
              "'adaway'). Leave blank to stop.")
        while True:
            q = questionary.text("Tweak search term (blank to finish):", default="").ask()
            if not q:
                break
            tweak_queries.append(q)

    apks, wallpapers = [], []
    if questionary.confirm("Add a custom APK?", default=False).ask():
        apk_path = questionary.path("Path to APK:").ask()
        if apk_path:
            apks.append(apk_path)
    if questionary.confirm("Add a custom wallpaper?", default=False).ask():
        wp_path = questionary.path("Path to wallpaper image:").ask()
        if wp_path:
            wallpapers.append(wp_path)

    jobs_str = questionary.text("Parallel build jobs:", default="4").ask()
    try:
        jobs = int(jobs_str)
    except (TypeError, ValueError):
        jobs = 4

    dry_run = questionary.confirm(
        "Dry-run first (recommended -- prints every command without "
        "running anything)?", default=True).ask()

    workdir = questionary.text("Source working directory:", default="./romforge-src").ask()

    # Pre-check host requirements here too, so the TUI can offer --force
    # interactively instead of silently failing after a long Q&A session.
    probe = SourceManager(Path(workdir).expanduser(), source=source)
    host_warnings = probe.check_host_requirements()
    force = False
    if host_warnings:
        print("\nHost requirement warnings:")
        for w in host_warnings:
            print(f"  - {w}")
        force = questionary.confirm(
            "Proceed anyway despite the warnings above?", default=False).ask()
        if not force:
            print("Stopping -- resolve the warnings above and try again.")
            return

    ns = argparse.Namespace(
        version=version, source=source, use_latest_aosp=use_latest_aosp,
        codename=codename, vendor=vendor, arch=arch, workdir=workdir,
        backend=backend, lunch_target=None, jobs=jobs, gapps=gapps,
        gapps_variant=gapps_variant, root=root, kernel=kernel,
        tweak=tweak_queries or None, initd=initd,
        apk=apks or None, wallpaper=wallpapers or None, skip_device_tree=False,
        auto_select=False, force=force, dry_run=bool(dry_run),
    )
    cmd_build(ns)


def cmd_list_versions(_args):
    print(f"{'Version':<8}{'API':<5}{'Viability':<16}{'Lineage branch':<18}{'Notes'}")
    for v, info in ANDROID_VERSIONS.items():
        print(f"{v:<8}{info.api_level:<5}{info.viability:<16}"
              f"{(info.lineage_branch or '-'):<18}{info.notes[:60]}")
    print("\nArches:")
    for name, a in ARCHES.items():
        print(f"  {name:<8} bitness={a['bitness']} tier={a['tier']} common for: {a['common_for']}")


def cmd_detect_device(_args):
    info = detect_connected_device()
    if info is None:
        print("No connected device found (or adb not installed). "
              "Connect a device with USB debugging enabled and try again.")
        return
    print("Detected device:")
    for k, v in info.items():
        print(f"  {k}: {v}")


def cmd_find_device(args):
    print(f"Searching GitHub for device trees matching '{args.codename}'"
          + (f" (vendor hint: {args.vendor})" if args.vendor else "") + " ...")
    candidates = search_device_trees(args.codename, vendor_hint=args.vendor)
    print_candidates(candidates)
    if candidates:
        print("\nNote: review each result before cloning -- stars/recency are "
              "a starting filter, not a trust guarantee. Prefer LineageOS/"
              "TheMuppets org results when available.")


def _pick_repo_interactively(candidates: list, label: str, auto_select: bool) -> object | None:
    """
    Shared "show exact matches, let the person choose" flow used for
    device trees AND kernel trees (the same UX, just a different kind of
    repo). Returns the chosen RepoCandidate, or None if skipped/unavailable.
    Never falls back to silently picking the top result unless
    auto_select=True -- see the d2att incident in earlier testing for why.
    """
    exact = [c for c in candidates if c.exact_match]
    interactive = questionary is not None and sys.stdin.isatty()

    if not candidates:
        print(f"  No {label} candidates found.")
        return None
    if not exact:
        print(f"  No EXACT match found among {label} candidates -- only "
              f"partial/substring matches. Refusing to auto-select.")
        return None
    if auto_select:
        choice = next((c for c in exact if c.vendor_match), exact[0])
        print(f"  --auto-select: picked {choice.full_name} for {label} "
              f"(highest-ranked exact match). Review this before trusting "
              f"the build -- {len(exact)} exact match(es) were found in total.")
        return choice
    if interactive:
        labels = [f"{c.full_name}  (★{c.stars}, pushed {c.pushed_at[:10]})" for c in exact]
        choice = questionary.select(
            f"{len(exact)} exact {label} match(es) found -- pick one:",
            choices=labels + [f"Skip -- I'll provide the {label} myself"],
        ).ask()
        if choice and not choice.startswith("Skip"):
            return exact[labels.index(choice)]
        return None
    print(f"  Multiple exact {label} matches found but no TTY/questionary "
          f"available to prompt for a choice. Re-run interactively, or "
          f"pass --auto-select to take the top-ranked match without prompting.")
    return None


def cmd_build(args):
    if args.version not in ANDROID_VERSIONS:
        print(f"Unknown version '{args.version}'. Run `list-versions` to see options.")
        sys.exit(1)
    info = ANDROID_VERSIONS[args.version]
    workdir = Path(args.workdir).expanduser().resolve()

    print(f"=== ROMForge build: Android {args.version} ({info.viability}) ===")
    if info.viability == "archival-only":
        print("  WARNING: this version is rated archival-only. Expect manual "
              "toolchain/dependency repair regardless of how this proceeds.")

    sm = SourceManager(workdir, source=args.source, use_latest_aosp=args.use_latest_aosp)
    warnings = sm.check_host_requirements()
    for w in warnings:
        print(f"  [warning] {w}")
    if warnings and not args.force:
        print("  Resolve the warnings above, or re-run with --force to proceed anyway.")
        sys.exit(1)

    # 1. Device tree resolution (search + optional ADB auto-detect)
    codename = args.codename
    vendor = args.vendor
    if codename is None:
        detected = detect_connected_device()
        if detected:
            codename = detected["codename"]
            vendor = vendor or detected["vendor"]
            print(f"  Auto-detected connected device: {codename} ({vendor})")
        else:
            print("  No --codename given and no connected device detected. "
                  "Pass --codename explicitly.")
            sys.exit(1)

    print(f"\n--- Resolving device trees for '{codename}' ---")
    candidates = search_device_trees(codename, vendor_hint=vendor)
    print_candidates(candidates)
    clone_urls = {}
    if candidates and not args.skip_device_tree:
        device_candidates = [c for c in candidates if c.kind == "device"]
        device_repo = _pick_repo_interactively(device_candidates, "device tree", args.auto_select)
        if device_repo is not None:
            print(f"  Selected device tree: {device_repo.full_name}")
            clone_urls["device"] = device_repo.clone_url
            vendor_repo = next((c for c in candidates
                                  if c.kind == "vendor" and c.exact_match), None)
            if vendor_repo:
                clone_urls["vendor"] = vendor_repo.clone_url
        else:
            print("  Skipping device tree auto-clone. Place a device tree "
                  "under the workdir's device/ directory yourself, or "
                  "re-run with --codename matching the repo's actual "
                  "naming convention.")

    # 1b. Kernel tree resolution -- separate from device trees because a
    # device commonly has several competing community kernel forks worth
    # choosing between (stock-derived, custom perf-tuned, etc.), unlike the
    # device tree itself. Only runs if --kernel was requested, since most
    # device trees already reference a default kernel tree on their own.
    if args.kernel and not args.skip_device_tree:
        print(f"\n--- Resolving kernel trees for '{codename}' ---")
        kernel_candidates = search_kernel_trees(codename, vendor_hint=vendor)
        print_candidates(kernel_candidates)
        kernel_repo = _pick_repo_interactively(kernel_candidates, "kernel tree", args.auto_select)
        if kernel_repo is not None:
            print(f"  Selected kernel tree: {kernel_repo.full_name}")
            clone_urls["kernel"] = kernel_repo.clone_url
        else:
            print("  Skipping kernel auto-clone. The device tree's default "
                  "kernel reference (if any) will be used instead.")

    # 2. Source sync
    print(f"\n--- Syncing source ({args.source}) ---")
    if not sm.init_and_sync(args.version, jobs=args.jobs, dry_run=args.dry_run):
        print("  Source sync failed -- see message above. Stopping.")
        sys.exit(1)

    if clone_urls:
        print("\n--- Cloning resolved device/vendor trees ---")
        sm.clone_device_trees(clone_urls, dry_run=args.dry_run)

    # 3. Optional customization (pre-build)
    if args.gapps:
        print("\n--- Staging GApps ---")
        stage_gapps(workdir, info.api_level, args.arch,
                    android_version_marketing=args.version,
                    variant=args.gapps_variant, dry_run=args.dry_run)

    if args.apk or args.wallpaper:
        print("\n--- Staging custom apps/wallpapers ---")
        stage_custom_assets(
            workdir,
            apks=[Path(p) for p in (args.apk or [])],
            wallpapers=[Path(p) for p in (args.wallpaper or [])],
            codename=codename,
            dry_run=args.dry_run,
        )

    if args.tweak:
        print("\n--- Resolving tweak/mod modules ---")
        chosen_modules = []
        for query in args.tweak:
            print(f"  Searching for '{query}'...")
            results = search_tweak_modules(query)
            print_candidates(results)
            if not results:
                continue
            if args.auto_select:
                chosen_modules.append(results[0])
                print(f"  --auto-select: picked {results[0].full_name}")
            elif questionary is not None and sys.stdin.isatty():
                labels = [f"{c.full_name}  (★{c.stars})" for c in results]
                pick = questionary.select(
                    f"Pick a module for '{query}':",
                    choices=labels + ["Skip this one"],
                ).ask()
                if pick and pick != "Skip this one":
                    chosen_modules.append(results[labels.index(pick)])
            else:
                print("  No TTY/questionary to prompt -- skipping (or pass --auto-select).")
        if chosen_modules:
            stage_tweak_modules(workdir, chosen_modules, dry_run=args.dry_run)

    if args.initd:
        print("\n--- Enabling init.d support ---")
        enable_initd_support(workdir, codename, info.api_level, dry_run=args.dry_run)

    # 4. Build
    print(f"\n--- Building ({args.backend} backend) ---")
    lunch_target = args.lunch_target or f"lineage_{codename}-userdebug"
    backend = get_backend(args.backend)
    if args.backend == "github-actions":
        from backends_remote import GithubActionsBuildBackend
        gh = backend  # type: GithubActionsBuildBackend
        gh.write_workflow(workdir, sm.manifest_url(), sm.branch_for(args.version),
                           lunch_target, dry_run=args.dry_run)
        backend.run_build(workdir, lunch_target, args.jobs, dry_run=args.dry_run)
        return
    elif args.backend == "docker":
        built = backend.run_build(workdir, lunch_target, args.jobs, dry_run=args.dry_run)
    else:
        built = backend.run_build(workdir, lunch_target, args.jobs, dry_run=args.dry_run)

    if not built:
        sys.exit(1)

    # 4b. Locate the build artifact (local backend only -- docker/github-
    # actions outputs land in a container filesystem or an Actions
    # artifact respectively, which the user retrieves through those
    # systems rather than a local path this tool can print).
    output_zip = None
    if args.backend == "local" and not args.dry_run:
        print("\n--- Locating build artifact ---")
        output_zip = backend.locate_output(workdir, codename)
        if output_zip:
            size_mb = output_zip.stat().st_size / (1024 * 1024)
            print(f"  Build artifact: {output_zip}  ({size_mb:.0f} MB)")
        else:
            print(f"  Build reported success but no .zip was found under "
                  f"{workdir / 'out' / 'target' / 'product' / codename}. "
                  f"Check the build log above -- `mka bacon` sometimes "
                  f"completes a stage without producing the final signed "
                  f"package if something downstream (e.g. signing) failed silently.")

    # 5. Root (post-build boot.img patch)
    if args.root and args.backend == "local":
        print("\n--- Root (Magisk boot image patch) ---")
        boot_img = workdir / "out" / "target" / "product" / codename / "boot.img"
        magisk_dir = workdir / "magisk"
        magisk_apk = fetch_latest_magisk(magisk_dir, dry_run=args.dry_run)
        if magisk_apk:
            patch_boot_image_with_magisk(boot_img, magisk_apk, dry_run=args.dry_run)
    elif args.root:
        print("\n  Root patching is currently only wired up for the local "
              "backend's output path (docker/github-actions outputs land "
              "in different locations) -- patch the boot.img manually using "
              "the same Magisk steps after retrieving the build artifact.")

    print("\n=== Done ===")
    if output_zip:
        print(f"Flashable ROM: {output_zip}")


def build_arg_parser():
    p = argparse.ArgumentParser(prog="romforge")
    sub = p.add_subparsers(dest="command", required=False)

    sub.add_parser("list-versions", help="List supported Android versions and arches").set_defaults(func=cmd_list_versions)

    sub.add_parser("tui", help="Interactive arrow-key menu mode (needs questionary)").set_defaults(func=lambda _args: run_tui())

    sub.add_parser("detect-device", help="Read codename/arch from a connected ADB device").set_defaults(func=cmd_detect_device)

    pf = sub.add_parser("find-device", help="Search GitHub for device trees by codename")
    pf.add_argument("--codename", required=True)
    pf.add_argument("--vendor", default=None)
    pf.set_defaults(func=cmd_find_device)

    pb = sub.add_parser("build", help="Run the full pipeline")
    pb.add_argument("--version", required=True, help="Android major version, e.g. 12")
    pb.add_argument("--source", choices=["lineage", "aosp"], default="lineage")
    pb.add_argument("--use-latest-aosp", action="store_true",
                     help="With --source aosp, use Google's current rolling "
                          "android-latest-release branch instead of a "
                          "historical numbered tag (see config.py notes)")
    pb.add_argument("--codename", default=None, help="Device codename (omit to auto-detect via ADB)")
    pb.add_argument("--vendor", default=None, help="Vendor hint, e.g. google, samsung")
    pb.add_argument("--arch", choices=list(ARCHES.keys()), default="arm64")
    pb.add_argument("--workdir", default="./romforge-src")
    pb.add_argument("--backend", choices=["local", "docker", "github-actions"], default="local")
    pb.add_argument("--lunch-target", default=None)
    pb.add_argument("--jobs", type=int, default=4)
    pb.add_argument("--gapps", action="store_true", help="Stage GApps for this version/arch")
    pb.add_argument("--gapps-variant", choices=list(NIKGAPPS_VARIANTS.keys()), default=None,
                     help="NikGapps variant (core/basic/omni/stock/full); requires --gapps")
    pb.add_argument("--root", action="store_true", help="Patch output boot.img with Magisk")
    pb.add_argument("--apk", action="append", help="Path to a custom APK to bundle (repeatable)")
    pb.add_argument("--wallpaper", action="append", help="Path to a custom wallpaper image (repeatable)")
    pb.add_argument("--kernel", action="store_true",
                     help="Search for and select a kernel tree separately from the device tree")
    pb.add_argument("--tweak", action="append", default=None,
                     help="Search term for a Magisk/KernelSU tweak module to stage (repeatable, "
                          "e.g. --tweak viper4android --tweak adaway)")
    pb.add_argument("--initd", action="store_true",
                     help="Create /system/etc/init.d structure + setup notes (legacy, mostly "
                          "relevant to Android 4-9-era CM/early-Lineage builds)")
    pb.add_argument("--skip-device-tree", action="store_true", help="Skip auto device tree clone")
    pb.add_argument("--auto-select", action="store_true",
                     help="Non-interactive: pick the top-ranked exact device "
                          "tree match without prompting (for scripted runs)")
    pb.add_argument("--force", action="store_true", help="Proceed despite host requirement warnings")
    pb.add_argument("--dry-run", action="store_true", help="Print commands without executing them")
    pb.set_defaults(func=cmd_build)

    return p


if __name__ == "__main__":
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.command is None:
        run_tui()
    else:
        args.func(args)
