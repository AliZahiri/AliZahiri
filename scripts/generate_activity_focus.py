#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


GRAPHQL_URL = "https://api.github.com/graphql"
BACKGROUND = "#0D1117"
DEEP_NAVY = "#0B1F3A"
PRIMARY_BLUE = "#1F6FEB"
BRIGHT_BLUE = "#4EA1FF"
GOLD = "#F2B84B"
DEEP_GOLD = "#D99500"
WHITE = "#F5F7FA"
MUTED_TEXT = "#AAB4C3"
TRACK = "#081B33"
FONT_FAMILY = "Inter, Segoe UI, Arial, sans-serif"


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
class ActivitySummary:
    total_stars: int
    year_commits: int
    total_pull_requests: int
    total_issues: int
    contributed_to: int
    year: int


@dataclass(frozen=True)
class TopLanguage:
    name: str
    size: int


def github_graphql(
    query: str,
    variables: dict[str, Any],
    token: str,
    attempts: int = 3,
) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            GRAPHQL_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "AliZahiri-profile-activity-generator",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            if body.get("errors"):
                messages = "; ".join(
                    str(error.get("message", error)) for error in body["errors"]
                )
                raise RuntimeError(f"GitHub GraphQL error: {messages}")
            data = body.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("GitHub GraphQL response did not contain data")
            return data
        except Exception as error:  # urllib and malformed/API responses share retry policy
            last_error = error
            if attempt < attempts:
                delay = 2 ** (attempt - 1)
                print(
                    f"GitHub API request failed (attempt {attempt}/{attempts}); "
                    f"retrying in {delay}s: {error}",
                    file=sys.stderr,
                )
                time.sleep(delay)

    raise RuntimeError(f"GitHub API request failed after {attempts} attempts: {last_error}")


def fetch_activity_data(
    username: str, token: str, days: int
) -> tuple[ActivityCounts, ActivitySummary]:
    now = datetime.now(UTC)
    variables = {
        "login": username,
        "activityFrom": (now - timedelta(days=days)).isoformat(),
        "yearFrom": datetime(now.year, 1, 1, tzinfo=UTC).isoformat(),
        "to": now.isoformat(),
    }
    query = """
    query(
      $login: String!
      $activityFrom: DateTime!
      $yearFrom: DateTime!
      $to: DateTime!
    ) {
      user(login: $login) {
        activity: contributionsCollection(from: $activityFrom, to: $to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
        currentYear: contributionsCollection(from: $yearFrom, to: $to) {
          totalCommitContributions
        }
        pullRequests(first: 1) {
          totalCount
        }
        issues(first: 1) {
          totalCount
        }
        repositoriesContributedTo(
          first: 1
          includeUserRepositories: true
          privacy: PUBLIC
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) {
          totalCount
        }
      }
    }
    """
    data = github_graphql(query, variables, token)
    user = data.get("user")
    if not isinstance(user, dict):
        raise RuntimeError(f"GitHub user {username!r} was not found")

    activity = user["activity"]
    counts = ActivityCounts(
        commits=activity["totalCommitContributions"],
        issues=activity["totalIssueContributions"],
        pull_requests=activity["totalPullRequestContributions"],
        code_reviews=activity["totalPullRequestReviewContributions"],
    )
    summary = ActivitySummary(
        total_stars=0,
        year_commits=user["currentYear"]["totalCommitContributions"],
        total_pull_requests=user["pullRequests"]["totalCount"],
        total_issues=user["issues"]["totalCount"],
        contributed_to=user["repositoriesContributedTo"]["totalCount"],
        year=now.year,
    )
    return counts, summary


