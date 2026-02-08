import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import orch


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-100 | PENDING | P1 | task one | c1 | - | - | - | n1 |
| ORCH-101 | PENDING | P0 | task zero | c2 | - | - | - | n2 |
| ORCH-102 | IN_PROGRESS | P2 | task two | c3 | s1 | 2026-01-01 10:00 | - | n3 |

## Tail
"""


class OrchCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def qf(self):
        return orch.QueueFile(self.queue_path)

    def run_cmd(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = orch.main(["--queue", str(self.queue_path)] + argv)
        return code, buf.getvalue()

    def test_parse_rows_count(self):
        self.assertEqual(len(self.qf().rows), 3)

    def test_list_filters_status(self):
        code, out = self.run_cmd(["list", "--status", "IN_PROGRESS"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-102", out)
        self.assertNotIn("ORCH-100", out)

    def test_add_row_appends_pending(self):
        code, _ = self.run_cmd([
            "add",
            "--id",
            "ORCH-200",
            "--priority",
            "P2",
            "--task",
            "new task",
            "--success-criteria",
            "new criteria",
        ])
        self.assertEqual(code, 0)
        row = self.qf().find_by_id("ORCH-200")
        self.assertEqual(row.status, "PENDING")
        self.assertEqual(row.due_at_kst, "-")

    def test_add_duplicate_id_fails(self):
        code, out = self.run_cmd([
            "add",
            "--id",
            "ORCH-100",
            "--priority",
            "P1",
            "--task",
            "dup",
            "--success-criteria",
            "dup",
        ])
        self.assertEqual(code, 1)
        self.assertIn("already exists", out)

    def test_pick_selects_highest_priority(self):
        code, out = self.run_cmd(["pick", "--owner-session", "child-1"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-101", out)
        row = self.qf().find_by_id("ORCH-101")
        self.assertEqual(row.status, "IN_PROGRESS")
        self.assertEqual(row.owner_session, "child-1")
        self.assertNotEqual(row.started_at_kst, "-")

    def test_pick_no_pending(self):
        qf = self.qf()
        for r in qf.rows:
            if r.status == "PENDING":
                r.status = "DONE"
        qf.save()
        code, out = self.run_cmd(["pick"])
        self.assertEqual(code, 0)
        self.assertIn("No pending tasks", out)

    def test_done_updates_status_and_notes(self):
        code, _ = self.run_cmd(["done", "--id", "ORCH-102", "--notes", "completed ok"])
        self.assertEqual(code, 0)
        row = self.qf().find_by_id("ORCH-102")
        self.assertEqual(row.status, "DONE")
        self.assertEqual(row.notes, "completed ok")

    def test_fail_updates_status_and_notes(self):
        code, _ = self.run_cmd(["fail", "--id", "ORCH-100", "--notes", "failed due to timeout"])
        self.assertEqual(code, 0)
        row = self.qf().find_by_id("ORCH-100")
        self.assertEqual(row.status, "FAILED")
        self.assertEqual(row.notes, "failed due to timeout")

    def test_done_nonexistent_row_fails(self):
        code, out = self.run_cmd(["done", "--id", "ORCH-999", "--notes", "x"])
        self.assertEqual(code, 1)
        self.assertIn("not found", out)

    def test_table_tail_preserved_after_save(self):
        self.run_cmd(["pick"])
        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("## Tail", text)

    def test_sanitize_pipe_in_notes(self):
        self.run_cmd(["done", "--id", "ORCH-100", "--notes", "line | with pipe"])
        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("line / with pipe", text)


if __name__ == "__main__":
    unittest.main()
