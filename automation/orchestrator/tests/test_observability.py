import json
import tempfile
import unittest
from pathlib import Path

from automation.orchestrator import metrics_aggregate, orch


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-100 | PENDING | P1 | task one | c1 | - | - | - | n1 |
"""


class ObservabilityTests(unittest.TestCase):
    def test_orch_writes_trace_log(self):
        with tempfile.TemporaryDirectory() as td:
            queue = Path(td) / "QUEUE.md"
            log = Path(td) / "runs.jsonl"
            queue.write_text(SAMPLE_QUEUE, encoding="utf-8")

            code = orch.main([
                "--queue",
                str(queue),
                "--log-path",
                str(log),
                "--trace-id",
                "trace-test-123",
                "list",
            ])
            self.assertEqual(code, 0)

            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(events[0]["event"], "run_start")
            self.assertEqual(events[1]["event"], "run_end")
            self.assertEqual(events[0]["trace_id"], "trace-test-123")
            self.assertEqual(events[1]["trace_id"], "trace-test-123")

    def test_metrics_aggregate_from_logs(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "runs.jsonl"
            payloads = [
                {"event": "run_end", "command": "done", "exit_code": 0, "duration_ms": 100},
                {"event": "run_end", "command": "fail", "exit_code": 0, "duration_ms": 300},
                {"event": "run_end", "command": "list", "exit_code": 0, "duration_ms": 50},
            ]
            log.write_text("\n".join(json.dumps(p) for p in payloads) + "\n", encoding="utf-8")

            report = metrics_aggregate.aggregate_from_logs(log)
            self.assertEqual(report["terminal_runs"], 2)
            self.assertEqual(report["success"], 1)
            self.assertEqual(report["failed"], 1)
            self.assertEqual(report["success_rate"], 0.5)
            self.assertEqual(report["latency_p95_ms"], 100)


if __name__ == "__main__":
    unittest.main()
