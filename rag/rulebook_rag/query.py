"""Retrieve rules for a symptom; optionally draft an answer with the Claude API.

    python3 -m rulebook_rag.query index.json "кольца в ряду наплывают друг на друга"
    python3 -m rulebook_rag.query index.json "bar chart overlaps axis labels" --answer

--answer requires ANTHROPIC_API_KEY. The model is told to answer ONLY from the retrieved
rules and to say "not covered by the rulebook" otherwise — an agent that invents a rule is
worse than one that admits the gap, because invented rules get written into code.
"""
import json
import os
import sys
import urllib.request
from typing import List, Tuple

from .bm25 import BM25
from .chunks import Chunk
from .index import load

MODEL = os.environ.get("RULEBOOK_RAG_MODEL", "claude-sonnet-5")
ABSTAIN_BELOW = float(os.environ.get("RULEBOOK_RAG_MIN_SCORE", "4.0"))


class Retriever:
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.bm25 = BM25([f"{c.heading}\n{c.text}" for c in chunks])

    def search(self, query: str, k: int = 5) -> List[Tuple[Chunk, float]]:
        return [(self.chunks[i], s) for i, s in self.bm25.top(query, k)]


SYSTEM = (
    "You are a rulebook assistant for a mobile-app delivery pipeline. Answer ONLY from the "
    "rules provided. Quote the rule id you rely on in square brackets, e.g. [layout.md#12]. "
    "If no provided rule covers the question, reply exactly: NOT COVERED BY THE RULEBOOK. "
    "Never invent a rule, an API, or a threshold that is not in the provided text."
)


def draft_answer(query: str, hits: List[Tuple[Chunk, float]]) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return "(no ANTHROPIC_API_KEY — retrieval only)"
    if not hits or hits[0][1] < ABSTAIN_BELOW:
        return "NOT COVERED BY THE RULEBOOK (retrieval score below threshold, model not called)"
    context = "\n\n".join(f"[{c.id}] {c.heading}\n{c.text}" for c, _ in hits)
    body = {
        "model": MODEL,
        "max_tokens": 600,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": f"Rules:\n\n{context}\n\nQuestion: {query}"}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return "".join(part.get("text", "") for part in data.get("content", []))


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    index_path, query = argv[0], argv[1]
    want_answer = "--answer" in argv
    k = 5
    ret = Retriever(load(index_path))
    hits = ret.search(query, k)
    if not hits:
        print("no hits"); return 1
    for c, s in hits:
        first = c.text.splitlines()[0][:110]
        print(f"{s:6.2f}  [{c.id}]  {c.heading}\n        {first}")
    if want_answer:
        print("\n--- answer ---")
        print(draft_answer(query, hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
