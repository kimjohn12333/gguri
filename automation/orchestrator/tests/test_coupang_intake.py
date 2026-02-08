import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from automation.orchestrator import coupang_intake


SAMPLE_QUEUE = """# Orchestrator Queue

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-018 | DONE | P1 | prev | c | - | - | - | n |

"""


class CoupangIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "QUEUE.md"
        self.queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = coupang_intake.main(["--queue", str(self.queue_path)] + argv)
        return code, buf.getvalue()

    def test_plan_safe_mentions_approval(self):
        code, out = self.run_cmd([
            "plan",
            "--request",
            "생수 2L 6개",
            "--mode",
            "safe",
        ])
        self.assertEqual(code, 0)
        self.assertIn("mode: safe", out)
        self.assertIn("승인 요청", out)

    def test_submit_auto_creates_pending_row(self):
        code, out = self.run_cmd([
            "submit",
            "--request",
            "키친타월",
            "--mode",
            "auto",
            "--max-price",
            "20000",
            "--qty",
            "2",
            "--must-have",
            "로켓배송",
        ])
        self.assertEqual(code, 0)
        self.assertIn("created=1 id=ORCH-019", out)

        text = self.queue_path.read_text(encoding="utf-8")
        self.assertIn("ORCH-019", text)
        self.assertIn("[쿠팡구매/auto] 키친타월", text)
        self.assertIn("주문 완료", text)

    def test_submit_invalid_qty_fails(self):
        with self.assertRaises(ValueError):
            coupang_intake.main([
                "--queue",
                str(self.queue_path),
                "submit",
                "--request",
                "휴지",
                "--qty",
                "0",
            ])


if __name__ == "__main__":
    unittest.main()
