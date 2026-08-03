import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reports_wagent.config import (
    ConfigurationError,
    Settings,
    _parse_bool,
    _parse_json_object,
    _parse_user_ids,
)


class ConfigTests(unittest.TestCase):
    def test_parse_user_ids(self) -> None:
        self.assertEqual(_parse_user_ids("123, 456\n789"), {123, 456, 789})

    def test_parse_user_ids_rejects_text(self) -> None:
        with self.assertRaises(ConfigurationError):
            _parse_user_ids("123,not-an-id")

    def test_parse_json_object(self) -> None:
        self.assertEqual(
            _parse_json_object('{"max_results": 5}', "NAME"), {"max_results": 5}
        )

    def test_parse_json_object_rejects_non_object(self) -> None:
        with self.assertRaises(ConfigurationError):
            _parse_json_object("[1, 2, 3]", "NAME")

    def test_parse_bool(self) -> None:
        self.assertTrue(_parse_bool("true"))
        self.assertTrue(_parse_bool("1"))
        self.assertFalse(_parse_bool("false"))

    def test_settings_load_required_values(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env = {
                "TELEGRAM_BOT_TOKEN": "telegram-secret",
                "DEEPSEEK_API_KEY": "deepseek-secret",
                "TELEGRAM_ALLOWED_USER_IDS": "123",
                "AGENT_WORKSPACE": workspace,
                "DEEPSEEK_MODEL": "deepseek-v4-flash",
                "OPENAI_API_KEY": "openai-secret",
                "TRANSCRIPTION_LANGUAGE": "en",
                "TAVILY_API_KEY": "tavily-secret",
                "TAVILY_DEFAULT_PARAMETERS": '{"max_results": 5}',
                "LINKEDIN_MCP_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=True):
                settings = Settings.from_env()

        self.assertEqual(settings.allowed_user_ids, {123})
        self.assertEqual(settings.agent_workspace, Path(workspace).resolve())
        self.assertEqual(settings.openai_api_key, "openai-secret")
        self.assertEqual(settings.transcription_language, "en")
        self.assertEqual(settings.tavily_api_key, "tavily-secret")
        self.assertEqual(settings.tavily_default_parameters, {"max_results": 5})
        self.assertTrue(settings.linkedin_mcp_enabled)
        self.assertEqual(settings.linkedin_mcp_command, "uvx")


if __name__ == "__main__":
    unittest.main()
