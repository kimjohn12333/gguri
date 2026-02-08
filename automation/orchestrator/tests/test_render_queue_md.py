import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import db_store, render_queue_md


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-001 | DONE | P1 | old task | old c | - | - | - | old |

## Tail
keep-this-section
"""


class RenderQueueFromDbTests(unittest.TestCase):
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
            code = render_queue_md.main(argv)
        return code, buf.getvalue()

    def test_render_overwrites_table_from_db(self):
        db_store.add_item(self.db_path, id="ORCH-100", priority="P1", task="task one", success_criteria="c1")
        db_store.add_item(self.db_path, id="ORCH-101", priority="P0", task="task zero", success_criteria="c2")

        code, out = self.run_cmd(["--db", str(self.db_path), "--queue", str(self.queue_path)])
        self.assertEqual(code, 0)
        self.assertIn("rendered 2 rows", out)

        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("ORCH-100", text)
        self.assertIn("ORCH-101", text)
        self.assertNotIn("ORCH-001", text)
        self.assertIn("keep-this-section", text)

    def test_render_empty_db_keeps_valid_table(self):
        code, out = self.run_cmd(["--db", str(self.db_path), "--queue", str(self.queue_path)])
        self.assertEqual(code, 0)
        self.assertIn("rendered 0 rows", out)
        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("| id | status | priority | task |", text)


if __name__ == "__main__":
    unittest.main()
