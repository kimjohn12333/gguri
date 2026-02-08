import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import db_store, ops


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-100 | PENDING | P1 | task one | c1 | - | - | - | n1 |
| ORCH-101 | FAILED | P0 | task zero | c2 | - | - | - | err |
| ORCH-102 | IN_PROGRESS | P2 | task two | c3 | s1 | 2026-01-01 10:00 | - | n3 |

## Tail
"""


class OpsCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")
        self.db_path = Path(self.tmp.name) / "queue.db"
        db_store.init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ops.main(argv)
        return code, buf.getvalue()

    def _qf(self):
        from automation.orchestrator.orch import QueueFile

        return QueueFile(self.queue_path)

    def _db_add(self, *, id: str, status: str = "PENDING"):
        db_store.add_item(self.db_path, id=id, priority="P1", task=id, success_criteria="ok")
        if status == "FAILED":
            db_store.mark_failed(self.db_path, id, "failed")
        elif status == "IN_PROGRESS":
            db_store.pick_next(self.db_path, owner_session="worker-1")

    def test_status_output_non_empty_markdown(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "status"])
        self.assertEqual(code, 0)
        self.assertIn("summary", out)
        self.assertIn("IN_PROGRESS=1", out)

    def test_workers_output_markdown(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "workers"])
        self.assertEqual(code, 0)
        self.assertIn("workers_active=1", out)
        self.assertIn("s1", out)
        self.assertIn("ORCH-102", out)

    def test_cancel_changes_status_markdown(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "cancel", "--id", "ORCH-100"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-100 -> BLOCKED", out)
        row = self._qf().find_by_id("ORCH-100")
        self.assertEqual(row.status, "BLOCKED")
        self.assertIn("cancelled_by_operator", row.notes)

    def test_replan_transition_markdown(self):
        code, out = self.run_cmd([
            "--queue",
            str(self.queue_path),
            "replan",
            "--id",
            "ORCH-102",
            "--notes",
            "split scope",
        ])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-102 -> BLOCKED", out)
        row = self._qf().find_by_id("ORCH-102")
        self.assertEqual(row.status, "BLOCKED")
        self.assertIn("replan:split scope", row.notes)

    def test_retry_basic_markdown(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "retry", "--id", "ORCH-101"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-101 -> PENDING", out)
        row = self._qf().find_by_id("ORCH-101")
        self.assertEqual(row.status, "PENDING")

    def test_status_db_mode_smoke(self):
        self._db_add(id="DB-1")
        code, out = self.run_cmd(["--db", str(self.db_path), "status"])
        self.assertEqual(code, 0)
        self.assertIn("summary", out)
        self.assertIn("PENDING=1", out)

    def test_workers_db_mode_smoke(self):
        self._db_add(id="DB-W1", status="IN_PROGRESS")
        code, out = self.run_cmd(["--db", str(self.db_path), "workers"])
        self.assertEqual(code, 0)
        self.assertIn("workers_active=1", out)
        self.assertIn("worker-1", out)

    def test_retry_db_mode_respects_attempts(self):
        self._db_add(id="DB-R1", status="FAILED")
        code, out = self.run_cmd(["--db", str(self.db_path), "retry", "--id", "DB-R1"])
        self.assertEqual(code, 0)
        self.assertIn("DB-R1 -> PENDING", out)
        row = [r for r in db_store.list_items(self.db_path) if r["id"] == "DB-R1"][0]
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["attempt_count"], 1)


if __name__ == "__main__":
    unittest.main()
