"""
romforge.device_resolver
=========================
Finds device trees, vendor blob repos, and kernel trees for a given device
codename by searching GitHub -- rather than relying on a hardcoded list,
which would be stale the day it was written.

Also supports pulling the codename automatically from a connected device
over ADB (read-only `getprop` calls; never pushes/installs anything).
"""

import json
import shutil
import subprocess
import urllib.request
import urllib.parse
from dataclasses import dataclass

from config import (DEVICE_TREE_ORGS, DEVICE_TREE_SEARCH_TEMPLATES,
                     KERNEL_SEARCH_TEMPLATES, TWEAK_MODULE_ORGS, TWEAK_SEARCH_TEMPLATES)


@dataclass
class RepoCandidate:
    full_name: str
    html_url: str
    clone_url: str
    stars: int
    pushed_at: str
    kind: str          # "device" | "vendor" | "kernel" | "unknown"
    exact_match: bool  # codename appears as a whole _-or-/-delimited token, not just a substring
    vendor_match: bool  # vendor_hint appears as a whole token too (True if no hint was given)


def detect_connected_device() -> dict | None:
    """
    Read-only ADB probe. Returns {codename, vendor, arch, android_version}
    or None if no device / adb unavailable. Never writes to the device.
    """
    if shutil.which("adb") is None:
        return None
    try:
        subprocess.run(["adb", "start-server"], capture_output=True, timeout=10)
        devices = subprocess.run(["adb", "devices"], capture_output=True,
                                  text=True, timeout=10).stdout
        if "device\n" not in devices and "\tdevice" not in devices:
            return None

        def getprop(prop):
            out = subprocess.run(["adb", "shell", "getprop", prop],
                                  capture_output=True, text=True, timeout=10)
            return out.stdout.strip()

        codename = getprop("ro.product.device") or getprop("ro.build.product")
        vendor = getprop("ro.product.manufacturer")
        abi = getprop("ro.product.cpu.abi")
        release = getprop("ro.build.version.release")

        arch = "arm64" if "arm64" in abi else (
               "armv7" if "armeabi" in abi else (
               "x86_64" if "x86_64" in abi else (
               "x86" if "x86" in abi else "unknown")))

        if not codename:
            return None
        return {
            "codename": codename,
            "vendor": vendor.lower() if vendor else "unknown",
            "arch": arch,
            "android_version": release,
        }
    except (subprocess.SubprocessError, OSError):
        return None


def _github_api(path: str) -> dict:
    """
    Minimal unauthenticated GitHub API GET. Subject to GitHub's anonymous
    rate limit (60 req/hr) -- fine for occasional lookups, not for scripted
    bulk scraping. Set GITHUB_TOKEN env var support could be added later
    if that becomes a problem for a given user.
    """
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "romforge"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _name_tokens(repo_name: str) -> list[str]:
    """Split a repo name into tokens on the separators device trees actually
    use (underscore, hyphen), lowercased. 'android_device_archos_ac50hello'
    -> ['android', 'device', 'archos', 'ac50hello']. This is what lets us
    tell a real codename match from "hello" merely being a substring of
    "ac50hello"."""
    import re
    return [t for t in re.split(r"[_\-]+", repo_name.lower()) if t]


def _search_repos(queries: list[str], match_token: str, vendor_token: str | None,
                    kind_keywords: dict[str, list[str]]) -> list[RepoCandidate]:
    """
    Shared GitHub search + ranking logic used by search_device_trees,
    search_kernel_trees, and search_tweak_modules. match_token is checked
    as a whole _-or-/-delimited token in the repo name (not a substring)
    to avoid false positives like codename "hello" matching "...ac50hello".
    kind_keywords maps a label (e.g. "device", "kernel", "vendor") to a
    list of substrings that, if found in the repo name, assign that label.
    """
    candidates: list[RepoCandidate] = []
    seen = set()
    match_lower = match_token.lower()
    vendor_lower = (vendor_token or "").lower()

    for q in queries:
        try:
            encoded = urllib.parse.quote(q)
            data = _github_api(f"/search/repositories?q={encoded}&sort=stars&order=desc&per_page=5")
        except Exception:
            continue  # network/rate-limit issue on this query; keep going
        for item in data.get("items", []):
            full_name = item["full_name"]
            if full_name in seen:
                continue
            seen.add(full_name)
            name_lower = item["name"].lower()
            tokens = _name_tokens(item["name"])

            kind = "unknown"
            for label, keywords in kind_keywords.items():
                if any(kw in name_lower for kw in keywords):
                    kind = label
                    break

            exact_match = match_lower in tokens
            vendor_match = (not vendor_lower) or (vendor_lower in tokens)

            candidates.append(RepoCandidate(
                full_name=full_name,
                html_url=item["html_url"],
                clone_url=item["clone_url"],
                stars=item.get("stargazers_count", 0),
                pushed_at=item.get("pushed_at", ""),
                kind=kind,
                exact_match=exact_match,
                vendor_match=vendor_match,
            ))

    candidates.sort(key=lambda c: (c.exact_match, c.vendor_match, c.stars, c.pushed_at), reverse=True)
    return candidates


