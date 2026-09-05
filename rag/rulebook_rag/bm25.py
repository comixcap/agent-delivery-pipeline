"""BM25 with a bilingual (Russian + English + code identifiers) tokenizer.

Why not embeddings: the corpus is a few hundred rules written by one person in a fixed
vocabulary; the queries are symptoms from the same person or from an agent quoting the
symptom table. Lexical overlap is high, the corpus is tiny, and the whole thing must run
offline inside a build with no network access (network egress is on the deny list). BM25
is the honest baseline; the eval harness exists to tell whether anything better is needed.
"""
import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Tuple

_WORD = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# Crude Russian suffix stripper. Not a stemmer; enough to fold «кольца/кольцо/колец» → «кол».
_RU_SUFFIXES = (
    "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими", "ешь", "ете", "ует", "уют",
    "ать", "ять", "ить", "ить", "ся", "ов", "ев", "ей", "ой", "ый", "ий", "ая", "яя", "ое",
    "ее", "ые", "ие", "ом", "ем", "ах", "ях", "ам", "ям", "ой", "ть", "ет", "ит", "ут",
    "ют", "ла", "ли", "ло", "а", "я", "ы", "и", "е", "у", "ю", "о", "ь",
)
_EN_SUFFIXES = ("ing", "ies", "ed", "es", "s")

STOP = set("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только её
мне было вот от меня ещё нет о из ему теперь когда даже ну вдруг ли если уже или ни быть
был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть
надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда
кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас
были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот
через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед
иногда лучше чуть том нельзя такой им более всегда конечно всю между это
the a an of to in on for and or is are be at by with from as that this it its into not
""".split())


def _strip(word: str, suffixes: Sequence[str], min_len: int) -> str:
    for s in suffixes:
        if len(word) - len(s) >= min_len and word.endswith(s):
            return word[: -len(s)]
    return word


def tokenize(text: str) -> List[str]:
    out: List[str] = []
    for raw in _WORD.findall(text):
        parts = _CAMEL.split(raw) if any(c.isupper() for c in raw[1:]) else [raw]
        for p in parts:
            w = p.lower()
            if not w or w in STOP or (len(w) == 1 and not w.isdigit()):
                continue
            if re.search(r"[а-яё]", w):
                w = _strip(w, _RU_SUFFIXES, 3)
            else:
                w = _strip(w, _EN_SUFFIXES, 3)
            out.append(w)
    return out


class BM25:
    def __init__(self, docs: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tokens = [tokenize(d) for d in docs]
        self.n = len(docs)
        self.avgdl = (sum(len(t) for t in self.tokens) / self.n) if self.n else 0.0
        self.tf: List[Counter] = [Counter(t) for t in self.tokens]
        df: Dict[str, int] = defaultdict(int)
        for t in self.tokens:
            for w in set(t):
                df[w] += 1
        # BM25+ style idf, never negative
        self.idf = {w: math.log(1 + (self.n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def score(self, query: str) -> List[float]:
        q = tokenize(query)
        scores = [0.0] * self.n
        for i, tf in enumerate(self.tf):
            dl = len(self.tokens[i])
            norm = self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            s = 0.0
            for w in q:
                f = tf.get(w)
                if not f:
                    continue
                s += self.idf.get(w, 0.0) * f * (self.k1 + 1) / (f + norm)
            scores[i] = s
        return scores

    def top(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        sc = self.score(query)
        order = sorted(range(self.n), key=lambda i: sc[i], reverse=True)
        return [(i, sc[i]) for i in order[:k] if sc[i] > 0]
