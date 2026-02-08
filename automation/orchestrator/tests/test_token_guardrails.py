import unittest

from automation.orchestrator import token_guardrails as tg


GOOD_REPORT = """[REPORT ORCH-012]
Status: DONE
Files:
- automation/orchestrator/token_guardrails.py
Diff-Summary:
- Added executable guardrail policy checks.
Validation:
- python -m unittest: pass
Risks:
- None
Next:
- None
"""

BAD_REPORT = """Status: DONE
Files:
Diff-Summary:
Validation:
Risks:
Next:
```python
print('paste')
```
"""


class TokenGuardrailsTests(unittest.TestCase):
    def test_validate_compact_report_pass_case(self):
        result = tg.validate_compact_report(GOOD_REPORT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["violations"], [])
        self.assertGreater(result["estimated_tokens"], 0)

    def test_validate_compact_report_fail_case(self):
        result = tg.validate_compact_report(BAD_REPORT)
        self.assertFalse(result["ok"])
        codes = {v["code"] for v in result["violations"]}
        self.assertIn("MISSING_REPORT_HEADER", codes)
        self.assertIn("CODE_FENCE_FORBIDDEN", codes)

    def test_budget_boundaries(self):
        self.assertEqual(tg.check_budget(1999), tg.STATE_OK)
        self.assertEqual(tg.check_budget(2000), tg.STATE_OK)
        self.assertEqual(tg.check_budget(2001), tg.STATE_SOFT_EXCEEDED)
        self.assertEqual(tg.check_budget(3500), tg.STATE_SOFT_EXCEEDED)
        self.assertEqual(tg.check_budget(3501), tg.STATE_HARD_EXCEEDED)

    def test_decide_action(self):
        self.assertEqual(tg.decide_action(tg.STATE_OK, []), tg.ACTION_ALLOW)
        self.assertEqual(tg.decide_action(tg.STATE_SOFT_EXCEEDED, []), tg.ACTION_SUMMARIZE)
        self.assertEqual(
            tg.decide_action(tg.STATE_OK, [{"code": "X", "severity": "medium"}]),
            tg.ACTION_SUMMARIZE,
        )
        self.assertEqual(
            tg.decide_action(tg.STATE_OK, [{"code": "X", "severity": "high"}]),
            tg.ACTION_BLOCK,
        )


if __name__ == "__main__":
    unittest.main()
