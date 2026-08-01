import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports_wagent.config import ConfigurationError, Settings, _parse_user_ids


class ConfigTests(unittest.TestCase):
    def test_parse_user_ids(self) -> None:
        self.assertEqual(_parse_user_ids("123, 456\n789"), {123, 456, 789})

    def test_parse_user_ids_rejects_text(self) -> None:
        with self.assertRaises(ConfigurationError):
            _parse_user_ids("123,not-an-id")

    def test_settings_load_required_values(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env = {
                "TELEGRAM_BOT_TOKEN": "telegram-secret",
                "DEEPSEEK_API_KEY": "deepseek-secret",
                "TELEGRAM_ALLOWED_USER_IDS": "123",
                "AGENT_WORKSPACE": workspace,
                "DEEPSEEK_MODEL": "deepseek-v4-flash",
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()

        self.assertEqual(settings.allowed_user_ids, {123})
        self.assertEqual(settings.agent_workspace, Path(workspace).resolve())


if __name__ == "__main__":
    unittest.main()
