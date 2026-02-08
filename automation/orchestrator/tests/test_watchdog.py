import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import db_store, watchdog


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-200 | IN_PROGRESS | P1 | task one | c1 | w1 | 2026-01-01 10:00 | - | n1 |
| ORCH-201 | IN_PROGRESS | P1 | task two | c2 | w2 | 2099-01-01 10:00 | - | n2 |

"""


class WatchdogTests(unittest.TestCase):
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
            code = watchdog.main(argv)
        return code, buf.getvalue()

    def test_md_resets_only_stale(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "--stale-minutes", "60"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-200", out)
        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("ORCH-200 | PENDING", text)
        self.assertIn("ORCH-201 | IN_PROGRESS", text)

    def test_md_noop_when_nothing_stale(self):
        content = SAMPLE_QUEUE.replace("2026-01-01 10:00", "2099-01-01 10:00")
        self.queue_path.write_text(content, encoding="utf-8")
        code, out = self.run_cmd(["--queue", str(self.queue_path), "--stale-minutes", "60"])
        self.assertEqual(code, 0)
        self.assertIn("NOOP", out)

    def test_db_retries_failed(self):
        db_store.add_item(self.db_path, id="DB-W1", priority="P1", task="a", success_criteria="ok")
        db_store.mark_failed(self.db_path, "DB-W1", "fail")
        code, out = self.run_cmd(["--db", str(self.db_path)])
        self.assertEqual(code, 0)
        self.assertIn("DB-W1", out)
        row = [r for r in db_store.list_items(self.db_path) if r["id"] == "DB-W1"][0]
        self.assertEqual(row["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
