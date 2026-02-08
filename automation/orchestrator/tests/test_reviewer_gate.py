import unittest

from automation.orchestrator.reviewer_gate import BLOCK, PASS, RETRY, evaluate_result


class ReviewerGateTests(unittest.TestCase):
    def test_pass_when_all_criteria_covered(self):
        criteria = "update README; run tests"
        report = "Done: update README section and run tests successfully."
        out = evaluate_result(criteria, report)
        self.assertEqual(out["verdict"], PASS)
        self.assertEqual(out["missing_checks"], [])

    def test_retry_when_missing_checks(self):
        criteria = "update README; run tests"
        report = "Updated README only."
        out = evaluate_result(criteria, report)
        self.assertEqual(out["verdict"], RETRY)
        self.assertEqual(len(out["missing_checks"]), 1)

    def test_block_on_explicit_blocker_or_retry_guard(self):
        criteria = "update README"
        report = "BLOCKER: cannot proceed due to permissions"
        out = evaluate_result(criteria, report)
        self.assertEqual(out["verdict"], BLOCK)

        out2 = evaluate_result("run tests", "incomplete", attempt_count=3, max_retries=3)
        self.assertEqual(out2["verdict"], BLOCK)
        self.assertTrue(any("retry_limit_reached" in r for r in out2["reasons"]))


if __name__ == "__main__":
    unittest.main()
