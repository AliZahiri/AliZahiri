#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape


GRAPHQL_URL = "https://api.github.com/graphql"
BLUE_PALETTE = ("#2f81f7", "#1f6feb", "#58a6ff", "#79c0ff", "#388bfd", "#0969da")


@dataclass(frozen=True)
class ActivityCounts:
    commits: int
    issues: int
    pull_requests: int
    code_reviews: int

    @property
    def total(self) -> int:
        return self.commits + self.issues + self.pull_requests + self.code_reviews

    def percentages(self) -> dict[str, int]:
        if self.total == 0:
            return {
                "commits": 0,
                "issues": 0,
                "pull_requests": 0,
                "code_reviews": 0,
            }
        return {
            "commits": round(self.commits / self.total * 100),
            "issues": round(self.issues / self.total * 100),
            "pull_requests": round(self.pull_requests / self.total * 100),
            "code_reviews": round(self.code_reviews / self.total * 100),
        }


@dataclass(frozen=True)
class TopLanguage:
    name: str
    size: int


def fetch_activity_counts(username: str, token: str, days: int) -> ActivityCounts:
    now = datetime.now(UTC)
    variables = {
        "login": username,
        "from": (now - timedelta(days=days)).isoformat(),
        "to": now.isoformat(),
    }
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AliZahiri-profile-activity-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    collection = body["data"]["user"]["contributionsCollection"]
    return ActivityCounts(
        commits=collection["totalCommitContributions"],
        issues=collection["totalIssueContributions"],
        pull_requests=collection["totalPullRequestContributions"],
        code_reviews=collection["totalPullRequestReviewContributions"],
    )


def fetch_top_languages(username: str, token: str) -> list[TopLanguage]:
    variables = {"login": username}
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(
          first: 100
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          nodes {
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AliZahiri-profile-activity-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if body.get("errors"):
        raise RuntimeError(body["errors"])

    totals: dict[str, int] = {}
    repositories = body["data"]["user"]["repositories"]["nodes"]
    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]

    return [
        TopLanguage(name=name, size=size)
        for name, size in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:5]
        if size > 0
    ]


def clamp_axis(value: int, radius: int) -> int:
    return round(radius * max(0, min(100, value)) / 100)


def render_svg(counts: ActivityCounts, username: str, days: int) -> str:
    percentages = counts.percentages()
    center_x = 180
    center_y = 110
    horizontal_radius = 126
    vertical_radius = 82
    commits_x = center_x - clamp_axis(percentages["commits"], horizontal_radius)
    issues_x = center_x + clamp_axis(percentages["issues"], horizontal_radius)
    reviews_y = center_y - clamp_axis(percentages["code_reviews"], vertical_radius)
    prs_y = center_y + clamp_axis(percentages["pull_requests"], vertical_radius)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d UTC")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="title desc">
  <title id="title">GitHub activity focus radar for {escape(username)}</title>
  <desc id="desc">Activity focus for the last {days} days: {counts.commits} commits, {counts.issues} issues, {counts.pull_requests} pull requests, and {counts.code_reviews} code reviews.</desc>
  <!-- Generated from GitHub contribution data at {generated_at}. -->
  <defs>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <rect width="360" height="220" rx="10" fill="#0d1117" />

  <g stroke="#1f6feb" stroke-linecap="round">
    <line x1="{center_x}" y1="28" x2="{center_x}" y2="192" stroke-width="2" opacity="0.95" />
    <line x1="54" y1="{center_y}" x2="306" y2="{center_y}" stroke-width="2" opacity="0.95" />
    <line x1="{commits_x}" y1="{center_y}" x2="{issues_x}" y2="{center_y}" stroke-width="9" opacity="0.18" filter="url(#glow)" />
    <line x1="{commits_x}" y1="{center_y}" x2="{issues_x}" y2="{center_y}" stroke-width="4" opacity="0.72" filter="url(#glow)" />
    <line x1="{center_x}" y1="{reviews_y}" x2="{center_x}" y2="{prs_y}" stroke-width="4" opacity="0.35" filter="url(#glow)" />
  </g>

  <g fill="#0d1117" stroke="#58a6ff" stroke-width="3" filter="url(#glow)">
    <circle cx="{commits_x}" cy="{center_y}" r="4" />
    <circle cx="{center_x}" cy="{center_y}" r="5" />
    <circle cx="{issues_x}" cy="{center_y}" r="4" />
    <circle cx="{center_x}" cy="{reviews_y}" r="3" />
    <circle cx="{center_x}" cy="{prs_y}" r="3" />
  </g>

  <g fill="#8b949e" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="13">
    <text x="{center_x}" y="18" text-anchor="middle" fill="#9fb3c8">Code review</text>
    <text x="{center_x}" y="213" text-anchor="middle" fill="#9fb3c8">Pull requests</text>
    <text x="48" y="106" text-anchor="middle">{percentages["commits"]}%</text>
    <text x="48" y="124" text-anchor="middle" fill="#9fb3c8">Commits</text>
    <text x="314" y="106" text-anchor="middle">{percentages["issues"]}%</text>
    <text x="314" y="124" text-anchor="middle" fill="#9fb3c8">Issues</text>
    <text x="{center_x}" y="37" text-anchor="middle">{percentages["code_reviews"]}%</text>
    <text x="{center_x}" y="198" text-anchor="middle">{percentages["pull_requests"]}%</text>
  </g>

  <g fill="#6e7681" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="10">
    <text x="180" y="94" text-anchor="middle">last {days} days</text>
  </g>
