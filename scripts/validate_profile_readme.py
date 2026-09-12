#!/usr/bin/env python3
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
REQUIRED_SECTIONS = (
    "## GitHub Activity",
    "## What I Work On",
    "## Focus Areas",
    "## Project Map",
    "### Featured Portfolio Systems",
    "## Current Direction",
)
REQUIRED_PROJECTS = (
    "ai-rag-platform-blueprint",
    "gitlab-ci-compose-zero-downtime",
    "kong-deck-compose-gateway",
    "ansible-linux-ops-bootstrap",
)
REQUIRED_ENGINEERING_ENTRY_POINTS = (
    "https://github.com/AliZahiri/ai-rag-platform-blueprint/blob/main/docs/architecture.md",
    "https://github.com/AliZahiri/gitlab-ci-compose-zero-downtime/blob/main/docs/zero-downtime-compose.md",
    "https://github.com/AliZahiri/kong-deck-compose-gateway/blob/main/docs/zero-downtime-kong-deck.md",
    "https://github.com/AliZahiri/ansible-linux-ops-bootstrap/blob/main/docs/hardening-checklist.md",
)
REQUIRED_ASSETS = (
    "assets/devops-platform-architect.png",
    "assets/github-activity-focus.svg",
    "assets/github-activity-counts.svg",
    "assets/github-top-languages.svg",
)
ACTIVITY_ASSETS = REQUIRED_ASSETS[1:]
REQUIRED_ACTIVITY_CADENCE = "refreshed every six hours"
REQUIRED_POSITIONING = "Designing scalable and reliable cloud and on-prem platforms."
REQUIRED_CONTACT = "https://www.linkedin.com/in/zahiri/"


def activity_section(content: str) -> str:
    start = content.find("## GitHub Activity")
    if start == -1:
        return ""
    end = content.find("\n## ", start + 1)
    return content[start:] if end == -1 else content[start:end]


def profile_readme_warnings(content: str) -> tuple[str, ...]:
    warnings: list[str] = []
    if REQUIRED_POSITIONING not in content:
        warnings.append("missing_platform_positioning")
    if REQUIRED_CONTACT not in content:
        warnings.append("missing_linkedin_contact")
    for section in REQUIRED_SECTIONS:
        if section not in content:
            warnings.append(f"missing_section:{section}")
    for project in REQUIRED_PROJECTS:
        if f"https://github.com/AliZahiri/{project}" not in content:
            warnings.append(f"missing_project_link:{project}")
    for entry_point in REQUIRED_ENGINEERING_ENTRY_POINTS:
        if entry_point not in content:
            warnings.append(f"missing_engineering_entry_point:{entry_point}")
    for asset in REQUIRED_ASSETS:
        if asset not in content:
            warnings.append(f"missing_asset_reference:{asset}")
        asset_path = ROOT / asset
        if not asset_path.exists():
            warnings.append(f"missing_asset_file:{asset}")
        elif asset_path.suffix == ".svg":
            if asset_path.stat().st_size < 500:
                warnings.append(f"invalid_svg_too_small:{asset}")
                continue
            try:
                root = ET.parse(asset_path).getroot()
            except ET.ParseError:
                warnings.append(f"invalid_svg_xml:{asset}")
                continue
            if root.tag != "{http://www.w3.org/2000/svg}svg":
                warnings.append(f"invalid_svg_root:{asset}")

    section = activity_section(content)
    if REQUIRED_ACTIVITY_CADENCE not in section:
        warnings.append(
            f"activity_cadence:expected={REQUIRED_ACTIVITY_CADENCE}"
        )
    image_count = len(re.findall(r"<img\b", section))
    if image_count != 3:
        warnings.append(f"activity_chart_count:expected=3:actual={image_count}")
    local_activity_images = re.findall(
        r'<img\b[^>]*\bsrc="(assets/github-[^"]+\.svg)"', section
    )
    if tuple(local_activity_images) != ACTIVITY_ASSETS:
        warnings.append(
            "activity_chart_order_or_count:expected=" + ",".join(ACTIVITY_ASSETS)
        )
    return tuple(warnings)


def main() -> int:
    content = README.read_text(encoding="utf-8")
    warnings = profile_readme_warnings(content)
    for warning in warnings:
        print(f"profile-readme-warning: {warning}")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
