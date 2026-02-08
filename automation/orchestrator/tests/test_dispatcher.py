import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import db_store, dispatcher


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-100 | PENDING | P1 | task one | c1 | - | - | - | n1 |
| ORCH-101 | PENDING | P0 | task zero | c2 | - | - | - | n2 |

"""


class DispatcherTests(unittest.TestCase):
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
            code = dispatcher.main(argv)
        return code, buf.getvalue()

    def test_pick_md_p0_first(self):
        code, out = self.run_cmd(["--queue", str(self.queue_path), "--owner-session", "d1"])
        self.assertEqual(code, 0)
        self.assertIn("ORCH-101", out)

    def test_pick_md_noop_when_empty(self):
        self.queue_path.write_text(
            SAMPLE_QUEUE.replace("| ORCH-100 | PENDING", "| ORCH-100 | DONE").replace("| ORCH-101 | PENDING", "| ORCH-101 | DONE"),
            encoding="utf-8",
        )
        code, out = self.run_cmd(["--queue", str(self.queue_path)])
        self.assertEqual(code, 0)
        self.assertIn("NOOP", out)

    def test_pick_db(self):
        db_store.add_item(self.db_path, id="DB-1", priority="P1", task="a", success_criteria="ok")
        db_store.add_item(self.db_path, id="DB-2", priority="P0", task="b", success_criteria="ok")
        code, out = self.run_cmd(["--db", str(self.db_path), "--owner-session", "d2"])
        self.assertEqual(code, 0)
        self.assertIn("DB-2", out)


if __name__ == "__main__":
    unittest.main()
