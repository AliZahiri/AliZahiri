#!/usr/bin/env python3
from __future__ import annotations

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
    "assets/github-top-languages.svg",
)


def profile_readme_warnings(content: str) -> tuple[str, ...]:
    warnings: list[str] = []
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
        if not (ROOT / asset).exists():
            warnings.append(f"missing_asset_file:{asset}")
    return tuple(warnings)


def main() -> int:
    content = README.read_text(encoding="utf-8")
    warnings = profile_readme_warnings(content)
    for warning in warnings:
        print(f"profile-readme-warning: {warning}")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
