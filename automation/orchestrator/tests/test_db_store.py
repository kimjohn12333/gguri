import sqlite3
import tempfile
import unittest
from pathlib import Path

from automation.orchestrator import db_store


class DbStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "queue.db"
        db_store.init_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, **filters):
        return db_store.list_items(self.db_path, **filters)

    def test_init_db_creates_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        self.assertIn("queue_items", names)
        self.assertIn("queue_events", names)

    def test_add_item_defaults_pending(self):
        db_store.add_item(
            self.db_path,
            id="ORCH-200",
            priority="P1",
            task="task",
            success_criteria="done",
        )
        row = self.rows()[0]
        self.assertEqual(row["id"], "ORCH-200")
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["owner_session"], "-")
        self.assertEqual(row["attempt_count"], 0)
        self.assertEqual(row["max_attempts"], 3)

    def test_list_items_filters(self):
        db_store.add_item(self.db_path, id="A", priority="P1", task="a", success_criteria="a")
        db_store.add_item(self.db_path, id="B", priority="P0", task="b", success_criteria="b")
        db_store.mark_done(self.db_path, "A", "ok")
        done = self.rows(status="DONE")
        p0 = self.rows(priority="P0")
        self.assertEqual([r["id"] for r in done], ["A"])
        self.assertEqual([r["id"] for r in p0], ["B"])

    def test_pick_next_priority_order(self):
        db_store.add_item(self.db_path, id="A", priority="P2", task="a", success_criteria="a")
        db_store.add_item(self.db_path, id="B", priority="P0", task="b", success_criteria="b")
        picked = db_store.pick_next(self.db_path, owner_session="sess-1")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["id"], "B")
        row_b = [r for r in self.rows() if r["id"] == "B"][0]
        self.assertEqual(row_b["status"], "IN_PROGRESS")
        self.assertEqual(row_b["owner_session"], "sess-1")

    def test_pick_next_none_when_empty(self):
        self.assertIsNone(db_store.pick_next(self.db_path, owner_session="s"))

    def test_mark_done_and_failed(self):
        db_store.add_item(self.db_path, id="A", priority="P1", task="a", success_criteria="a")
        db_store.mark_done(self.db_path, "A", " finished ")
        row = self.rows()[0]
        self.assertEqual(row["status"], "DONE")
        self.assertEqual(row["notes"], "finished")

        db_store.add_item(self.db_path, id="B", priority="P1", task="b", success_criteria="b")
        db_store.mark_failed(self.db_path, "B", " bad ")
        row_b = [r for r in self.rows() if r["id"] == "B"][0]
        self.assertEqual(row_b["status"], "FAILED")
        self.assertEqual(row_b["notes"], "bad")
        self.assertEqual(row_b["last_error"], "bad")

    def test_mark_nonexistent_raises(self):
        with self.assertRaises(ValueError):
            db_store.mark_done(self.db_path, "NOPE", "x")

    def test_append_event_persists_json(self):
        db_store.add_item(self.db_path, id="A", priority="P1", task="a", success_criteria="a")
        db_store.append_event(self.db_path, "A", "custom", {"x": 1})
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT event_type, payload_json FROM queue_events WHERE item_id='A' ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
        self.assertEqual(row[0], "custom")
        self.assertEqual(row[1], '{"x": 1}')

    def test_lease_acquire_renew_release_happy_path(self):
        db_store.add_item(self.db_path, id="L1", priority="P1", task="a", success_criteria="a")
        self.assertTrue(db_store.acquire_lease(self.db_path, "L1", "worker-1", lease_seconds=120))
        self.assertTrue(db_store.renew_lease(self.db_path, "L1", "worker-1", lease_seconds=120))
        self.assertTrue(db_store.release_lease(self.db_path, "L1", "worker-1"))
        row = [r for r in self.rows() if r["id"] == "L1"][0]
        self.assertIsNone(row["lease_owner"])
        self.assertIsNone(row["lease_expires_at"])

    def test_lease_conflict_path(self):
        db_store.add_item(self.db_path, id="L2", priority="P1", task="a", success_criteria="a")
        self.assertTrue(db_store.acquire_lease(self.db_path, "L2", "worker-1", lease_seconds=120))
        self.assertFalse(db_store.acquire_lease(self.db_path, "L2", "worker-2", lease_seconds=120))
        self.assertFalse(db_store.renew_lease(self.db_path, "L2", "worker-2", lease_seconds=120))
        self.assertFalse(db_store.release_lease(self.db_path, "L2", "worker-2"))

    def test_retry_backoff_progression_and_max_attempt_stop(self):
        db_store.add_item(
            self.db_path,
            id="R1",
            priority="P1",
            task="a",
            success_criteria="a",
            max_attempts=3,
        )
        db_store.mark_failed(self.db_path, "R1", "net")

        r1 = db_store.retry_eligible_items(self.db_path, now_ts=1000)
        self.assertEqual(r1, ["R1"])
        row = [r for r in self.rows() if r["id"] == "R1"][0]
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["attempt_count"], 1)
        self.assertIn("retry_not_before=1060", row["notes"])

        db_store.mark_failed(self.db_path, "R1", "net2")
        r2 = db_store.retry_eligible_items(self.db_path, now_ts=2000)
        self.assertEqual(r2, ["R1"])
        row = [r for r in self.rows() if r["id"] == "R1"][0]
        self.assertEqual(row["attempt_count"], 2)
        self.assertIn("retry_not_before=2180", row["notes"])

        db_store.mark_failed(self.db_path, "R1", "net3")
        r3 = db_store.retry_eligible_items(self.db_path, now_ts=3000)
        self.assertEqual(r3, ["R1"])
        row = [r for r in self.rows() if r["id"] == "R1"][0]
        self.assertEqual(row["attempt_count"], 3)
        self.assertIn("retry_not_before=3600", row["notes"])

        db_store.mark_failed(self.db_path, "R1", "net4")
        r4 = db_store.retry_eligible_items(self.db_path, now_ts=4000)
        self.assertEqual(r4, [])
        row = [r for r in self.rows() if r["id"] == "R1"][0]
        self.assertEqual(row["status"], "FAILED")
        self.assertEqual(row["attempt_count"], 3)

    def test_idempotency_duplicate_prevention_on_pick(self):
        db_store.add_item(
            self.db_path,
            id="I1",
            priority="P1",
            task="a",
            success_criteria="a",
            idempotency_key="k-1",
        )
        db_store.mark_done(self.db_path, "I1", "done")

        db_store.add_item(
            self.db_path,
            id="I2",
            priority="P0",
            task="dup",
            success_criteria="dup",
            idempotency_key="k-1",
        )
        db_store.add_item(
            self.db_path,
            id="I3",
            priority="P1",
            task="real",
            success_criteria="real",
        )

        picked = db_store.pick_next(self.db_path, owner_session="sess-x")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["id"], "I3")

        row_i2 = [r for r in self.rows() if r["id"] == "I2"][0]
        self.assertEqual(row_i2["status"], "DONE")
        self.assertIn("Skipped duplicate by idempotency_key", row_i2["notes"])


if __name__ == "__main__":
    unittest.main()
