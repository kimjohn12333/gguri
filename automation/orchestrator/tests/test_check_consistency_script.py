import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation.orchestrator import db_store


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-100 | PENDING | P1 | task one | c1 | - | - | - | n1 |

"""


class CheckConsistencyScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.queue_path = self.root / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")
        self.db_path = self.root / "queue.db"
        db_store.init_db(self.db_path)
        db_store.add_item(self.db_path, id="ORCH-100", priority="P1", task="task one", success_criteria="c1")

        self.log_path = self.root / "runs.jsonl"
        self.log_path.write_text(
            '{"event":"run_end","command":"done","exit_code":0,"duration_ms":100}\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_script_health_ok(self):
        script = "/Users/jm/.openclaw/workspace/automation/orchestrator/check_consistency.sh"
        env = os.environ.copy()
        env.update(
            {
                "ORCH_QUEUE_MD": str(self.queue_path),
                "ORCH_DB_PATH": str(self.db_path),
                "ORCH_LOG_PATH": str(self.log_path),
                "ORCH_KPI_MAX_FAILURE_RATE": "1.0",
                "ORCH_KPI_MAX_LATENCY_P95_MS": "5000",
                "ORCH_KPI_MAX_STALE_IN_PROGRESS": "1",
            }
        )
        cp = subprocess.run(
            [script],
            capture_output=True,
            text=True,
            env=env,
            cwd="/Users/jm/.openclaw/workspace",
        )
        self.assertEqual(cp.returncode, 0)
        self.assertIn("HEALTH_OK", cp.stdout)


if __name__ == "__main__":
    unittest.main()
