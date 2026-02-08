import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.orchestrator import review_and_route
from automation.orchestrator.orch import QueueFile


SAMPLE_QUEUE = """# Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-1 | IN_PROGRESS | P1 | t | update README; run tests | s | 2026-01-01 10:00 | - | |
"""


class ReviewAndRouteMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pass_marks_done(self):
        review_and_route.main(
            [
                "--queue",
                str(self.queue_path),
                "--id",
                "ORCH-1",
                "--success-criteria",
                "update README; run tests",
                "--report",
                "updated README and run tests complete",
            ]
        )
        row = QueueFile(self.queue_path).find_by_id("ORCH-1")
        self.assertEqual(row.status, "DONE")

    def test_retry_marks_pending_and_increments_attempt_note(self):
        review_and_route.main(
            [
                "--queue",
                str(self.queue_path),
                "--id",
                "ORCH-1",
                "--success-criteria",
                "update README; run tests",
                "--report",
                "updated README only",
                "--max-retries",
                "3",
            ]
        )
        row = QueueFile(self.queue_path).find_by_id("ORCH-1")
        self.assertEqual(row.status, "PENDING")
        self.assertIn("review_attempts=1", row.notes)

    def test_ui_failure_forces_retry(self):
        with patch(
            "automation.orchestrator.review_and_route.validate_ui",
            return_value={"ok": False, "reasons": ["ui_missing_terms:Dashboard"], "missing": ["Dashboard"]},
        ):
            review_and_route.main(
                [
                    "--queue",
                    str(self.queue_path),
                    "--id",
                    "ORCH-1",
                    "--success-criteria",
                    "update README; run tests",
                    "--report",
                    "updated README and run tests complete",
                    "--ui-url",
                    "https://example.com",
                    "--ui-contains",
                    "Dashboard",
                ]
            )
        row = QueueFile(self.queue_path).find_by_id("ORCH-1")
        self.assertEqual(row.status, "PENDING")
        self.assertIn("ui_validation", row.notes)


if __name__ == "__main__":
    unittest.main()
