import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.orchestrator import db_store, review_and_route


class ReviewAndRouteDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "queue.db"
        db_store.init_db(self.db_path)
        db_store.add_item(
            self.db_path,
            id="ORCH-DB-1",
            priority="P1",
            task="t",
            success_criteria="update README; run tests",
            max_attempts=3,
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE queue_items SET status='IN_PROGRESS', owner_session='w1' WHERE id='ORCH-DB-1'")

    def tearDown(self):
        self.tmp.cleanup()

    def _row(self):
        return [r for r in db_store.list_items(self.db_path) if r["id"] == "ORCH-DB-1"][0]

    def test_retry_increments_attempt_and_sets_pending(self):
        review_and_route.main(
            [
                "--db",
                str(self.db_path),
                "--id",
                "ORCH-DB-1",
                "--success-criteria",
                "update README; run tests",
                "--report",
                "updated README only",
            ]
        )
        row = self._row()
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["attempt_count"], 1)

    def test_block_when_max_retries_exhausted(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE queue_items SET attempt_count=3 WHERE id='ORCH-DB-1'")

        review_and_route.main(
            [
                "--db",
                str(self.db_path),
                "--id",
                "ORCH-DB-1",
                "--success-criteria",
                "update README; run tests",
                "--report",
                "updated README only",
                "--max-retries",
                "3",
            ]
        )
        row = self._row()
        self.assertEqual(row["status"], "BLOCKED")

    def test_ui_failure_blocks_when_retry_limit_reached(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE queue_items SET attempt_count=3 WHERE id='ORCH-DB-1'")

        with patch(
            "automation.orchestrator.review_and_route.validate_ui",
            return_value={"ok": False, "reasons": ["ui_snapshot_failed:timeout"], "missing": []},
        ):
            review_and_route.main(
                [
                    "--db",
                    str(self.db_path),
                    "--id",
                    "ORCH-DB-1",
                    "--success-criteria",
                    "update README; run tests",
                    "--report",
                    "updated README and run tests complete",
                    "--max-retries",
                    "3",
                    "--ui-url",
                    "https://example.com",
                ]
            )
        row = self._row()
        self.assertEqual(row["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
