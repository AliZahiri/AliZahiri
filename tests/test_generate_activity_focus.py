import io
import json
import tempfile
import urllib.error
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import call, patch

from scripts.generate_activity_focus import (
    ActivityCounts,
    ActivitySummary,
    TopLanguage,
    github_graphql,
    render_activity_distribution_svg,
    render_activity_summary_svg,
    render_top_languages_svg,
    write_outputs,
)


class ActivityPercentageTests(unittest.TestCase):
    def test_percentages_sum_to_one_hundred(self) -> None:
        percentages = ActivityCounts(1, 1, 1, 0).percentages()

        self.assertEqual(100, sum(percentages.values()))
        self.assertEqual(
            {
                "commits": 34,
                "issues": 33,
                "pull_requests": 33,
                "code_reviews": 0,
            },
            percentages,
        )

    def test_zero_activity_has_zero_percentages(self) -> None:
        percentages = ActivityCounts(0, 0, 0, 0).percentages()

        self.assertEqual(0, sum(percentages.values()))
        self.assertTrue(all(value == 0 for value in percentages.values()))


class GitHubGraphQLRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_response = io.BytesIO(b'{"data": {"viewer": {"login": "AliZahiri"}}}')

    def test_retries_transient_http_failure_then_returns_data(self) -> None:
        transient_error = urllib.error.HTTPError(
            "https://api.github.com/graphql", 503, "Service Unavailable", {}, None
        )
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                side_effect=[transient_error, self.valid_response],
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            data = github_graphql("query", {}, "token")

        self.assertEqual({"viewer": {"login": "AliZahiri"}}, data)
        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(1)

    def test_retries_transient_network_failure(self) -> None:
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                side_effect=[urllib.error.URLError("connection reset"), self.valid_response],
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            data = github_graphql("query", {}, "token")

        self.assertIn("viewer", data)
        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(1)

    def test_retries_graphql_rate_limit_error(self) -> None:
        rate_limit_response = io.BytesIO(
            b'{"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}'
        )
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                side_effect=[rate_limit_response, self.valid_response],
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            data = github_graphql("query", {}, "token")

        self.assertIn("viewer", data)
        self.assertEqual(2, urlopen.call_count)
        sleep.assert_called_once_with(1)

    def test_does_not_retry_permanent_http_failure(self) -> None:
        permanent_error = urllib.error.HTTPError(
            "https://api.github.com/graphql", 401, "Unauthorized", {}, None
        )
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                side_effect=permanent_error,
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                github_graphql("query", {}, "token")

        urlopen.assert_called_once()
        sleep.assert_not_called()

    def test_transient_retries_stop_at_attempt_limit(self) -> None:
        errors = [
            urllib.error.HTTPError(
                "https://api.github.com/graphql", 503, "Service Unavailable", {}, None
            )
            for _ in range(3)
        ]
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                side_effect=errors,
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                github_graphql("query", {}, "token", attempts=3)

        self.assertEqual(3, urlopen.call_count)
        self.assertEqual([call(1), call(2)], sleep.call_args_list)

    def test_does_not_retry_graphql_errors(self) -> None:
        response = io.BytesIO(b'{"errors": [{"message": "Invalid query"}]}')
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                return_value=response,
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "GraphQL error: Invalid query"):
                github_graphql("query", {}, "token")

        urlopen.assert_called_once()
        sleep.assert_not_called()

    def test_does_not_retry_invalid_json_response(self) -> None:
        response = io.BytesIO(b"not-json")
        with (
            patch(
                "scripts.generate_activity_focus.urllib.request.urlopen",
                return_value=response,
            ) as urlopen,
            patch("scripts.generate_activity_focus.time.sleep") as sleep,
        ):
            with self.assertRaises(json.JSONDecodeError):
                github_graphql("query", {}, "token")

        urlopen.assert_called_once()
        sleep.assert_not_called()


class ActivitySvgTests(unittest.TestCase):
    def test_rendered_cards_are_valid_svg(self) -> None:
        cards = (
            render_activity_distribution_svg(ActivityCounts(3, 2, 1, 1), "A&B", 30),
            render_activity_summary_svg(ActivitySummary(4, 5, 6, 7, 8, 2026), "A&B"),
            render_top_languages_svg(
                [TopLanguage("Python", 200), TopLanguage("Shell", 100)], "A&B"
            ),
        )

        for card in cards:
            root = ET.fromstring(card)
            self.assertEqual("{http://www.w3.org/2000/svg}svg", root.tag)

    def test_invalid_card_preserves_every_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.svg"
            second = root / "second.svg"
            first.write_text("first-original", encoding="utf-8")
            second.write_text("second-original", encoding="utf-8")
            valid_card = render_activity_distribution_svg(
                ActivityCounts(1, 0, 0, 0), "AliZahiri", 365
            )

            with self.assertRaises(RuntimeError):
                write_outputs({first: valid_card, second: "not-an-svg"})

            self.assertEqual("first-original", first.read_text(encoding="utf-8"))
            self.assertEqual("second-original", second.read_text(encoding="utf-8"))
            self.assertFalse((root / ".first.svg.tmp").exists())

    def test_replace_failure_restores_every_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.svg"
            second = root / "second.svg"
            first.write_text("first-original", encoding="utf-8")
            second.write_text("second-original", encoding="utf-8")
            valid_card = render_activity_distribution_svg(
                ActivityCounts(1, 0, 0, 0), "AliZahiri", 365
            )
            original_replace = Path.replace

            def fail_second_publish(source: Path, destination: Path) -> Path:
                if source.name == ".second.svg.tmp" and destination == second:
                    raise OSError("simulated publish failure")
                return original_replace(source, destination)

            with patch.object(Path, "replace", new=fail_second_publish):
                with self.assertRaisesRegex(OSError, "simulated publish failure"):
                    write_outputs({first: valid_card, second: valid_card})

            self.assertEqual("first-original", first.read_text(encoding="utf-8"))
            self.assertEqual("second-original", second.read_text(encoding="utf-8"))
            self.assertFalse((root / ".first.svg.tmp").exists())
            self.assertFalse((root / ".second.svg.tmp").exists())
            self.assertFalse((root / ".first.svg.bak").exists())
            self.assertFalse((root / ".second.svg.bak").exists())


if __name__ == "__main__":
    unittest.main()
