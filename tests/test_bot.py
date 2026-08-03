import unittest
from pathlib import Path

from reports_wagent.bot import _chunks, _with_transcription
from reports_wagent.config import Settings
from reports_wagent.mcp_tools import load_mcp_tools


class ChunkTests(unittest.TestCase):
    def test_short_text_stays_in_one_chunk(self) -> None:
        self.assertEqual(_chunks("hello", limit=10), ["hello"])

    def test_long_text_is_split_without_data_loss(self) -> None:
        text = "one two three four"
        chunks = _chunks(text, limit=8)
        self.assertTrue(all(len(chunk) <= 8 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)

    def test_with_transcription_prefixes_answer(self) -> None:
        self.assertEqual(
            _with_transcription("hello there", "Agent answer"),
            "Transcription:\nhello there\n\nAgent answer",
        )


class TavilyToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_tavily_tools_returns_empty_without_key(self) -> None:
        settings = Settings(
            telegram_bot_token="telegram-secret",
            deepseek_api_key="deepseek-secret",
            openai_api_key=None,
            allowed_user_ids=frozenset({123}),
            deepseek_model="deepseek-v4-flash",
            agent_workspace=Path.cwd(),
            agent_memory_db=Path.cwd() / ".agent_memory" / "checkpoints.sqlite",
            agent_status_file=Path.cwd() / ".agent_runtime" / "status.json",
            tavily_api_key=None,
        )

        self.assertEqual(await load_mcp_tools(settings), [])


if __name__ == "__main__":
    unittest.main()