</svg>
"""


def render_donut_segments(languages: list[TopLanguage], radius: int = 42) -> str:
    total = sum(language.size for language in languages)
    if total == 0:
        return """    <circle cx="250" cy="112" r="42" fill="transparent" stroke="#161b22" stroke-width="22" />"""

    circumference = 2 * math.pi * radius
    offset = 0.0
    segments = []
    for index, language in enumerate(languages):
        length = circumference * language.size / total
        gap = 1.5 if len(languages) > 1 else 0
        visible_length = max(0, length - gap)
        color = BLUE_PALETTE[index % len(BLUE_PALETTE)]
        segments.append(
            f"""    <circle cx="250" cy="112" r="{radius}" fill="transparent" stroke="{color}" stroke-width="22" """
            f"""stroke-dasharray="{visible_length:.2f} {circumference - visible_length:.2f}" """
            f"""stroke-dashoffset="-{offset:.2f}" stroke-linecap="butt" transform="rotate(-90 250 112)" />"""
        )
        offset += length
    return "\n".join(segments)


def render_language_rows(languages: list[TopLanguage]) -> str:
    total = sum(language.size for language in languages)
    if total == 0:
        return """    <text x="64" y="116" fill="#8b949e">No public language data yet</text>"""

    rows = []
    for index, language in enumerate(languages[:5]):
        y = 92 + index * 22
        percentage = round(language.size / total * 100)
        color = BLUE_PALETTE[index % len(BLUE_PALETTE)]
        rows.append(
            f"""    <rect x="64" y="{y - 9}" width="10" height="10" rx="2" fill="{color}" />\n"""
            f"""    <text x="84" y="{y}" fill="#c9d1d9">{escape(language.name)}</text>\n"""
            f"""    <text x="176" y="{y}" fill="#8b949e" text-anchor="end">{percentage}%</text>"""
        )
    return "\n".join(rows)


def render_top_languages_svg(languages: list[TopLanguage], username: str) -> str:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d UTC")
    language_summary = ", ".join(f"{language.name}: {language.size}" for language in languages)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="title desc">
  <title id="title">Top commit languages for {escape(username)}</title>
  <desc id="desc">Top public repository languages by byte size. {escape(language_summary)}</desc>
  <!-- Generated from GitHub repository language data at {generated_at}. -->
  <defs>
    <filter id="soft-glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="2.5" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <rect width="360" height="220" rx="10" fill="#0d1117" />
  <text x="64" y="40" fill="#2f81f7" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="20" font-weight="600">Top Languages</text>

  <g font-family="Inter, Segoe UI, Arial, sans-serif" font-size="13">
{render_language_rows(languages)}
  </g>

  <g filter="url(#soft-glow)">
    <circle cx="250" cy="112" r="42" fill="transparent" stroke="#161b22" stroke-width="22" />
{render_donut_segments(languages)}
    <circle cx="250" cy="112" r="25" fill="#0d1117" />
  </g>
</svg>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the profile activity focus SVG.")
    parser.add_argument("--username", default=os.environ.get("GITHUB_USERNAME", "AliZahiri"))
    parser.add_argument("--days", type=int, default=int(os.environ.get("GITHUB_ACTIVITY_DAYS", "365")))
    parser.add_argument("--output", default="assets/github-activity-focus.svg")
    parser.add_argument("--language-output", default="assets/github-top-languages.svg")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Render deterministic sample data without calling the GitHub API.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample:
        counts = ActivityCounts(commits=76, issues=21, pull_requests=2, code_reviews=1)
        languages = [TopLanguage(name="Python", size=76), TopLanguage(name="Shell", size=24)]
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("GITHUB_TOKEN or GH_TOKEN is required unless --sample is used", file=sys.stderr)
            return 2
        counts = fetch_activity_counts(args.username, token, args.days)
        languages = fetch_top_languages(args.username, token)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(counts, args.username, args.days), encoding="utf-8")

    language_output = Path(args.language_output)
    language_output.parent.mkdir(parents=True, exist_ok=True)
    language_output.write_text(render_top_languages_svg(languages, args.username), encoding="utf-8")

    print(f"Generated {output} from {counts.total} contributions")
    print(f"Generated {language_output} from {len(languages)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
