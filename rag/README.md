# rulebook_rag

Symptom → rule retrieval over the markdown rulebook, with an eval harness. Python 3.9+,
no third-party dependencies.

```
python3 -m rulebook_rag.index build ../rulebook index.json
python3 -m rulebook_rag.query index.json "кольца в ряду наплывают друг на друга"
python3 -m rulebook_rag.query index.json "bar chart overlaps axis labels" --answer   # needs ANTHROPIC_API_KEY
python3 -m rulebook_rag.evaluate index.json evalset.json
python3 -m unittest discover -s tests
```

## Pieces

- `chunks.py` — one rule = one chunk. Rules are long bullets (symptom → cause → fix);
  splitting them would separate the symptom from the fix. Tables stay whole; fenced code
  stays with its rule; heading path is kept as context.
- `bm25.py` — BM25 with a bilingual tokenizer: camelCase identifiers split
  (`chartYAxis` → `chart`, `y`, `axis`), crude Russian/English suffix folding, stop words.
- `query.py` — top-k retrieval; optional answer drafting through the Claude Messages API
  (`urllib`, no SDK). The system prompt requires rule-id citations and an explicit
  `NOT COVERED BY THE RULEBOOK`; below a retrieval-score threshold the model is not called.
- `evaluate.py` — hit@1/3/5 and MRR on in-scope symptoms; top scores on out-of-scope
  questions so the abstain threshold is chosen from data.

## Current numbers (26 in-scope, 3 out-of-scope)

| hit@1 | hit@3 | hit@5 | MRR | in-scope top-1 floor | out-of-scope top-1 |
|---|---|---|---|---|---|
| 0.923 | 0.962 | 1.0 | 0.946 | 2.84 | 0.00 / 0.00 / 0.00 |

The eval set is built from the rulebook's own symptom table plus rephrasings and two
English queries. It is small and written by the rulebook's author, so it measures
"does retrieval find what I meant" — not generalisation to strangers' phrasing. That is
the next thing to grow.
