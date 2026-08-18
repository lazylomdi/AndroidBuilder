# romforge

A Python orchestrator for building custom Android ROMs (Android 4–15).
Handles source sync, device tree discovery, GApps, custom assets, root,
recovery, and the actual build — with a questionary TUI or plain CLI flags.

## Quick start

```bash
# Install TUI dependency (nothing else needed for CLI)
pip install questionary

# Set a GitHub token once — raises API limit from 60 to 5,000 req/hr
# (create at github.com/settings/tokens — no scopes needed)
export GITHUB_TOKEN=ghp_...
# or set it interactively: python3 romforge.py → Settings → Set GitHub token

# Interactive TUI (recommended first run)
python3 romforge.py

# CLI — dry run to preview all commands before committing disk/time
python3 romforge.py build \
  --version 14 --codename angler --vendor google --arch arm64 \
  --gapps --gapps-variant core --root \
  --dry-run

# CLI — actual build (takes hours, needs 150GB+ disk)
python3 romforge.py build \
  --version 14 --codename angler --vendor google \
  --gapps --gapps-variant core --root \
  --background          # runs in tmux, survives terminal close
```

## Files

| File | Role |
|---|---|
| `romforge.py` | Entry point — TUI dispatcher + CLI argument parsing + pipeline runner |
| `config.py` | All static data: version map, GApps catalog, org lists |
| `github_client.py` | Authenticated, disk-cached GitHub API client |
| `device_resolver.py` | GitHub search for device/kernel/recovery trees; ADB detect |
| `pipeline.py` | Build pipeline steps: host checks, repo sync, tree cloning, background launch |
| `backends.py` | Local, Docker, GitHub Actions build backends |
| `customizer.py` | GApps (with working Android.mk), assets, boot animation, root, init.d |
| `tui.py` | Interactive TUI — collects config, passes to pipeline |
| `requirements.txt` | Python and system dependencies |
| `README.md` | This file |

## Subcommands

```
python3 romforge.py                          # TUI
python3 romforge.py build       [opts]       # CLI build
python3 romforge.py find        --codename X # search device trees on GitHub
python3 romforge.py detect                   # read codename/arch from ADB device
python3 romforge.py versions                 # list supported Android versions
python3 romforge.py status      [--workdir]  # show pipeline state for a workdir
python3 romforge.py clear-cache              # clear GitHub API response cache
```

## GitHub token (important)

Without a token the GitHub API allows 60 requests/hr per IP. A typical
device tree search fires 8–10 requests; add kernel + recovery searches and
you hit the limit within a single session.

With a token: 5,000 req/hr. Set it once:

```bash
# Option 1: environment variable (best for CI)
export GITHUB_TOKEN=ghp_...

# Option 2: stored permanently (set once in TUI Settings, or:)
python3 -c "import github_client; github_client.set_token('ghp_...')"
# stored at ~/.config/romforge/github_token (chmod 600)
```

No scopes needed — public repository read access only.

API responses are also cached to `~/.cache/romforge/api/` for 1 hour
(search results) / 24 hours (release info), so repeated searches within
a session are free regardless of token status.

## Background mode (`--background`)

```bash
python3 romforge.py build --version 14 --codename angler ... --background
```

Re-launches itself in a `tmux` session named `romforge` (falls back to
`nohup` if tmux isn't installed). The build survives:
- Closing the terminal window
- SSH disconnects
- Screen lock / sleep

Reattach at any time: `tmux attach -t romforge`
View log file: `tail -f ./romforge-14-angler.log`
Kill the build: `tmux kill-session -t romforge`

Install tmux: `sudo apt install tmux`

## Resume / incremental builds

romforge writes a state file (`.romforge_state.json`) to the workdir after
each step completes. On re-run, completed steps are skipped automatically:

```
  ✓  repo sync
  ✓  device trees (device, vendor)
  ✗  customizations
  ✗  build
```

Force a full rebuild: `--rebuild`
Check state without building: `python3 romforge.py status --workdir ./romforge-src`

## Pure AOSP vs LineageOS source — and patching AOSP with specific Lineage changes

`--source lineage` syncs LineageOS's own manifest (`github.com/LineageOS/android.git`
for Android 7+, `github.com/CyanogenMod/android.git` for Android 4–6 — these
are separate orgs with incompatible branches, handled automatically per
version). This is the entire OS source tree with Lineage's patches already
integrated into every repo's history — not a lightweight layer on top of AOSP.

