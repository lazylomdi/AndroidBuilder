#!/usr/bin/env python3
"""Offline-first Ubuntu Touch readiness assessment for AndroidBuilder."""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STATUSES = {"VERIFIED", "CANDIDATE", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"}

@dataclass(frozen=True)
class Finding:
    key: str
    value: Any
    status: str
    evidence: str
    next_step: str = ""
    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid status: {self.status}")

def assess_device(manufacturer: str | None, model: str | None, ram_gb: float | None,
                  codename: str | None = None, android_version: str | None = None,
                  kernel_version: str | None = None, bootloader_unlock: str | None = None) -> dict[str, Any]:
    """Build a conservative assessment from user-supplied facts only."""
    findings: list[Finding] = []
    supplied = {"manufacturer": manufacturer, "model": model, "ram_gb": ram_gb,
                "codename": codename, "android_version": android_version,
                "kernel_version": kernel_version, "bootloader_unlock": bootloader_unlock}
    for key, value in supplied.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            findings.append(Finding(key, None, "UNKNOWN", "Not provided.",
                "Research or obtain this device-specific information."))
        else:
            findings.append(Finding(key, value, "CANDIDATE",
                "User-provided input; not independently verified.",
                "Verify against manufacturer documentation or a trustworthy device source."))
    for key in ("kernel_source", "device_tree", "vendor_blobs", "halium_base",
                "bootloader_unlock_eligibility", "existing_ubuntu_touch_port",
                "hardware_functionality", "partition_layout"):
        findings.append(Finding(key, None, "UNKNOWN", "No independently verified evidence collected.",
            "Research authoritative sources; physical testing may be required."))
    missing_core = [f.key for f in findings if f.key in {
        "codename", "android_version", "kernel_version", "bootloader_unlock"
    } and f.status == "UNKNOWN"]
    return {
        "schema_version": 1,
        "assessment": "UNKNOWN" if missing_core else "CANDIDATE",
        "device": supplied,
        "readiness_claim": "No functional Ubuntu Touch port is established by this report.",
        "physical_device_available": False,
        "findings": [asdict(f) for f in findings],
        "missing_core_information": missing_core,
        "limitations": [
            "This report is based on user-supplied data and offline rules only.",
            "Repository existence does not prove that sources build or support hardware.",
            "Compilation does not prove bootability or working hardware features.",
            "No device was connected, flashed, or physically tested."
        ]
    }

def render_markdown(report: dict[str, Any]) -> str:
    device = report["device"]
    label = " ".join(str(device[k]) for k in ("manufacturer", "model") if device.get(k)) or "Unspecified device"
    lines = [f"# Ubuntu Touch readiness report: {label}", "",
        f"- **Assessment:** {report['assessment']}",
        f"- **RAM (reported):** {device.get('ram_gb') if device.get('ram_gb') is not None else 'Unknown'} GB",
        f"- **Physical device available:** {report['physical_device_available']}",
        f"- **Conclusion:** {report['readiness_claim']}", "",
        "## Findings", "", "| Area | Value | Status | Evidence |", "|---|---|---|---|"]
    def safe(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    for item in report["findings"]:
        value = "Unknown" if item["value"] is None else str(item["value"])
        lines.append(f"| {safe(item['key'])} | {safe(value)} | {item['status']} | {safe(item['evidence'])} |")
    lines.extend(["", "## Missing core information", ""])
    lines.extend([f"- `{key}`" for key in report["missing_core_information"]] or ["- None recorded by this rule set."])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)

def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number greater than zero") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a number greater than zero")
    return parsed

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="romforge.py ut-check",
        description="Assess Ubuntu Touch port readiness without a connected phone.")
    parser.add_argument("--manufacturer", default="Sony")
    parser.add_argument("--model", default="Xperia R1")
    parser.add_argument("--ram-gb", type=_positive_float, default=2.0)
    parser.add_argument("--codename")
    parser.add_argument("--android-version")
    parser.add_argument("--kernel-version")
    parser.add_argument("--bootloader-unlock", choices=["yes", "no", "unknown"], default="unknown")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = assess_device(args.manufacturer, args.model, args.ram_gb, args.codename,
        args.android_version, args.kernel_version,
        None if args.bootloader_unlock == "unknown" else args.bootloader_unlock)
    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    markdown_text = render_markdown(report)
    try:
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json_text, encoding="utf-8")
        if args.markdown_out:
            args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_out.write_text(markdown_text, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write report: {exc}", file=sys.stderr)
        return 2
    if not args.json_out and not args.markdown_out:
        print(markdown_text, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