def search_device_trees(codename: str, vendor_hint: str | None = None) -> list[RepoCandidate]:
    """
    Search GitHub for device trees / vendor blobs matching a codename.
    Tries the configured orgs first (higher trust), then falls back to a
    general code/repo search. Results are NOT auto-trusted -- the caller
    should let the user confirm before cloning, since repo quality and
    intent vary a lot.
    """
    queries = [f"org:{org} {codename} in:name" for org in DEVICE_TREE_ORGS]
    vendor = vendor_hint or ""
    for template in DEVICE_TREE_SEARCH_TEMPLATES:
        queries.append(template.format(vendor=vendor, codename=codename).strip())

    return _search_repos(
        queries, match_token=codename, vendor_token=vendor_hint,
        kind_keywords={"vendor": ["vendor", "proprietary"],
                       "kernel": ["kernel"],
                       "device": ["device"]},
    )


def search_kernel_trees(codename: str, vendor_hint: str | None = None) -> list[RepoCandidate]:
    """
    Search GitHub specifically for KERNEL trees for a device. Kept separate
    from search_device_trees because a device commonly has several
    competing community kernel forks worth choosing between (unlike the
    device tree itself, which is usually closer to 1:1), and kernel repos
    use a different naming convention (kernel_<vendor>_<codename> etc.).
    """
    queries = [f"org:{org} {codename} kernel in:name" for org in DEVICE_TREE_ORGS]
    vendor = vendor_hint or ""
    for template in KERNEL_SEARCH_TEMPLATES:
        queries.append(template.format(vendor=vendor, codename=codename).strip())

    return _search_repos(
        queries, match_token=codename, vendor_token=vendor_hint,
        kind_keywords={"kernel": ["kernel"]},
    )


def search_tweak_modules(query: str) -> list[RepoCandidate]:
    """
    Search GitHub for Magisk/KernelSU module repositories matching a
    free-text query (e.g. "viper4android", "fontfix", "adaway"). Unlike
    device/kernel trees, there's no single codename to exact-match against
    here, so exact_match is set True for every result and vendor_match is
    always True -- ranking falls back to stars/recency, and the person
    should read each module's README before trusting it, same caution as
    vendor blob repos.
    """
    queries = [f"org:{org} {query} in:name" for org in TWEAK_MODULE_ORGS]
    for template in TWEAK_SEARCH_TEMPLATES:
        queries.append(template.format(query=query).strip())

    candidates: list[RepoCandidate] = []
    seen = set()
    for q in queries:
        try:
            encoded = urllib.parse.quote(q)
            data = _github_api(f"/search/repositories?q={encoded}&sort=stars&order=desc&per_page=5")
        except Exception:
            continue
        for item in data.get("items", []):
            full_name = item["full_name"]
            if full_name in seen:
                continue
            seen.add(full_name)
            candidates.append(RepoCandidate(
                full_name=full_name,
                html_url=item["html_url"],
                clone_url=item["clone_url"],
                stars=item.get("stargazers_count", 0),
                pushed_at=item.get("pushed_at", ""),
                kind="tweak",
                exact_match=True,
                vendor_match=True,
            ))
    candidates.sort(key=lambda c: (c.stars, c.pushed_at), reverse=True)
    return candidates


def print_candidates(candidates: list[RepoCandidate]) -> None:
    if not candidates:
        print("  No candidates found. Device tree may not exist publicly, "
              "or GitHub search rate-limited this lookup -- try again "
              "shortly, or supply a tree URL manually.")
        return
    for i, c in enumerate(candidates, 1):
        flag = "exact" if c.exact_match else "PARTIAL/substring match -- verify before using"
        print(f"  [{i}] ({c.kind:<7}) {c.full_name}  ★{c.stars}  pushed {c.pushed_at}  [{flag}]")
        print(f"        {c.html_url}")
