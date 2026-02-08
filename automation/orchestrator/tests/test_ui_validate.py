import unittest

from automation.orchestrator.ui_validate import validate_ui


class UiValidateTests(unittest.TestCase):
    def test_validate_ui_pass(self):
        def runner(cmd, timeout):
            if "open" in cmd:
                return 0, "", ""
            if "snapshot" in cmd:
                return 0, "Dashboard Ready\nBuild: green", ""
            return 0, "", ""

        out = validate_ui("https://example.com", ["Dashboard", "green"], runner=runner)
        self.assertTrue(out["ok"])
        self.assertEqual(out["missing"], [])

    def test_validate_ui_missing_terms(self):
        def runner(cmd, timeout):
            if "open" in cmd:
                return 0, "", ""
            if "snapshot" in cmd:
                return 0, "Only Home Screen", ""
            return 0, "", ""

        out = validate_ui("https://example.com", ["Dashboard"], runner=runner)
        self.assertFalse(out["ok"])
        self.assertIn("Dashboard", out["missing"])

    def test_validate_ui_open_failure(self):
        def runner(cmd, timeout):
            if "open" in cmd:
                return 1, "", "browser failed"
            return 0, "", ""

        out = validate_ui("https://example.com", ["Dashboard"], runner=runner)
        self.assertFalse(out["ok"])
        self.assertIn("ui_open_failed", out["reasons"][0])


if __name__ == "__main__":
    unittest.main()
