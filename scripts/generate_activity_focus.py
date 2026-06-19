#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape


GRAPHQL_URL = "https://api.github.com/graphql"


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

  <g stroke="#39d353" stroke-linecap="round">
    <line x1="{center_x}" y1="28" x2="{center_x}" y2="192" stroke-width="2" opacity="0.95" />
    <line x1="54" y1="{center_y}" x2="306" y2="{center_y}" stroke-width="2" opacity="0.95" />
    <line x1="{commits_x}" y1="{center_y}" x2="{issues_x}" y2="{center_y}" stroke-width="9" opacity="0.18" filter="url(#glow)" />
    <line x1="{commits_x}" y1="{center_y}" x2="{issues_x}" y2="{center_y}" stroke-width="4" opacity="0.72" filter="url(#glow)" />
    <line x1="{center_x}" y1="{reviews_y}" x2="{center_x}" y2="{prs_y}" stroke-width="4" opacity="0.35" filter="url(#glow)" />
  </g>

  <g fill="#0d1117" stroke="#7ee787" stroke-width="3" filter="url(#glow)">
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the profile activity focus SVG.")
    parser.add_argument("--username", default=os.environ.get("GITHUB_USERNAME", "AliZahiri"))
    parser.add_argument("--days", type=int, default=int(os.environ.get("GITHUB_ACTIVITY_DAYS", "365")))
    parser.add_argument("--output", default="assets/github-activity-focus.svg")
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
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("GITHUB_TOKEN or GH_TOKEN is required unless --sample is used", file=sys.stderr)
            return 2
        counts = fetch_activity_counts(args.username, token, args.days)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(counts, args.username, args.days), encoding="utf-8")
    print(f"Generated {output} from {counts.total} contributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