`--source aosp` syncs Google's raw manifest instead. **There is no bulk
"apply all of LineageOS's patches" operation** — LineageOS's manifest
already *is* that result, built up repo-by-repo over years. Re-deriving it
as a patch set onto AOSP would just reinvent what `--source lineage` gives
you directly.

What IS real: cherry-picking **specific, individually chosen** LineageOS
Gerrit changes onto whatever tree you synced (AOSP or Lineage) — the same
mechanism LineageOS's own `repopick` tool uses internally:

```bash
python3 romforge.py build --version 14 --codename angler --source aosp \
  --gerrit-patch 65062 --gerrit-patch 70001 \
  --dry-run
```

Find change numbers by browsing `review.lineageos.org`. Each patch is
looked up via Gerrit's REST API, then applied with
`git fetch <project> <ref> && git cherry-pick FETCH_HEAD`. Patches applied
onto a **vanilla AOSP** tree may conflict — they were written against
LineageOS's own diverged history, not against AOSP directly — so this is
closer to an expert/manual workflow than a guaranteed one-liner. Applied
patches are recorded in the resume state file, so re-running skips ones
already applied.

## GApps

For Android 9+ (API 29+) with NikGapps:
- Pick a variant: `core` / `basic` / `omni` / `stock` / `full`
- romforge generates a **working** `vendor/romforge_gapps/Android.mk` so the
  build system actually includes the package
- Download the zip manually from SourceForge (NikGapps has no stable API):
  `sourceforge.net/projects/nikgapps/files/Releases/Android-{ver}/`
- Place it at `vendor/romforge_gapps/NikGapps.zip`
- Add to your device's `BoardConfig.mk`:
  `PRODUCT_SOONG_NAMESPACES += vendor/romforge_gapps`
- Per-app control: edit `nikgapps.config` in the zip (`PackageName=0/1/2`)

For Android 4–8: flash GApps separately after installing the ROM.
In-tree GApps integration for old versions is fragile and not worth it.

## Backends

**local** (default) — runs `repo sync`, `lunch`, `mka bacon` directly on
this machine. Requires Ubuntu 22.04 (or equivalent), 150GB+ free disk,
16GB+ RAM, the AOSP build deps listed in `requirements.txt`. After a
successful build, prints the path to the flashable `.zip`.

**docker** — generates `Dockerfile.romforge` with all build deps and runs
the build in a container with the workdir bind-mounted. Still needs
150GB+ disk allocated to Docker.

**github-actions** — generates `.github/workflows/romforge-build.yml`.
Nothing runs locally. Push it, trigger from the Actions tab or
`gh workflow run romforge-build.yml`. Free runners have ~14GB disk and
a 6hr limit — use a self-hosted runner for full AOSP builds.

## Build pipeline steps

```
[1/5] repo sync        — repo init + repo sync (auto-retry 3×)
[2/5] tree cloning     — device, vendor, kernel, recovery trees
[3/5] customizations   — GApps, custom APKs/wallpapers, boot animation, init.d
[4/5] build            — lunch + mka bacon
[5/5] root             — Magisk boot.img patch (manual step — see output)
```

## Honest limitations

- **Android 4–6**: rated archival. Toolchains from this era don't build on
  modern Ubuntu without a container running 14.04/16.04. Device trees are
  largely dead. Expect manual repair regardless.
- **No device list**: device trees are searched live on GitHub. Coverage
  depends entirely on what's public and maintained for your specific device.
- **Device tree quality**: romforge finds and clones a tree; it cannot fix
  a tree that's out of date, missing blobs, or has broken sepolicy.
- **Radio firmware**: completely separate from the ROM build. Lives in its
  own partition, shipped by the carrier/OEM. Flash separately from a stock
  OTA. Without a matching radio your device has no cellular/GPS/Wi-Fi.
- **SELinux**: policy mismatches are the most common cause of "boots but
  some apps crash". Don't set `SELinux=permissive` in production (security
  regression). Use `adb logcat | grep avc` + `audit2allow` to fix properly.
- **150GB+ disk is real**: the tool checks and warns, but cannot make the
  build fit in less space.

## Verified sources (July 2026)

- AOSP branch model: source.android.com/docs/setup/download
- LineageOS EOL policy: lineageos.org/Changelog-31, wiki.lineageos.org/faq
- NikGapps variants: nikgapps.com/build
- GitHub API rate limits: docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- tmux background launch: man tmux (new-session -d -s)
