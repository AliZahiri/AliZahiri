import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.generate_activity_focus import (
    ActivityCounts,
    ActivitySummary,
    TopLanguage,
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


if __name__ == "__main__":
    unittest.main()
