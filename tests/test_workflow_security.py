import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_REFERENCE = re.compile(r"^\s*-\s+uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)
IMMUTABLE_COMMIT = re.compile(r"[0-9a-f]{40}")


class WorkflowSecurityTests(unittest.TestCase):
    def test_external_actions_are_pinned_to_full_commit_shas(self) -> None:
        references: list[tuple[Path, str, str]] = []

        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            content = workflow.read_text(encoding="utf-8")
            references.extend(
                (workflow, action, revision)
                for action, revision in ACTION_REFERENCE.findall(content)
                if not action.startswith("./")
            )

        self.assertTrue(references, "expected at least one external action reference")
        for workflow, action, revision in references:
            with self.subTest(workflow=workflow.name, action=action):
                self.assertIsNotNone(IMMUTABLE_COMMIT.fullmatch(revision))


if __name__ == "__main__":
    unittest.main()
