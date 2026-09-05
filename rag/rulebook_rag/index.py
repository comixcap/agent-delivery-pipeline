"""Build and load the chunk index.

    python3 -m rulebook_rag.index build ../rulebook index.json
"""
import json
import sys
from typing import List

from .chunks import Chunk, load_dir


def build(rulebook_dir: str, out_path: str) -> List[Chunk]:
    chunks = load_dir(rulebook_dir)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=1)
    return chunks


def load(path: str) -> List[Chunk]:
    with open(path, encoding="utf-8") as f:
        return [Chunk(**d) for d in json.load(f)]


def main(argv):
    if len(argv) >= 3 and argv[0] == "build":
        chunks = build(argv[1], argv[2])
        sizes = sorted(len(c.text) for c in chunks)
        print(f"chunks: {len(chunks)}  median chars: {sizes[len(sizes)//2]}  max: {sizes[-1]}  → {argv[2]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
