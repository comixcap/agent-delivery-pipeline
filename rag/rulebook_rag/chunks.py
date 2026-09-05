"""Split markdown rulebooks into retrievable chunks.

A rulebook is written as headings plus long bullets: each top-level bullet is one rule
(symptom → cause → fix). The chunker keeps a rule intact — splitting a rule in the middle
would separate the symptom from the fix, which is exactly what retrieval needs together.

Boundaries: a heading line, a top-level bullet (`- ` at column 0), or a blank line outside
a code fence / table. Continuation lines (indented) and fenced code stay with their rule.
"""
import os
import re
from dataclasses import dataclass, asdict
from typing import List, Iterable

HEADING = re.compile(r"^(#{1,4})\s+(.*)")
BULLET = re.compile(r"^- ")


@dataclass
class Chunk:
    id: str          # "<file>#<n>"
    source: str      # file name
    heading: str     # nearest heading path, e.g. "Вёрстка > Таббар"
    text: str        # rule body (markdown kept)

    def to_dict(self):
        return asdict(self)


def _flush(buf, chunks, source, heading_path, counter, min_chars):
    text = "\n".join(buf).strip()
    buf.clear()
    if len(text) < min_chars:
        return
    counter[0] += 1
    chunks.append(Chunk(
        id=f"{source}#{counter[0]}",
        source=source,
        heading=" > ".join(h for h in heading_path if h),
        text=text,
    ))


def chunk_markdown(md: str, source: str, min_chars: int = 40) -> List[Chunk]:
    chunks: List[Chunk] = []
    buf: List[str] = []
    heading_path = ["", "", "", ""]
    counter = [0]
    in_fence = False
    in_table = False

    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            buf.append(line)
            continue
        if in_fence:
            buf.append(line)
            continue

        m = HEADING.match(line)
        if m:
            _flush(buf, chunks, source, heading_path, counter, min_chars)
            level = len(m.group(1))
            heading_path[level - 1] = m.group(2).strip()
            for i in range(level, 4):
                heading_path[i] = ""
            in_table = False
            continue

        if stripped.startswith("|"):
            # a table is one chunk: rows only make sense together
            if not in_table:
                _flush(buf, chunks, source, heading_path, counter, min_chars)
                in_table = True
            buf.append(line)
            continue
        elif in_table:
            _flush(buf, chunks, source, heading_path, counter, min_chars)
            in_table = False

        if BULLET.match(line):
            _flush(buf, chunks, source, heading_path, counter, min_chars)
            buf.append(line)
            continue

        if not stripped:
            # blank line ends a paragraph, but NOT a bullet whose continuation follows
            if buf and not BULLET.match(buf[0]):
                _flush(buf, chunks, source, heading_path, counter, min_chars)
            elif buf:
                buf.append(line)
            continue

        buf.append(line)

    _flush(buf, chunks, source, heading_path, counter, min_chars)
    return chunks


def load_dir(path: str, patterns: Iterable[str] = ("*.md",)) -> List[Chunk]:
    import glob
    out: List[Chunk] = []
    for pat in patterns:
        for p in sorted(glob.glob(os.path.join(path, pat))):
            with open(p, encoding="utf-8") as f:
                out += chunk_markdown(f.read(), os.path.basename(p))
    return out
