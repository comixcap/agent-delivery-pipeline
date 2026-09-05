"""Eval harness: does retrieval surface the RIGHT rule for a symptom?

    python3 -m rulebook_rag.evaluate index.json evalset.json

evalset.json: [{"q": "<symptom as a human or agent would phrase it>",
                "expect": "<substring that must appear in the correct rule>",
                "note": "<why this case exists>"}, ...]
Items with "expect": null are OUT-OF-SCOPE questions: the rulebook has no rule for them, and
the right behaviour is a low top score (abstain) rather than a confident wrong rule.

Metrics: hit@1, hit@3, hit@5, MRR on in-scope items; for out-of-scope items the top score,
so the abstain threshold can be chosen from data instead of guessed.
"""
import json
import sys

from .index import load
from .query import Retriever


def run(index_path: str, evalset_path: str, k: int = 5, verbose: bool = True):
    ret = Retriever(load(index_path))
    with open(evalset_path, encoding="utf-8") as f:
        cases = json.load(f)

    in_scope = [c for c in cases if c.get("expect")]
    out_scope = [c for c in cases if not c.get("expect")]

    hits = {1: 0, 3: 0, 5: 0}
    rr_sum = 0.0
    misses = []
    in_scores = []
    for c in in_scope:
        res = ret.search(c["q"], k)
        rank = None
        for i, (chunk, score) in enumerate(res, start=1):
            if c["expect"] in chunk.text:
                rank = i
                break
        if res:
            in_scores.append(res[0][1])
        if rank:
            rr_sum += 1.0 / rank
            for n in hits:
                if rank <= n:
                    hits[n] += 1
        else:
            misses.append((c["q"], [(ch.id, round(s, 2)) for ch, s in res[:3]]))

    n = len(in_scope) or 1
    out_scores = []
    for c in out_scope:
        res = ret.search(c["q"], 1)
        out_scores.append((c["q"], round(res[0][1], 2) if res else 0.0))

    report = {
        "in_scope": len(in_scope),
        "hit@1": round(hits[1] / n, 3),
        "hit@3": round(hits[3] / n, 3),
        "hit@5": round(hits[5] / n, 3),
        "mrr": round(rr_sum / n, 3),
        "in_scope_top_score_min": round(min(in_scores), 2) if in_scores else None,
        "out_of_scope_top_scores": out_scores,
        "misses": misses,
    }
    if verbose:
        print(f"in-scope cases: {report['in_scope']}")
        print(f"hit@1 {report['hit@1']}   hit@3 {report['hit@3']}   hit@5 {report['hit@5']}   MRR {report['mrr']}")
        print(f"lowest top-1 score among in-scope hits: {report['in_scope_top_score_min']}")
        if out_scores:
            print("out-of-scope top scores (should sit below the in-scope floor):")
            for q, s in out_scores:
                print(f"   {s:6.2f}  {q}")
        if misses:
            print("misses:")
            for q, top in misses:
                print(f"   {q}\n      got {top}")
    return report


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    r = run(argv[0], argv[1])
    return 0 if r["hit@3"] >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
