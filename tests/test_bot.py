import unittest
from pathlib import Path

from reports_wagent.bot import _chunks, _load_tavily_tools
from reports_wagent.config import Settings


class ChunkTests(unittest.TestCase):
    def test_short_text_stays_in_one_chunk(self) -> None:
        self.assertEqual(_chunks("hello", limit=10), ["hello"])

    def test_long_text_is_split_without_data_loss(self) -> None:
        text = "one two three four"
        chunks = _chunks(text, limit=8)
        self.assertTrue(all(len(chunk) <= 8 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


class TavilyToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_tavily_tools_returns_empty_without_key(self) -> None:
        settings = Settings(
            telegram_bot_token="telegram-secret",
            deepseek_api_key="deepseek-secret",
            allowed_user_ids=frozenset({123}),
            deepseek_model="deepseek-v4-flash",
            agent_workspace=Path.cwd(),
            agent_memory_db=Path.cwd() / ".agent_memory" / "checkpoints.sqlite",
            tavily_api_key=None,
        )

        self.assertEqual(await _load_tavily_tools(settings), [])


if __name__ == "__main__":
    unittest.main()
