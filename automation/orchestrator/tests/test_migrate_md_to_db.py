import sqlite3
import tempfile
import unittest
from pathlib import Path

from automation.orchestrator.migrate_md_to_db import migrate


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-300 | PENDING | P1 | task one | c1 | - | - | - | n1 |
| ORCH-301 | DONE | P0 | task two | c2 | s1 | 2026-01-01 12:00 | - | shipped |
"""


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.db_path = Path(self.tmp.name) / "queue.db"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_migrate_imports_rows(self):
        count = migrate(self.queue_path, self.db_path)
        self.assertEqual(count, 2)
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0]
        self.assertEqual(total, 2)

    def test_migrate_is_idempotent_upsert(self):
        migrate(self.queue_path, self.db_path)
        updated = SAMPLE_QUEUE.replace("task one", "task one updated")
        self.queue_path.write_text(updated, encoding="utf-8")
        migrate(self.queue_path, self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0]
            task = conn.execute("SELECT task FROM queue_items WHERE id='ORCH-300'").fetchone()[0]
        self.assertEqual(total, 2)
        self.assertEqual(task, "task one updated")


if __name__ == "__main__":
    unittest.main()
