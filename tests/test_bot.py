import unittest

from reports_wagent.bot import _chunks


class ChunkTests(unittest.TestCase):
    def test_short_text_stays_in_one_chunk(self) -> None:
        self.assertEqual(_chunks("hello", limit=10), ["hello"])

    def test_long_text_is_split_without_data_loss(self) -> None:
        text = "one two three four"
        chunks = _chunks(text, limit=8)
        self.assertTrue(all(len(chunk) <= 8 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
