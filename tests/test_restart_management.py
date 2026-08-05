import unittest
from unittest.mock import patch

from reports_wagent.restart_management import RestartManager


class RestartManagerTests(unittest.TestCase):
    def test_restart_tool_requests_restart(self) -> None:
        with patch.dict("os.environ", {"REPORTS_WAGENT_SUPERVISED": "1"}):
            manager = RestartManager()

        result = manager.tool.invoke({"reason": "code updated"})

        self.assertIn("code updated", result)
        self.assertTrue(manager.consume())
        self.assertFalse(manager.consume())


if __name__ == "__main__":
    unittest.main()
