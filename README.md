# romforge

A Python orchestrator for custom Android ROM builds: picks an Android
version (4–15), finds device trees on GitHub, syncs source via `repo`,
optionally stages GApps / custom APKs / wallpapers, builds via a chosen
backend (local machine, Docker, or GitHub Actions), and optionally patches
the output boot image with Magisk for root.

Has both a CLI (explicit flags, scriptable) and an interactive TUI
(arrow-key menus via `questionary`). Same underlying pipeline either way.

**This is a wrapper around existing tools (`repo`, `lunch`, `mka`, Magisk,
GitHub's API) — it removes manual toil, not the underlying realities of
AOSP builds.** Read the Limitations section before you invest hours into a
build.

## Files

| File | Responsibility |
|---|---|
| `main.py` | CLI + TUI, orchestrates the full pipeline |
| `config.py` | Version/branch/GApps/arch data tables (edit this to update mappings) |
| `device_resolver.py` | GitHub search for device trees; ADB auto-detect |
| `source_manager.py` | `repo init`/`sync` wrapper |
| `builder.py` | Build backend interface + local backend |
| `backends_remote.py` | Docker + GitHub Actions backends |
| `customizer.py` | GApps staging, custom asset staging, Magisk root patch |
| `romforge.yaml` | Example config shape for extending org/GApps lists |
| `requirements.txt` | Dependencies (questionary for TUI; everything else is stdlib) |
| `README.md` | This file |

## Quick start

```bash
pip install questionary   # only needed for the interactive TUI mode

# Interactive mode -- arrow-key menus walk you through every choice
python3 romforge.py
# (equivalent to: python3 romforge.py tui)

# --- Or use explicit CLI flags ---

# See supported versions + their build viability rating
python3 romforge.py list-versions

# Search GitHub for device trees by codename (no source synced yet)
python3 romforge.py find-device --codename angler --vendor google

# If a device is plugged in via USB debugging, read its codename/arch
python3 romforge.py detect-device

# Dry-run a full pipeline so you can see every command before it runs
python3 romforge.py build --version 12 --codename angler --vendor google \
    --backend local --gapps --root --dry-run

# Actually run it (drop --dry-run). This will take hours and ~150GB+ disk.
python3 romforge.py build --version 12 --codename angler --vendor google \
    --backend local --gapps --root --apk ./my_custom_app.apk \
    --wallpaper ./my_wallpaper.png

# With GApps variant, a separately-selected kernel tree, a tweak module
# search, and legacy init.d support all in one run:
python3 romforge.py build --version 11 --codename d2att --vendor samsung \
    --gapps --gapps-variant core --kernel --tweak viper4android --initd \
    --dry-run
```

## TUI

Running `python3 romforge.py` with no arguments (or `python3 romforge.py
tui` explicitly) drops into an arrow-key menu that asks the same questions
the CLI flags answer: action, Android version, source (LineageOS/AOSP),
device codename (auto-detects a connected device first and offers to use
it), architecture, build backend, optional GApps/root, optional custom
APK/wallpaper, job count, and dry-run. It then calls the *exact same*
pipeline function the CLI uses — the TUI is just a friendlier way to
collect the same parameters, not a separate code path.

If `questionary` isn't installed, TUI mode prints an install hint and
exits; the CLI subcommands keep working without it.

## What each stage actually does

1. **Version selection** — looks up the Android version in `config.py`,
   prints its viability rating (`good` / `fragile` / `archival-only`) so
   you know what you're getting into before syncing gigabytes of source.
2. **Device tree resolution** — searches GitHub (configured orgs +
   general search) for repos matching the codename, and checks whether
   the codename appears as a whole token in the repo name (e.g. `d2att`
   in `android_device_samsung_d2att`) rather than just a loose substring
   (a codename like `hello` would otherwise match an unrelated repo named
   `...ac50hello`). Matches are flagged `[exact]` or
   `[PARTIAL/substring match]` accordingly.
   **When multiple exact matches exist, you're prompted to pick one** —
   in an interactive terminal (CLI or TUI) this is a `questionary` select
   menu; the tool never silently grabs the highest-starred result for you.
   For scripted/non-interactive runs, pass `--auto-select` to take the
   top-ranked exact match without prompting (review the printed candidate
   list either way — popularity isn't a correctness guarantee, especially
   for vendor blob repos containing binaries you can't audit).
3. **Source sync** — runs `repo init`/`repo sync` against either a
   LineageOS or raw AOSP manifest for the chosen version's branch. For
   AOSP, `--use-latest-aosp` switches to Google's current rolling
   `android-latest-release` branch (with the `--partial-clone
   --no-use-superproject` flags their docs now specify) instead of a
   historical numbered tag — see the verification notes below.
4. **GApps** — resolves the right package *family* for your version+arch.
   For the API range NikGapps covers, you pick a **variant**
   (`core`/`basic`/`omni`/`stock`/`full` — see `config.NIKGAPPS_VARIANTS`)
   rather than just a family name. **Direct binary links are intentionally
   not hardcoded** — NikGapps ships via a SourceForge file browser with no
   stable API, so this tool points you at the correct per-version folder
   and the expected filename pattern, and you confirm/download the exact
   dated file yourself. Want to cherry-pick individual apps within a
   variant (e.g. drop GoogleDialer)? Edit `nikgapps.config` after
   extracting — each line is `PackageName=0/1/2`; see
   github.com/nikgapps/config.
5. **Kernel tree** (optional, `--kernel`) — separate search/selection from
   the device tree, since a device commonly has multiple competing
   community kernel forks worth choosing between. Same exact-match +
   interactive-pick pattern as device trees.
6. **Tweak/mod modules** (optional, `--tweak <query>`, repeatable) —
   searches GitHub (configured Magisk module orgs + general search) for a
   free-text query like `viper4android` or `adaway`, lets you pick from
   real results, and clones the chosen module(s) into `vendor/tweaks/`.
   These are flashed as Magisk/KernelSU zips after installing the ROM,
   not compiled into the system image — read each module's README before
   flashing, same caution as vendor blob repos.
7. **init.d support** (optional, `--initd`) — a **legacy** mechanism,
   relevant almost entirely to Android 4–9-era CM/early-Lineage builds
   (modern setups use Magisk modules instead). Creates the conventional
   `/system/etc/init.d` directory and writes the documented `init.rc`
   service snippet as a reference file. Does **not** patch a boot image's
   ramdisk automatically — that patch point is kernel/device-specific
   enough that guessing wrong can produce an unbootable image, so it's
   left as a manual, verifiable step (same reasoning as the Magisk root
   step below).
8. **Custom apps/wallpapers** — copies your files into a vendor overlay
   path. You still need a matching device tree makefile entry
   (`PRODUCT_PACKAGES` / `PRODUCT_COPY_FILES`) referencing them — staging
   the files doesn't auto-wire the build to include them.
9. **Build** — runs `lunch` + `mka bacon` via your chosen backend. On the
   **local** backend, a successful build is automatically followed by
   locating the output `.zip` under `out/target/product/<codename>/` and
   printing its full path (with size) as `Flashable ROM: ...` at the end
   of the run — no need to go hunting through the AOSP output tree
   yourself. If the build reports success but no zip turns up (signing
   failed silently, etc.), this is called out explicitly rather than
   silently saying nothing.
10. **Root** — patches the output `boot.img` with Magisk. Done as a
    post-build step (safer, more reliable across versions) rather than an
    in-tree `su` addon. The actual headless patch step prints manual
    instructions rather than guessing `magiskboot` flags blindly per device.

## Backends

- **local** (default) — runs everything directly on this machine,
  automatically, start to finish: source sync, device/kernel tree
  cloning, customization, `lunch`+`mka bacon`, and (unless `--dry-run`)
  locating the final flashable zip for you. This is the only backend that
  prints a final `Flashable ROM: <path>` line, since docker/github-actions
  outputs land in a container filesystem or a GitHub Actions artifact
  respectively, which you retrieve through those systems instead.
- **docker** — generates a `Dockerfile.romforge` with the build deps and
  runs the build inside a container with your workdir bind-mounted. Disk/
  RAM still need to be available to Docker itself.
- **github-actions** — generates `.github/workflows/romforge-build.yml`.
  Doesn't run anything locally; you commit/push it and trigger it from the
  Actions tab. **Free runners have ~14GB disk and a 6hr limit** — realistic
  for small device trees or partial steps, not most full AOSP builds. Use
  a self-hosted runner for anything serious.
- **Cloud VM / QEMU box** — not a separate backend. SSH into your VM and
  run the `local` backend there. A fourth code path would just be these
  same shell commands with extra indirection.

## verified-against-source notes (checked June 2026)

- **AOSP's release model changed in 2026.** Source now publishes twice a
  year (Q2/Q4) under a trunk-stable model, and Google's documented branch
  for building/contributing is the rolling `android-latest-release`, not
  per-version numbered tags. This tool keeps the historical tags available
  (for reproducing an exact old release) but defaults new AOSP work toward
  `--use-latest-aosp`. Source: source.android.com/docs/setup/download
- **LineageOS only officially builds the two most recent major versions
  at a time.** Branches below 14 in this tool's table are marked
  `lineage_eol=True` and will print a warning when selected — the branch
  ref may still exist in git history, but expect no upstream fixes or
  official builds. Source: lineageos.org/Changelog-31, wiki.lineageos.org/faq
- Re-verify branch names periodically — they rot. Check
  github.com/LineageOS/android/branches for the current pair before
  relying on an exact tag beyond what's in `config.py`.

## Limitations (read this before a long build)

- **Android 4–6 are rated `archival-only`.** Old versions often don't
  build on modern Ubuntu/glibc, and most public device trees from this
  era are dead or abandoned (this was the CyanogenMod era, pre-dating
  LineageOS). This tool will still attempt the steps, but no script can
  repair a decade of bitrot — treat it as a research exercise, not "I
  will flash this on my phone tonight."
- **No hardcoded device list.** Device trees are searched live on GitHub
  rather than baked in, because a static list would be stale immediately.
  This means coverage depends entirely on what's public and maintained
  for your specific device.
- **Disk/RAM/time are real.** Expect 150GB+ free disk, 16GB+ RAM, and
  multi-hour build times for any modern (9+) target. The tool checks and
  warns but cannot work around insufficient resources.
- **Architecture matters throughout.** GApps package, Magisk variant, and
  even build viability differ between `armv7` and `arm64` — pass `--arch`
  correctly; double check against your device's actual `ro.product.cpu.abi`
  if unsure (`detect-device` does this for you on a connected device).
- **This tool can't guarantee a successful build for any given
  device/version combination.** It removes toil (manifest lookup, tree
  search, boilerplate commands); it cannot remove the risk that a specific
  device tree is incompatible with a specific branch, or that proprietary
  blobs are missing/mismatched.
