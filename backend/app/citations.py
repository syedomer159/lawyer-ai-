"""Citations are data, checked in code (ADR-0005). An agent cites {chunk_id, quote}; the quote must
appear in that chunk of THIS case (exactly, or >= MIN_SCORE fuzzy to tolerate OCR noise)."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.store.case_store import CaseStore

MIN_SCORE = 0.9


class Citation(BaseModel):
    """What agents output. The field descriptions are shown to the model."""

    chunk_id: int = Field(description="id of the chunk, from the [chunk N] markers")
    quote: str = Field(description="exact words copied from that chunk (3 to 30 words)")


@dataclass(frozen=True)
class CheckedCitation:
    chunk_id: int
    quote: str
    verified: bool


_STRAIGHT_QUOTES = str.maketrans({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'})


def _norm(text: str) -> str:
    # OCR/LLM output often has curly quotes; compare on straight ones.
    text = text.lower().translate(_STRAIGHT_QUOTES)
    return re.sub(r"\s+", " ", text).strip()


def quote_score(quote: str, text: str) -> float:
    """1.0 if the quote is in the text; else the best fuzzy match over same-length windows."""
    q, t = _norm(quote), _norm(text)
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(q)  # cached once; only the window changes
    best, step = 0.0, max(1, len(q) // 10)
    for start in range(0, max(1, len(t) - len(q) + 1), step):
        matcher.set_seq1(t[start : start + len(q)])
        if matcher.real_quick_ratio() > best and matcher.quick_ratio() > best:
            best = max(best, matcher.ratio())
    return best


class CitationChecker:
    """Checks citations against one case's chunks (loaded once per analysis run)."""

    def __init__(self, store: CaseStore) -> None:
        self._texts = store.chunk_texts()

    def chunk_ids(self) -> list[int]:
        return list(self._texts)

    def check(self, c: Citation) -> CheckedCitation:
        text = self._texts.get(c.chunk_id)
        ok = text is not None and quote_score(c.quote, text) >= MIN_SCORE
        return CheckedCitation(c.chunk_id, c.quote, ok)

    def problems(self, citations: list[Citation]) -> list[str]:
        """Human-readable failures, fed back to the model as a retry hint."""
        out = []
        for c in citations:
            if c.chunk_id not in self._texts:
                out.append(f"chunk {c.chunk_id} does not exist")
            elif not self.check(c).verified:
                out.append(f'"{c.quote}" is not in chunk {c.chunk_id}; copy the words exactly')
        return out
