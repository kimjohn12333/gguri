import sqlite3
import tempfile
import unittest
from pathlib import Path

from automation.orchestrator import db_store
from automation.orchestrator import enforce_guardrails


class EnforceGuardrailsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "queue.db"
        db_store.init_db(self.db_path)
        db_store.add_item(
            self.db_path,
            id="ORCH-012",
            priority="P0",
            task="guardrails",
            success_criteria="done",
        )
        self.report_path = Path(self.tmp.name) / "report.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def test_enforcement_blocks_and_writes_event(self):
        self.report_path.write_text("not compact format", encoding="utf-8")

        code = enforce_guardrails.main(
            [
                "--id",
                "ORCH-012",
                "--report",
                str(self.report_path),
                "--current-tokens",
                "3600",
                "--db",
                str(self.db_path),
            ]
        )
        self.assertEqual(code, 0)

        item = [r for r in db_store.list_items(self.db_path) if r["id"] == "ORCH-012"][0]
        self.assertEqual(item["status"], "BLOCKED")
        self.assertIn("Guardrail BLOCK", item["notes"])

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT event_type, payload_json FROM queue_events WHERE item_id=? ORDER BY event_id DESC LIMIT 1",
                ("ORCH-012",),
            ).fetchone()
        self.assertEqual(row[0], "blocked")

        with sqlite3.connect(self.db_path) as conn:
            guard = conn.execute(
                "SELECT payload_json FROM queue_events WHERE item_id=? AND event_type='guardrail' ORDER BY event_id DESC LIMIT 1",
                ("ORCH-012",),
            ).fetchone()
        self.assertIsNotNone(guard)


if __name__ == "__main__":
    unittest.main()