def fetch_repository_data(
    username: str, token: str
) -> tuple[int, list[TopLanguage]]:
    query = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        repositories(
          first: 100
          after: $cursor
          ownerAffiliations: OWNER
          privacy: PUBLIC
          isFork: false
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            stargazerCount
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
    cursor: str | None = None
    total_stars = 0
    language_totals: dict[str, int] = {}

    while True:
        data = github_graphql(query, {"login": username, "cursor": cursor}, token)
        user = data.get("user")
        if not isinstance(user, dict):
            raise RuntimeError(f"GitHub user {username!r} was not found")
        repositories = user["repositories"]
        for repository in repositories["nodes"]:
            total_stars += repository["stargazerCount"]
            for edge in repository["languages"]["edges"]:
                name = edge["node"]["name"]
                language_totals[name] = language_totals.get(name, 0) + edge["size"]

        page_info = repositories["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    languages = [
        TopLanguage(name=name, size=size)
        for name, size in sorted(
            language_totals.items(), key=lambda item: item[1], reverse=True
        )[:5]
        if size > 0
    ]
    return total_stars, languages


def card_background() -> str:
    return f"""  <rect x="1" y="1" width="358" height="218" rx="12" fill="{BACKGROUND}" stroke="{DEEP_NAVY}" stroke-width="2" />
  <path d="M13 1 H240" stroke="{PRIMARY_BLUE}" stroke-width="2" />
  <path d="M240 1 H300" stroke="{GOLD}" stroke-width="2" />"""


def render_activity_rows(counts: ActivityCounts) -> str:
    percentages = counts.percentages()
    rows = (
        ("Commits", percentages["commits"], PRIMARY_BLUE),
        ("Issues", percentages["issues"], GOLD),
        ("Pull requests", percentages["pull_requests"], BRIGHT_BLUE),
        ("Code review", percentages["code_reviews"], WHITE),
    )
    rendered = []
    for index, (label, percentage, color) in enumerate(rows):
        y = 78 + index * 34
        width = round(320 * percentage / 100, 1)
        if percentage and width < 2:
            width = 2
        rendered.append(
            f"""  <text x="20" y="{y}" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="12">{escape(label)}</text>
  <text x="340" y="{y}" fill="{color}" font-family="{FONT_FAMILY}" font-size="12" font-weight="600" text-anchor="end">{percentage}%</text>
  <rect x="20" y="{y + 8}" width="320" height="5" rx="2.5" fill="{TRACK}" />
  <rect x="20" y="{y + 8}" width="{width}" height="5" rx="2.5" fill="{color}" />"""
        )
    return "\n".join(rendered)


def render_activity_distribution_svg(
    counts: ActivityCounts, username: str, days: int
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="activity-title activity-desc">
  <title id="activity-title">GitHub activity distribution for {escape(username)}</title>
  <desc id="activity-desc">Last {days} days: {counts.commits} commits, {counts.issues} issues, {counts.pull_requests} pull requests, and {counts.code_reviews} code reviews.</desc>
{card_background()}
  <text x="20" y="32" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="18" font-weight="600">Activity Distribution</text>
  <text x="20" y="51" fill="{MUTED_TEXT}" font-family="{FONT_FAMILY}" font-size="10">Last {days} days · {counts.total:,} contributions</text>
{render_activity_rows(counts)}
</svg>
"""


def language_color(language: TopLanguage, index: int) -> str:
    if language.name.casefold() == "python":
        return PRIMARY_BLUE
    if language.name.casefold() == "shell":
        return GOLD
    fallback = (BRIGHT_BLUE, "#79C0FF", WHITE, MUTED_TEXT, DEEP_GOLD)
    return fallback[index % len(fallback)]


def render_donut_segments(languages: list[TopLanguage], radius: int = 45) -> str:
    total = sum(language.size for language in languages)
    if total == 0:
        return f"  <circle cx=\"282\" cy=\"130\" r=\"{radius}\" fill=\"none\" stroke=\"{TRACK}\" stroke-width=\"18\" />"

    circumference = 2 * math.pi * radius
    offset = 0.0
    segments = []
    for index, language in enumerate(languages):
        length = circumference * language.size / total
        gap = 1.5 if len(languages) > 1 else 0
        visible_length = max(0, length - gap)
        color = language_color(language, index)
        segments.append(
            f"  <circle cx=\"282\" cy=\"130\" r=\"{radius}\" fill=\"none\" stroke=\"{color}\" stroke-width=\"18\" "
            f"stroke-dasharray=\"{visible_length:.2f},{circumference - visible_length:.2f}\" "
            f"stroke-dashoffset=\"-{offset:.2f}\" transform=\"rotate(-90 282 130)\" />"
        )
        offset += length
    return "\n".join(segments)


def render_language_rows(languages: list[TopLanguage]) -> str:
    total = sum(language.size for language in languages)
    if total == 0:
        return f"  <text x=\"20\" y=\"112\" fill=\"{MUTED_TEXT}\" font-family=\"{FONT_FAMILY}\" font-size=\"12\">No public language data</text>"

    rows = []
    for index, language in enumerate(languages):
        y = 78 + index * 27
        percentage_value = language.size / total * 100
        percentage = (
            "<1%" if 0 < percentage_value < 1 else f"{round(percentage_value)}%"
        )
        color = language_color(language, index)
        rows.append(
            f"""  <circle cx="25" cy="{y - 4}" r="4" fill="{color}" />
  <text x="38" y="{y}" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="12">{escape(language.name)}</text>
  <text x="176" y="{y}" fill="{color}" font-family="{FONT_FAMILY}" font-size="12" font-weight="600" text-anchor="end">{escape(percentage)}</text>"""
        )
    return "\n".join(rows)


def render_top_languages_svg(languages: list[TopLanguage], username: str) -> str:
    language_summary = ", ".join(
        f"{language.name}: {language.size} bytes" for language in languages
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="languages-title languages-desc">
  <title id="languages-title">Top public repository languages for {escape(username)}</title>
  <desc id="languages-desc">Languages by byte size across public, owned, non-fork repositories. {escape(language_summary)}</desc>
{card_background()}
  <text x="20" y="32" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="18" font-weight="600">Top Languages</text>
  <text x="20" y="51" fill="{MUTED_TEXT}" font-family="{FONT_FAMILY}" font-size="10">Public owned repositories · by bytes</text>
{render_language_rows(languages)}
  <circle cx="282" cy="130" r="45" fill="none" stroke="{TRACK}" stroke-width="18" />
{render_donut_segments(languages)}
  <circle cx="282" cy="130" r="34" fill="{BACKGROUND}" />
  <circle cx="282" cy="130" r="3" fill="{GOLD}" />
</svg>
"""


def render_activity_summary_svg(summary: ActivitySummary, username: str) -> str:
    rows = (
        ("Total Stars", summary.total_stars),
        (f"{summary.year} Commits", summary.year_commits),
        ("Total PRs", summary.total_pull_requests),
        ("Total Issues", summary.total_issues),
        ("Contributed to", summary.contributed_to),
    )
    rendered = []
    for index, (label, value) in enumerate(rows):
        y = 76 + index * 28
        accent = GOLD if index in (0, 4) else PRIMARY_BLUE
        separator = "" if index == len(rows) - 1 else (
            f'\n  <line x1="20" y1="{y + 10}" x2="340" y2="{y + 10}" '
            f'stroke="{DEEP_NAVY}" stroke-width="1" />'
        )
        rendered.append(
            f"""  <rect x="20" y="{y - 9}" width="3" height="12" rx="1.5" fill="{accent}" />
  <text x="32" y="{y}" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="12">{escape(label)}</text>
  <text x="340" y="{y}" fill="{BRIGHT_BLUE}" font-family="{FONT_FAMILY}" font-size="14" font-weight="700" text-anchor="end">{value:,}</text>{separator}"""
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="summary-title summary-desc">
  <title id="summary-title">GitHub activity counts for {escape(username)}</title>
  <desc id="summary-desc">{summary.total_stars} total stars, {summary.year_commits} commits in {summary.year}, {summary.total_pull_requests} total pull requests, {summary.total_issues} total issues, and contributions to {summary.contributed_to} public repositories.</desc>
{card_background()}
  <text x="20" y="32" fill="{WHITE}" font-family="{FONT_FAMILY}" font-size="18" font-weight="600">Activity Counts</text>
  <text x="20" y="51" fill="{MUTED_TEXT}" font-family="{FONT_FAMILY}" font-size="10">GitHub account statistics</text>
{"\n".join(rendered)}
</svg>
"""


def validate_svg(content: str, label: str) -> None:
    if len(content.encode("utf-8")) < 500:
        raise RuntimeError(f"Refusing to write suspiciously small SVG: {label}")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise RuntimeError(f"Generated invalid SVG for {label}: {error}") from error
    if root.tag != "{http://www.w3.org/2000/svg}svg":
        raise RuntimeError(f"Generated document is not an SVG: {label}")


def write_outputs(outputs: dict[Path, str]) -> None:
    temporary_files: list[Path] = []
    try:
        for output, content in outputs.items():
            validate_svg(content, str(output))
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_name(f".{output.name}.tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary_files.append(temporary)
        for output, temporary in zip(outputs, temporary_files, strict=True):
            temporary.replace(output)
    finally:
        for temporary in temporary_files:
            temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate GitHub profile activity SVGs.")
    parser.add_argument("--username", default=os.environ.get("GITHUB_USERNAME", "AliZahiri"))
    parser.add_argument(
        "--days", type=int, default=int(os.environ.get("GITHUB_ACTIVITY_DAYS", "365"))
    )
    parser.add_argument("--output", default="assets/github-activity-focus.svg")
    parser.add_argument("--summary-output", default="assets/github-activity-counts.svg")
    parser.add_argument("--language-output", default="assets/github-top-languages.svg")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.days < 1 or args.days > 365:
        print("--days must be between 1 and 365", file=sys.stderr)
        return 2

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2

    try:
        counts, summary = fetch_activity_data(args.username, token, args.days)
        total_stars, languages = fetch_repository_data(args.username, token)
        summary = ActivitySummary(
            total_stars=total_stars,
            year_commits=summary.year_commits,
            total_pull_requests=summary.total_pull_requests,
            total_issues=summary.total_issues,
            contributed_to=summary.contributed_to,
            year=summary.year,
        )

        outputs = {
            Path(args.output): render_activity_distribution_svg(
                counts, args.username, args.days
            ),
            Path(args.summary_output): render_activity_summary_svg(
                summary, args.username
            ),
            Path(args.language_output): render_top_languages_svg(
                languages, args.username
            ),
        }
        write_outputs(outputs)
    except Exception as error:
        print(
            f"Failed to generate GitHub activity charts; existing assets were preserved: {error}",
            file=sys.stderr,
        )
        return 1

    print(f"Generated {args.output} from {counts.total} contributions")
    print(f"Generated {args.summary_output} from GitHub account statistics")
    print(f"Generated {args.language_output} from {len(languages)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
