import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rulebook_rag.bm25 import BM25, tokenize  # noqa: E402
from rulebook_rag.chunks import chunk_markdown  # noqa: E402


class TokenizeTests(unittest.TestCase):
    def test_camel_case_is_split(self):
        # "chartYAxis" must share tokens with the plain words "chart" and "axis"
        toks = tokenize("chartYAxis")
        self.assertTrue(set(toks) & set(tokenize("chart")))
        self.assertTrue(set(toks) & set(tokenize("axis")))

    def test_russian_inflection_folds(self):
        self.assertEqual(tokenize("кольца")[0], tokenize("кольцо")[0])

    def test_stopwords_dropped(self):
        self.assertEqual(tokenize("и в на the a"), [])


class ChunkTests(unittest.TestCase):
    MD = """# Layout

Paragraph one that is long enough to be kept as a chunk on its own.

- rule one: symptom, cause, fix — kept as one chunk even with
  continuation lines and a code block
  ```swift
  let x = 1
  ```
- rule two: another rule with more than forty characters in it

## Table

| a | b |
|---|---|
| 1 | 2 |
"""

    def test_bullets_and_paragraphs_are_separate_chunks(self):
        chunks = chunk_markdown(self.MD, "t.md", min_chars=20)
        texts = [c.text for c in chunks]
        self.assertTrue(any(t.startswith("Paragraph one") for t in texts))
        self.assertTrue(any(t.startswith("- rule one") and "let x = 1" in t for t in texts))
        self.assertTrue(any(t.startswith("- rule two") for t in texts))

    def test_heading_path(self):
        chunks = chunk_markdown(self.MD, "t.md", min_chars=5)
        table = [c for c in chunks if c.text.startswith("|")][0]
        self.assertEqual(table.heading, "Layout > Table")


class BM25Tests(unittest.TestCase):
    def test_ranks_relevant_first(self):
        docs = ["кольца наплывают друг на друга обводка strokeBorder",
                "таббар раздулся minHeight 48",
                "swift charts chartYAxis AxisMarks"]
        bm = BM25(docs)
        top = bm.top("bar chart axis labels", 1)
        self.assertEqual(top[0][0], 2)
        top = bm.top("кольцо наплывает", 1)
        self.assertEqual(top[0][0], 0)


if __name__ == "__main__":
    unittest.main()
