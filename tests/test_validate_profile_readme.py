import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validate_profile_readme as validator


class ProfileReadmeValidationTests(unittest.TestCase):
    def setUp(self):
        self.content = validator.README.read_text(encoding="utf-8")

    def test_current_profile_is_valid(self):
        self.assertEqual((), validator.profile_readme_warnings(self.content))

    def test_positioning_and_contact_are_required(self):
        for text, warning in ((validator.REQUIRED_POSITIONING, "missing_platform_positioning"),
                              (validator.REQUIRED_CONTACT, "missing_linkedin_contact")):
            with self.subTest(warning=warning):
                self.assertIn(warning, validator.profile_readme_warnings(self.content.replace(text, "")))

    def test_third_party_card_cannot_replace_local_chart(self):
        content = self.content.replace(validator.ACTIVITY_ASSETS[0], "https://example.org/card.svg")
        warnings = validator.profile_readme_warnings(content)
        self.assertTrue(any(warning.startswith("activity_chart_order_or_count:") for warning in warnings))

    def test_missing_assets_are_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(validator, "ROOT", Path(directory)):
            warnings = validator.profile_readme_warnings(self.content)
        for asset in validator.REQUIRED_ASSETS:
            self.assertIn("missing_asset_file:" + asset, warnings)

    def test_malformed_svg_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / validator.ACTIVITY_ASSETS[0]
            target.parent.mkdir()
            target.write_text("<svg>" + "x" * 600)
            with patch.object(validator, "ROOT", root):
                self.assertIn("invalid_svg_xml:" + validator.ACTIVITY_ASSETS[0],
                              validator.profile_readme_warnings(self.content))

    def test_extra_activity_image_is_reported(self):
        content = self.content.replace("## GitHub Activity", '## GitHub Activity\n<img src="extra.svg" />')
        self.assertIn("activity_chart_count:expected=3:actual=4",
                      validator.profile_readme_warnings(content))
