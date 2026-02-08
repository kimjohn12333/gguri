import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import nl_intake


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-015 | DONE | P0 | prev | c | - | - | - | n |

"""


class NaturalIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = nl_intake.main(["--queue", str(self.queue_path)] + argv)
        return code, buf.getvalue()

    def test_propose_tasks_bulleted_lines(self):
        req = "- API 설계\n- 구현\n- 테스트"
        tasks = nl_intake.propose_tasks(req, parallel=3)
        self.assertEqual(tasks, ["API 설계", "구현", "테스트"])

    def test_propose_tasks_delimiter_split(self):
        req = "로그 정리, 재시도 보강 그리고 문서 업데이트"
        tasks = nl_intake.propose_tasks(req, parallel=3)
        self.assertEqual(len(tasks), 3)

    def test_propose_tasks_fallback_phase(self):
        req = "오케스트레이터 안정화"
        tasks = nl_intake.propose_tasks(req, parallel=2)
        self.assertEqual(len(tasks), 2)
        self.assertTrue(tasks[0].startswith("요구사항 정리/설계:"))

    def test_submit_creates_pending_rows(self):
        code, out = self.run_cmd(
            [
                "submit",
                "--request",
                "- A\n- B",
                "--parallel",
                "2",
                "--priority",
                "P0",
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("created=2", out)

        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("ORCH-016", text)
        self.assertIn("ORCH-017", text)
        self.assertIn("| PENDING | P0 |", text)

    def test_plan_outputs_preview(self):
        code, out = self.run_cmd(["plan", "--request", "배포 자동화", "--parallel", "1"])
        self.assertEqual(code, 0)
        self.assertIn("parallel: 1", out)


if __name__ == "__main__":
    unittest.main()
